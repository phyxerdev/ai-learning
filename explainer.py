"""
Ads Report Explainer - Day 7 mini project
Reads a CSV of ad results, calculates the metrics in Python,
and asks the LLM for a 5-bullet summary + 3 suggestions.

Run:
    python explainer.py                      # uses sample_ads.csv
    python explainer.py my_ads.csv           # your own file
    python explainer.py my_ads.csv --goal "lowest cost per conversion"
"""
import argparse
import csv
import sys
from datetime import date

from llm import chat, MODEL, NO_THINK_TAG

REQUIRED_COLUMNS = ["campaign", "spend", "impressions", "clicks", "conversions"]

SYSTEM_PROMPT = """You are a senior Facebook Ads analyst writing for a busy marketer.
Rules:
- Use ONLY the numbers inside <data>. Never invent numbers.
- The metrics are already calculated correctly. Do not recalculate them.
- Write in plain, simple English.
- Output exactly this format and nothing else:

## Summary
- (5 bullets: overall result, best campaign, worst campaign, one surprising pattern, budget view)

## Suggestions
1. (specific action, naming the campaign and the number that justifies it)
2. ...
3. ..."""


# ---------- 1. Load and check the CSV ----------
def load_csv(path):
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
    except FileNotFoundError:
        sys.exit(f"File not found: {path}")

    if not rows:
        sys.exit("The CSV is empty.")
    missing = [c for c in REQUIRED_COLUMNS if c not in rows[0]]
    if missing:
        sys.exit(f"CSV is missing columns: {missing}. Needed: {REQUIRED_COLUMNS}")

    campaigns = []
    for i, r in enumerate(rows, start=2):  # row 1 is the header
        try:
            campaigns.append({
                "campaign": r["campaign"].strip(),
                "spend": float(r["spend"]),
                "impressions": int(float(r["impressions"])),
                "clicks": int(float(r["clicks"])),
                "conversions": int(float(r["conversions"])),
            })
        except ValueError:
            print(f"(skipping row {i}: not a valid number -> {r})")
    return campaigns


# ---------- 2. Calculate metrics in Python (never trust LLM maths - Day 6) ----------
def safe_div(a, b):
    return a / b if b else None


def add_metrics(campaigns):
    for c in campaigns:
        c["ctr"] = safe_div(c["clicks"], c["impressions"])           # click-through rate
        c["cpc"] = safe_div(c["spend"], c["clicks"])                 # cost per click
        c["cpa"] = safe_div(c["spend"], c["conversions"])            # cost per conversion
        c["cvr"] = safe_div(c["conversions"], c["clicks"])           # conversion rate
        c["spend_share"] = None
    total_spend = sum(c["spend"] for c in campaigns)
    for c in campaigns:
        c["spend_share"] = safe_div(c["spend"], total_spend)

    totals = {
        "spend": total_spend,
        "impressions": sum(c["impressions"] for c in campaigns),
        "clicks": sum(c["clicks"] for c in campaigns),
        "conversions": sum(c["conversions"] for c in campaigns),
    }
    totals["ctr"] = safe_div(totals["clicks"], totals["impressions"])
    totals["cpa"] = safe_div(totals["spend"], totals["conversions"])
    return campaigns, totals


def fmt(value, kind):
    if value is None:
        return "n/a"
    if kind == "pct":
        return f"{value * 100:.2f}%"
    if kind == "usd":
        return f"${value:,.2f}"
    return f"{value:,}"


def build_table(campaigns, totals):
    """A clean text table - used both for the prompt and for printing."""
    header = f"{'Campaign':<18}{'Spend':>10}{'Share':>8}{'Impr.':>10}{'Clicks':>8}{'Conv.':>7}{'CTR':>8}{'CPC':>8}{'CPA':>10}{'CVR':>8}"
    lines = [header, "-" * len(header)]
    for c in sorted(campaigns, key=lambda c: c["cpa"] if c["cpa"] is not None else float("inf")):
        lines.append(
            f"{c['campaign']:<18}{fmt(c['spend'], 'usd'):>10}{fmt(c['spend_share'], 'pct'):>8}"
            f"{fmt(c['impressions'], 'int'):>10}{fmt(c['clicks'], 'int'):>8}{fmt(c['conversions'], 'int'):>7}"
            f"{fmt(c['ctr'], 'pct'):>8}{fmt(c['cpc'], 'usd'):>8}{fmt(c['cpa'], 'usd'):>10}{fmt(c['cvr'], 'pct'):>8}"
        )
    lines.append("-" * len(header))
    lines.append(
        f"{'TOTAL':<18}{fmt(totals['spend'], 'usd'):>10}{'100%':>8}{fmt(totals['impressions'], 'int'):>10}"
        f"{fmt(totals['clicks'], 'int'):>8}{fmt(totals['conversions'], 'int'):>7}{fmt(totals['ctr'], 'pct'):>8}"
        f"{'':>8}{fmt(totals['cpa'], 'usd'):>10}"
    )
    return "\n".join(lines)


# ---------- 3. Ask the LLM to explain ----------
def explain(table, goal):
    user_msg = f"""Business goal: {goal}

<data>
{table}
</data>

CTR = clicks/impressions, CPC = cost per click, CPA = cost per conversion,
CVR = conversions/clicks, Share = share of total spend. Sorted by CPA (best first).

Write the summary and suggestions.{NO_THINK_TAG}"""

    return chat(
        [{"role": "system", "content": SYSTEM_PROMPT},
         {"role": "user", "content": user_msg}],
        stream=True,
        temperature=0.3,
    )


# ---------- 4. Put it together ----------
def main():
    parser = argparse.ArgumentParser(description="Explain an ads CSV with an LLM")
    parser.add_argument("csv_path", nargs="?", default="sample_ads.csv")
    parser.add_argument("--goal", default="get the lowest cost per conversion")
    args = parser.parse_args()

    campaigns, totals = add_metrics(load_csv(args.csv_path))
    table = build_table(campaigns, totals)

    print(f"\nModel: {MODEL}   File: {args.csv_path}\n")
    print(table)
    print("\n" + "=" * 40 + "\n")

    try:
        analysis = explain(table, args.goal)
    except Exception as e:
        sys.exit(f"\nCould not reach the model: {e}\nIs Ollama running? Check your .env settings.")

    out_file = f"report_{date.today().isoformat()}.md"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(f"# Ads report - {date.today().isoformat()}\n\n")
        f.write(f"Source: `{args.csv_path}` | Model: `{MODEL}` | Goal: {args.goal}\n\n")
        f.write("```\n" + table + "\n```\n\n" + analysis + "\n")
    print(f"\nSaved report to {out_file}")


if __name__ == "__main__":
    main()
