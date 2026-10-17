"""
list_models.py - show which model names your current engine (.env) accepts.
Run:  python list_models.py
Use it after switching .env to Gemini (or GLM) to copy the exact names into LLM_MODEL / EMBED_MODEL.
"""
from llm import client, BASE_URL

print(f"Models available at {BASE_URL}\n")
names = sorted(m.id for m in client.models.list())

embed = [n for n in names if "embed" in n.lower()]
chat = [n for n in names if n not in embed]

print("Chat models (for LLM_MODEL):")
for n in chat:
    print("  ", n.removeprefix("models/"))
print("\nEmbedding models (for EMBED_MODEL):")
for n in embed:
    print("  ", n.removeprefix("models/"))
print("\nTip: for a free public app pick a 'flash' or 'flash-lite' chat model.")
