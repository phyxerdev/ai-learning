"""
Day 12-13 - "Ask My Docs" web app
Run locally (same folder as llm.py, rag.py and .env):
    python -m streamlit run app.py
On Streamlit Cloud, settings come from the app's Secrets instead of .env.
"""
import hashlib
import os
from urllib.parse import urlparse

import streamlit as st

# Streamlit Cloud has no .env file: copy the app's Secrets into environment variables
# BEFORE importing llm/rag, so they read them exactly like they read .env locally.
try:
    for key, value in st.secrets.items():
        if isinstance(value, (str, int, float)):
            os.environ.setdefault(key, str(value))
except Exception:
    pass  # no secrets file (running locally) -> .env is used

import rag                                           # noqa: E402
from llm import MODEL, BASE_URL, stream_chat         # noqa: E402

st.set_page_config(page_title="Ask My Docs", page_icon="📄")

# ---- Limits: protect your free quota / money on a public app ----
MAX_FILE_MB = int(os.getenv("MAX_FILE_MB", "5"))
MAX_CHUNKS = int(os.getenv("MAX_CHUNKS", "150"))           # caps embedding calls per document
MAX_QUESTIONS = int(os.getenv("MAX_QUESTIONS", "20"))      # per browser session
ANSWER_MAX_TOKENS = int(os.getenv("ANSWER_MAX_TOKENS", "600"))
APP_PASSWORD = os.getenv("APP_PASSWORD", "")               # empty = open to everyone

# ---- Optional password gate ----
if APP_PASSWORD and not st.session_state.get("unlocked"):
    st.title("Ask My Docs")
    pw = st.text_input("Password", type="password")
    if pw == APP_PASSWORD:
        st.session_state.unlocked = True
        st.rerun()
    elif pw:
        st.error("Wrong password.")
    st.stop()

# ------------------------------------------------------------------
# st.session_state = memory that survives while the page is open.
# (Streamlit re-runs this whole script on every click or message!)
# ------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []        # chat history shown on screen
    st.session_state.questions_used = 0
if "index" not in st.session_state:
    st.session_state.index = None         # the RAG index of the current document
    st.session_state.doc_name = None
    st.session_state.doc_id = None


@st.cache_resource(show_spinner=False)
def build_index_cached(doc_id, text):
    """Embedding is slow, so Streamlit remembers the result for the same document."""
    return rag.build_index(text, max_chunks=MAX_CHUNKS)


# ------------------------------------------------------------------ Sidebar
with st.sidebar:
    st.header("📄 Document")
    uploaded = st.file_uploader("Upload a .txt, .md or .pdf", type=["txt", "md", "pdf"])
    use_sample = st.button("Use sample: ads_handbook.txt")

    st.header("⚙️ Settings")
    k = st.slider("Chunks given to the model (k)", 1, 6, 3)
    min_score = st.slider("Minimum score (threshold)", 0.0, 1.0, float(rag.MIN_SCORE), 0.01)
    show_sources = st.toggle("Show sources", value=True)
    if st.button("Clear chat"):
        st.session_state.messages = []

    st.divider()
    host = urlparse(BASE_URL).hostname or BASE_URL
    engine = "Ollama (local)" if host in ("localhost", "127.0.0.1") else host
    st.caption(f"Engine: **{engine}**  \nModel: **{MODEL}**  \nEmbeddings: **{rag.EMBED_MODEL}**  \n"
               f"Questions left: **{MAX_QUESTIONS - st.session_state.questions_used}**")


# ------------------------------------------------------------------ Errors
def friendly_error(e):
    """Turn API errors into messages a normal user understands."""
    name = type(e).__name__
    if name == "RateLimitError" or "429" in str(e):
        return "⏳ The app is busy (free quota limit reached). Please wait a minute and try again."
    if name in ("AuthenticationError", "PermissionDeniedError"):
        return "🔑 The app's API key is missing or invalid. (Owner: check the Secrets settings.)"
    if name == "NotFoundError":
        return "❓ Model not found. (Owner: check LLM_MODEL / EMBED_MODEL in the settings.)"
    if name == "APIConnectionError":
        return "🔌 Can't reach the AI engine. (Owner: is LLM_BASE_URL right? Is Ollama running?)"
    return f"⚠️ Something went wrong: {e}"


# ------------------------------------------------------------------ Load a document
def set_document(name, text):
    doc_id = hashlib.md5(text.encode()).hexdigest()
    if doc_id == st.session_state.doc_id:
        return                                # same document, nothing to do
    if not text.strip():
        st.sidebar.error("No text found in this file (scanned PDFs have images, not text).")
        return
    with st.spinner(f"Reading and embedding {name}..."):
        st.session_state.index = build_index_cached(doc_id, text)
    if st.session_state.index.get("truncated"):
        st.sidebar.warning(f"Long document: only the first {MAX_CHUNKS} chunks were indexed.")
    st.session_state.doc_name, st.session_state.doc_id = name, doc_id
    st.session_state.messages = []            # new document -> fresh chat


try:
    if uploaded is not None:
        if uploaded.size > MAX_FILE_MB * 1024 * 1024:
            st.sidebar.error(f"File too large (max {MAX_FILE_MB} MB).")
        else:
            set_document(uploaded.name, rag.load_document_bytes(uploaded.name, uploaded.getvalue()))
    elif use_sample:
        set_document("ads_handbook.txt", rag.load_document("ads_handbook.txt"))
except Exception as e:
    st.sidebar.error(friendly_error(e))


# ------------------------------------------------------------------ Main page
st.title("Ask My Docs")

if st.session_state.index is None:
    st.info("👈 Upload a document (or use the sample) to start asking questions.")
    st.stop()                                 # nothing else to show until a document is loaded

st.caption(f"Chatting with **{st.session_state.doc_name}** "
           f"({len(st.session_state.index['chunks'])} chunks)")


def render_sources(hits):
    with st.expander("Sources"):
        for score, cid, text in hits:
            mark = "✅" if score >= min_score else "⬜"
            st.markdown(f"{mark} **chunk {cid}** · score {score:.3f}")
            st.caption(text)


# Show the conversation so far
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if show_sources and m.get("hits"):
            render_sources(m["hits"])

# New question
limit_reached = st.session_state.questions_used >= MAX_QUESTIONS
if limit_reached:
    st.warning(f"You've used all {MAX_QUESTIONS} questions for this session. Thanks for trying the app!")

question = st.chat_input("Ask something about the document...", disabled=limit_reached, max_chars=500)
if question and not limit_reached:
    st.session_state.questions_used += 1
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        try:
            hits = rag.search(st.session_state.index, question, k)
            if not hits or hits[0][0] < min_score:
                reply = rag.NOT_FOUND                       # filter 1: score too low, skip the LLM
                st.markdown(reply)
            else:
                reply = st.write_stream(                    # filter 2 lives in the prompt
                    stream_chat(rag.prompt_messages(question, hits), temperature=0,
                                max_tokens=ANSWER_MAX_TOKENS))
        except Exception as e:
            hits, reply = [], friendly_error(e)
            st.markdown(reply)
        if show_sources and hits:
            render_sources(hits)

    st.session_state.messages.append({"role": "assistant", "content": reply, "hits": hits})
    if st.session_state.questions_used >= MAX_QUESTIONS:
        st.rerun()                                   # refresh so the limit message shows right away
