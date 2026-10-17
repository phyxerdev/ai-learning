"""
Day 10 - Embeddings and RAG concepts
Run (same folder as llm.py and .env):
    ollama pull nomic-embed-text
    pip install numpy
    python day10_embeddings.py

Part 1: what an embedding is
Part 2: similarity = meaning, not spelling
Part 3: chunking a long document
Part 4: a tiny semantic search (preview of Day 11)
"""
import os
import re

import numpy as np

from llm import client

EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")


# =====================================================================
# Helpers
# =====================================================================
def embed(texts):
    """Turn a list of texts into a list of vectors (lists of numbers)."""
    resp = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [np.array(item.embedding) for item in resp.data]


def cosine_similarity(a, b):
    """1.0 = same direction (same meaning), ~0 = unrelated."""
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def chunk_text(text, max_words=120, overlap=20):
    """
    Split text into chunks of about max_words words.
    - Paragraphs are kept together when possible (they usually hold one idea).
    - Each new chunk repeats the last `overlap` words of the previous one,
      so an idea cut in half is still findable.
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

    # Step 1: list of word-groups. A paragraph that is too long is cut into pieces.
    piece = max_words - overlap
    units = []
    for para in paragraphs:
        words = para.split()
        for i in range(0, len(words), piece):
            units.append(words[i:i + piece])

    # Step 2: glue groups together until the chunk is full, then start a new one
    # that begins with the last `overlap` words of the previous chunk.
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


def main():
    # =================================================================
    # Part 1: what does an embedding look like?
    # =================================================================
    print("=" * 60 + "\nPART 1: an embedding is just a list of numbers\n" + "=" * 60)
    vec = embed(["cat"])[0]
    print(f"Model: {EMBED_MODEL}")
    print(f"'cat' becomes {len(vec)} numbers. First 5: {np.round(vec[:5], 4)}")
    print("Each number is one 'direction of meaning'. Similar meanings -> similar numbers.\n")

    # =================================================================
    # Part 2: similarity measures MEANING
    # =================================================================
    print("=" * 60 + "\nPART 2: which words are closest?\n" + "=" * 60)
    words = ["cat", "kitten", "invoice"]
    vecs = embed(words)
    for i in range(len(words)):
        for j in range(i + 1, len(words)):
            print(f"  {words[i]:<8} vs {words[j]:<8} = {cosine_similarity(vecs[i], vecs[j]):.3f}")

    print("\nSame idea, different words vs similar words, different idea:")
    base = "how much money did we spend on ads"
    others = [
        "total advertising budget used",      # different words, SAME meaning
        "how much money did we earn from sales",  # similar words, DIFFERENT meaning
        "recipe for fried rice",               # unrelated
    ]
    vb, *vo = embed([base] + others)
    for text, v in zip(others, vo):
        print(f"  {cosine_similarity(vb, v):.3f}  '{text}'")
    print("Keyword search would miss the first one. Embeddings catch it.\n")

    # =================================================================
    # Part 3: chunking a long document
    # =================================================================
    print("=" * 60 + "\nPART 3: chunking ads_handbook.txt\n" + "=" * 60)
    with open("ads_handbook.txt", encoding="utf-8") as f:
        doc = f.read()
    chunks = chunk_text(doc, max_words=120, overlap=20)
    print(f"Document: {len(doc.split())} words -> {len(chunks)} chunks\n")
    for i, c in enumerate(chunks):
        preview = c[:110] + ("..." if len(c) > 110 else "")
        print(f"  [{i}] ({len(c.split())} words) {preview}")

    # =================================================================
    # Part 4: tiny semantic search (this is the 'R' in RAG)
    # =================================================================
    print("\n" + "=" * 60 + "\nPART 4: find the right chunk for a question\n" + "=" * 60)
    chunk_vecs = embed(chunks)  # embed ALL chunks once (on Day 11 we save these)
    questions = [
        "When should I turn off a campaign that is too expensive?",
        "What do I do if our website gets blocked?",
        "How long can a video ad be?",
    ]
    for q in questions:
        qv = embed([q])[0]
        scores = [cosine_similarity(qv, cv) for cv in chunk_vecs]
        best = int(np.argmax(scores))
        print(f"\nQ: {q}")
        print(f"   best chunk [{best}] score {scores[best]:.3f}: {chunks[best][:120]}...")
    print("\nNo LLM answered anything yet - we only FOUND the right text.")
    print("Day 11: give these chunks to the LLM and let it answer from them.")


if __name__ == "__main__":
    main()
