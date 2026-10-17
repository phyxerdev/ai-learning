"""
Day 11 - Mini project 2: "Ask my documents"
Run (same folder as llm.py, rag.py and .env):
    python day11_ask.py                         # uses ads_handbook.txt
    python day11_ask.py my_file.pdf             # any .txt / .md / .pdf (pip install pypdf for PDF)
    python day11_ask.py --min-score 0.6 --k 3

Commands:  /test  run the 5-question check   /sources  show/hide the retrieved chunks
           /quit
"""
import argparse
import time

import rag
from llm import MODEL

TEST_QUESTIONS = [
    ("What is the target cost per conversion?", True),
    ("How much can I increase the budget per day when scaling?", True),
    ("What should I do if the landing page domain is blocked?", True),
    ("What is our refund policy?", False),
    ("Who is the CEO of the company?", False),
]


def show_hits(hits, min_score):
    for score, cid, text in hits:
        mark = "ok " if score >= min_score else "low"
        print(f"   [{mark}] chunk {cid}  score {score:.3f}  {text[:90]}...")


def run_tests(index, k, min_score):
    """3 answerable + 2 unanswerable questions: a quick quality check."""
    print(f"\n=== Test run: model {MODEL}, min_score {min_score} ===")
    correct = 0
    for q, answerable in TEST_QUESTIONS:
        start = time.time()
        ans, hits = rag.answer(q, index, k=k, min_score=min_score)
        said_not_found = rag.NOT_FOUND.lower()[:20] in ans.lower()
        ok = (answerable and not said_not_found) or (not answerable and said_not_found)
        correct += ok
        print(f"\n{'PASS' if ok else 'FAIL'}  Q: {q}   (best score {hits[0][0]:.3f}, {time.time() - start:.1f}s)")
        print(f"      A: {ans.strip()}")
    print(f"\nScore: {correct}/{len(TEST_QUESTIONS)}  (also read the answers: right facts? right citations?)\n")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("doc", nargs="?", default="ads_handbook.txt")
    p.add_argument("--k", type=int, default=3, help="how many chunks to give the LLM")
    p.add_argument("--min-score", type=float, default=rag.MIN_SCORE)
    p.add_argument("--max-words", type=int, default=120)
    args = p.parse_args()

    start = time.time()
    index, how = rag.load_or_build_index(args.doc, max_words=args.max_words)
    print(f"Index {how}: {len(index['chunks'])} chunks from {args.doc} "
          f"({time.time() - start:.1f}s, embeddings: {index['embed_model']})")
    print(f"Answer model: {MODEL}. Ask anything, or /test, /sources, /quit.\n")

    show_sources = True
    while True:
        q = input("You: ").strip()
        if not q:
            continue
        if q == "/quit":
            break
        if q == "/test":
            run_tests(index, args.k, args.min_score)
            continue
        if q == "/sources":
            show_sources = not show_sources
            print(f"(sources {'shown' if show_sources else 'hidden'})\n")
            continue

        hits = rag.search(index, q, args.k)
        if show_sources:
            show_hits(hits, args.min_score)

        print("Bot: ", end="", flush=True)
        if hits[0][0] < args.min_score:
            print(f"{rag.NOT_FOUND}  (best score {hits[0][0]:.3f} < {args.min_score}, LLM not called)")
        else:
            rag.answer(q, index, k=args.k, min_score=args.min_score, stream=True, hits=hits)
        print()


if __name__ == "__main__":
    main()
