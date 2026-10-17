"""
rag.py - Retrieval-Augmented Generation, step by step.
Reusable: day11_ask.py uses it now, the Streamlit app (Day 12) uses it later.

    load_document -> chunk_text -> build_index (embed + save)
    question -> search (top chunks + scores) -> answer (LLM, with citations)
"""
import hashlib
import json
import os
import re

import numpy as np

from llm import client, chat, NO_THINK_TAG

EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")

# Embeddings normally use the same engine as chat. Set EMBED_BASE_URL + EMBED_API_KEY
# to use a different one (e.g. GLM for answers, Gemini for embeddings).
if os.getenv("EMBED_BASE_URL"):
    from openai import OpenAI
    embed_client = OpenAI(base_url=os.getenv("EMBED_BASE_URL"),
                          api_key=os.getenv("EMBED_API_KEY", "none"))
else:
    embed_client = client
MIN_SCORE = float(os.getenv("RAG_MIN_SCORE", "0.55"))   # set this from your Day 10 measurements!
NOT_FOUND = "That isn't covered in the document."


# ---------------------------------------------------------------- 1. Load
def load_document(path):
    """Read .txt / .md / .pdf into plain text."""
    if path.lower().endswith(".pdf"):
        from pypdf import PdfReader          # pip install pypdf (only needed for PDFs)
        reader = PdfReader(path)
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    with open(path, encoding="utf-8") as f:
        return f.read()


def load_document_bytes(filename, data):
    """Same as load_document, but for a file uploaded in a web app (we get bytes, not a path)."""
    if filename.lower().endswith(".pdf"):
        import io
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    return data.decode("utf-8", errors="replace")


# ---------------------------------------------------------------- 2. Chunk
def chunk_text(text, max_words=120, overlap=20):
    """Same chunker as Day 10: keep paragraphs together, overlap between chunks."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    piece = max_words - overlap
    units = []
    for para in paragraphs:
        words = para.split()
        for i in range(0, len(words), piece):
            units.append(words[i:i + piece])

    chunks, current, new_words = [], [], 0
    for unit in units:
        if new_words and len(current) + len(unit) > max_words:
            chunks.append(" ".join(current))
            current, new_words = current[-overlap:], 0
        current += unit
        new_words += len(unit)
    if new_words:
        chunks.append(" ".join(current))
    return chunks


# ---------------------------------------------------------------- 3. Embed + index
def embed(texts, batch_size=32):
    """Embed many texts, a batch at a time. Returns a 2D numpy array (one row per text)."""
    vectors = []
    for i in range(0, len(texts), batch_size):
        resp = embed_client.embeddings.create(model=EMBED_MODEL, input=texts[i:i + batch_size])
        vectors += [item.embedding for item in resp.data]
    arr = np.array(vectors, dtype=np.float32)
    # Normalise once, so cosine similarity becomes a simple dot product later
    return arr / np.linalg.norm(arr, axis=1, keepdims=True)


def build_index(text, max_words=120, overlap=20, max_chunks=None):
    chunks = chunk_text(text, max_words, overlap)
    truncated = bool(max_chunks and len(chunks) > max_chunks)
    if truncated:
        chunks = chunks[:max_chunks]           # protects your API quota on huge documents
    return {
        "embed_model": EMBED_MODEL,
        "settings": {"max_words": max_words, "overlap": overlap},
        "fingerprint": hashlib.md5(text.encode()).hexdigest(),
        "chunks": chunks,
        "vectors": embed(chunks),
        "truncated": truncated,
    }


def save_index(index, path):
    data = dict(index, vectors=index["vectors"].tolist())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def load_or_build_index(doc_path, max_words=120, overlap=20):
    """
    Embedding costs time (and money on cloud APIs), so we save the index next to the document
    and reuse it. It is rebuilt automatically if the document, chunk settings or embedding
    model changed - vectors from different models must never be mixed.
    """
    text = load_document(doc_path)
    index_path = doc_path + ".index.json"
    wanted = {"embed_model": EMBED_MODEL,
              "settings": {"max_words": max_words, "overlap": overlap},
              "fingerprint": hashlib.md5(text.encode()).hexdigest()}

    if os.path.exists(index_path):
        with open(index_path, encoding="utf-8") as f:
            data = json.load(f)
        if all(data.get(k) == v for k, v in wanted.items()):
            data["vectors"] = np.array(data["vectors"], dtype=np.float32)
            return data, "loaded"

    index = build_index(text, max_words, overlap)
    save_index(index, index_path)
    return index, "built"


# ---------------------------------------------------------------- 4. Search
def search(index, question, k=3):
    """Return the top-k chunks as [(score, chunk_id, text)], best first."""
    q = embed([question])[0]
    scores = index["vectors"] @ q              # dot product of normalised vectors = cosine similarity
    top = np.argsort(scores)[::-1][:k]
    return [(float(scores[i]), int(i), index["chunks"][i]) for i in top]


# ---------------------------------------------------------------- 5. Answer
SYSTEM_PROMPT = f"""You answer questions using ONLY the document excerpts inside <documents>.
Rules:
- If the excerpts do not contain the answer, reply exactly: "{NOT_FOUND}"
- Never use outside knowledge, never guess.
- Keep answers short and specific; include numbers exactly as written.
- After each fact, cite the chunk it came from, like [chunk 3]."""


def build_prompt(question, hits):
    docs = "\n".join(f'<chunk id="{cid}">\n{text}\n</chunk>' for _, cid, text in hits)
    return f"<documents>\n{docs}\n</documents>\n\nQuestion: {question}{NO_THINK_TAG}"


def prompt_messages(question, hits):
    """The full message list for the LLM (used by the web app to stream the answer)."""
    return [{"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_prompt(question, hits)}]


def answer(question, index, k=3, min_score=MIN_SCORE, stream=False, hits=None):
    """
    Full RAG: search, then (only if something relevant was found) ask the LLM.
    Pass `hits` if you already searched, to avoid embedding the question twice.
    Returns (answer_text, hits).
    """
    if hits is None:
        hits = search(index, question, k)

    # Filter 1: retrieval score. Nothing relevant -> don't even call the LLM.
    if not hits or hits[0][0] < min_score:
        return NOT_FOUND, hits

    # Filter 2: the prompt tells the LLM to say NOT_FOUND if the chunks don't answer it.
    text = chat(prompt_messages(question, hits), stream=stream, temperature=0)
    return text, hits
