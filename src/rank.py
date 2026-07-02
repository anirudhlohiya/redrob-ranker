"""
Redrob Hackathon — Intelligent Candidate Discovery & Ranking
Usage:
    python -m src.rank --input data/candidates.jsonl.gz --output output/submission.csv --top 100
    python -m src.rank --input data/sample_candidates.json --output output/submission_sample.csv --top 20
"""
import argparse
import csv
import gzip
import json
import sys
import time

from src import jd_config as cfg
from src import features as feat
from src import scorer


def load_candidates(path):
    if path.endswith(".json"):
        with open(path, "r") as f:
            data = json.load(f)
        for row in data:
            yield row
        return

    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--top", type=int, default=100)
    args = ap.parse_args()

    t0 = time.time()
    print(f"Loading candidates from {args.input} ...", file=sys.stderr)
    candidates = list(load_candidates(args.input))
    print(f"Loaded {len(candidates)} candidates in {time.time()-t0:.1f}s", file=sys.stderr)

    t1 = time.time()
    texts = [feat.candidate_full_text(c) for c in candidates]
    semantic_scores = scorer.build_semantic_scores(texts, cfg.JD_TEXT_FOR_SEMANTIC_MATCH)
    print(f"Computed semantic scores in {time.time()-t1:.1f}s", file=sys.stderr)

    t2 = time.time()
    results = []
    skipped = 0
    for cand, sem in zip(candidates, semantic_scores):
        try:
            cid = cand["candidate_id"]
            r = scorer.score_candidate(cand, sem)
            reasoning = scorer.build_reasoning(cand, r)
            results.append((cid, r["final_score"], reasoning))
        except Exception as e:
            skipped += 1
            print(f"  skipped malformed record ({e}): {cand.get('candidate_id', '?')}", file=sys.stderr)
    if skipped:
        print(f"Skipped {skipped} malformed record(s)", file=sys.stderr)
    print(f"Scored all candidates in {time.time()-t2:.1f}s", file=sys.stderr)

    if not results:
        print("No candidates scored — nothing to write.", file=sys.stderr)
        sys.exit(1)

    max_s = max((s for _, s, _ in results), default=1.0) or 1.0
    # round FIRST, then sort — the tie-break must be computed on the values
    # actually written to the CSV, not the raw pre-rounding scores, otherwise
    # two candidates that round to the same displayed score can still end up
    # in the wrong order relative to the validator's candidate_id tie-break rule.
    rounded = [
        (cid, round(min(s / max_s, 1.0), 4), reasoning) for cid, s, reasoning in results
    ]
    rounded.sort(key=lambda x: (-x[1], x[0]))  # score desc, then candidate_id asc for ties
    top = rounded[: args.top]

    with open(args.output, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        for i, (cid, s, reasoning) in enumerate(top, start=1):
            writer.writerow([cid, i, s, reasoning])

    print(f"Wrote top {len(top)} candidates to {args.output}", file=sys.stderr)
    print(f"Total time: {time.time()-t0:.1f}s", file=sys.stderr)


if __name__ == "__main__":
    main()