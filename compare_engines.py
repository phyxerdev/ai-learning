"""
Day 14 - Compare engines on the same questions.

Runs the same test questions through every engine you have a settings file for
(.env.ollama, .env.gemini, .env.glm ...), checks each answer against the expected
fact, times it, and writes compare_report.md.

Run:
    python compare_engines.py                         # all .env.* files except .env.example
    python compare_engines.py .env.ollama .env.gemini # only these
"""
import glob
import json
import os
import subprocess
import sys
import time
from datetime import datetime

DOC = "ads_handbook.txt"

# (question, words that MUST appear in a correct answer, or None = should be "not covered")
QUESTIONS = [
    ("What is the target cost per conversion?", ["8"]),
    ("How much can I increase the daily budget when scaling?", ["20%"]),
    ("What should I do if the landing page domain is blocked?", ["backup", "1 hour"]),
    ("How long can a video ad be?", ["15"]),
    ("When should I pause an ad because people don't click?", ["0.8%", "5,000"]),
    ("What is our refund policy?", None),
    ("What is the target cost per click?", None),      # trick: only cost per CONVERSION exists
]


# ---------------------------------------------------------------- worker (one engine)
def run_worker(env_file):
    """Runs in a separate Python process, so each engine gets fresh settings."""
    from dotenv import load_dotenv, dotenv_values
    load_dotenv(env_file, override=True)       # this engine's settings win over everything
    # Settings this file doesn't mention must not leak in from your main .env
    for key in ("EMBED_BASE_URL", "EMBED_API_KEY", "NO_THINK_TAG"):
        if key not in dotenv_values(env_file):
            os.environ[key] = ""
    import rag                                  # imported AFTER loading settings on purpose
    from llm import MODEL

    t0 = time.time()
    index, _ = rag.load_or_build_index(DOC)
    results = {"engine": env_file, "model": MODEL, "embed_model": rag.EMBED_MODEL,
               "min_score": rag.MIN_SCORE, "index_seconds": round(time.time() - t0, 1), "rows": []}

    for question, must_contain in QUESTIONS:
        start = time.time()
        try:
            answer, hits = rag.answer(question, index)
            error = None
        except Exception as e:
            answer, hits, error = "", [], f"{type(e).__name__}: {e}"
        seconds = round(time.time() - start, 1)
        said_not_found = "isn't covered" in answer.lower() or "not covered" in answer.lower()

        if error:
            verdict = "ERROR"
        elif must_contain is None:
            verdict = "PASS" if said_not_found else "FAIL (invented an answer)"
        elif said_not_found:
            verdict = "FAIL (refused)"
        elif all(w.lower() in answer.lower() for w in must_contain):
            verdict = "PASS"
        else:
            verdict = "CHECK (missing: " + ", ".join(w for w in must_contain if w.lower() not in answer.lower()) + ")"

        results["rows"].append({
            "question": question, "verdict": verdict, "seconds": seconds,
            "best_score": round(hits[0][0], 3) if hits else None,
            "answer": (error or answer).strip().replace("\n", " "),
        })
        time.sleep(1)   # be gentle with free-tier rate limits
    print("@@RESULT@@" + json.dumps(results))


# ---------------------------------------------------------------- parent (all engines)
def main():
    env_files = sys.argv[1:] or sorted(f for f in glob.glob(".env.*") if not f.endswith(".example"))
    if not env_files:
        sys.exit("No settings files found. Create e.g. .env.ollama and .env.gemini first.")

    all_results = []
    for env_file in env_files:
        print(f"Testing {env_file} ...", flush=True)
        proc = subprocess.run(
            [sys.executable, __file__, "--worker", env_file],
            capture_output=True, text=True, encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        line = next((l for l in proc.stdout.splitlines() if l.startswith("@@RESULT@@")), None)
        if not line:
            print(f"  failed:\n{proc.stderr[-800:]}")
            continue
        res = json.loads(line[len("@@RESULT@@"):])
        passed = sum(r["verdict"] == "PASS" for r in res["rows"])
        print(f"  {res['model']}: {passed}/{len(res['rows'])} passed")
        all_results.append(res)

    write_report(all_results)


def write_report(all_results):
    lines = [f"# Engine comparison - {datetime.now():%Y-%m-%d %H:%M}", "",
             f"Document: `{DOC}`, {len(QUESTIONS)} questions "
             f"({sum(m is None for _, m in QUESTIONS)} should be refused).", "",
             "## Summary", "",
             "| Settings | Answer model | Embeddings | Threshold | Passed | Avg seconds |",
             "| --- | --- | --- | --- | --- | --- |"]
    for r in all_results:
        passed = sum(x["verdict"] == "PASS" for x in r["rows"])
        avg = sum(x["seconds"] for x in r["rows"]) / len(r["rows"])
        lines.append(f"| {r['engine']} | {r['model']} | {r['embed_model']} | {r['min_score']} "
                     f"| {passed}/{len(r['rows'])} | {avg:.1f} |")

    for r in all_results:
        lines += ["", f"## {r['engine']} ({r['model']})", "",
                  "| Question | Verdict | Score | Sec | Answer |", "| --- | --- | --- | --- | --- |"]
        for x in r["rows"]:
            ans = x["answer"][:160].replace("|", "/") + ("..." if len(x["answer"]) > 160 else "")
            lines.append(f"| {x['question']} | {x['verdict']} | {x['best_score']} | {x['seconds']} | {ans} |")

    lines += ["", "Verdicts: PASS = correct; CHECK = answered but a key fact is missing (read it); "
              "FAIL (refused) = said not covered but it is; FAIL (invented) = should have said not covered."]
    with open("compare_report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\nSaved compare_report.md - open it in VS Code (Ctrl+Shift+V for preview).")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--worker":
        run_worker(sys.argv[2])
    else:
        main()