# Ads Report Explainer

Reads a CSV of Facebook Ads results, calculates the key metrics (CTR, CPC, cost per conversion, conversion rate, spend share), and asks an LLM for a 5-bullet summary plus 3 concrete suggestions. Works with a free local model (Ollama) or any OpenAI-compatible API.

## How it works

1. **Python** loads the CSV and calculates every metric (LLMs are bad at maths, so the model never calculates).
2. The results go into a prompt as a table inside `<data>` tags, with a strict system prompt.
3. The **LLM** explains the numbers and suggests actions, streamed live.
4. The table and analysis are saved to `report_YYYY-MM-DD.md`.

## Setup

```
pip install -r requirements.txt
ollama pull qwen3:8b
copy .env.example .env        (Windows)   |   cp .env.example .env   (Mac/Linux)
```

## Run

```
python explainer.py                                   # uses sample_ads.csv
python explainer.py my_ads.csv
python explainer.py my_ads.csv --goal "maximise clicks under $500"
```

Your CSV needs these columns: `campaign, spend, impressions, clicks, conversions`.

## Switching engines

Edit `.env` only. Examples are in `.env.example` (Ollama, Gemini, GLM).

## Files

| File | What it does |
| --- | --- |
| `explainer.py` | Main script: load, calculate, prompt, save |
| `llm.py` | One client for every engine, reads `.env` |
| `sample_ads.csv` | Example data |
| `.env.example` | Settings template (copy to `.env`) |
