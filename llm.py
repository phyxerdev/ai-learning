"""
llm.py - one place to talk to ANY engine (Ollama, GLM, Gemini...).
Every project imports from here, so switching engines = editing .env only.
"""
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
API_KEY = os.getenv("LLM_API_KEY", "ollama")
MODEL = os.getenv("LLM_MODEL", "qwen3:30b-a3b")
# Qwen3 on Ollama thinks by default; "/no_think" turns it off. Other engines ignore it harmlessly,
# but you can set NO_THINK_TAG= (empty) in .env when you switch engines.
NO_THINK_TAG = os.getenv("NO_THINK_TAG", " /no_think")

client = OpenAI(base_url=BASE_URL, api_key=API_KEY)


def chat(messages, stream=False, temperature=0.3, max_tokens=1200):
    """
    Send messages, return the answer text.
    stream=True prints the answer live while it arrives, then returns the full text.
    """
    resp = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=stream,
    )
    if not stream:
        return resp.choices[0].message.content

    text = ""
    for chunk in resp:
        if chunk.choices and chunk.choices[0].delta.content:
            piece = chunk.choices[0].delta.content
            print(piece, end="", flush=True)
            text += piece
    print()
    return text
