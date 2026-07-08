# Redrob Candidate Ranker

Ranks candidates from the 100K-candidate pool against the "Senior AI
Engineer — Founding Team" JD the way a strong recruiter would: by
reasoning about actual fit, not by counting skill keywords.



## Why this beats keyword matching

The JD itself calls out the trap: a candidate whose skills section lists
every AI keyword but whose title is "Marketing Manager" is not a fit; a
candidate who never uses the words "RAG" or "Pinecone" but clearly built
a recommendation system at a product company *is*. So the pipeline does
three things a keyword filter can't:

1. **Encodes the JD's own stated rubric as rules** — the JD explicitly
   lists its disqualifiers (pure-research-only, consulting-only career,
   CV/speech-only, tech-lead-not-coding, recent-LangChain-only) and its
   must-haves (production embeddings/retrieval, production vector-DB/hybrid
   search, evaluation-framework experience). We extract these as
   structured signals from each candidate's `career_history` and `skills`,
   not just their skills list.
2. **Adds a semantic-similarity layer** (TF-IDF + LSA/TruncatedSVD) so
   candidates who describe equivalent work in different language still
   surface, without needing an exact keyword hit.
3. **Weighs behavioral signals as an availability multiplier**, per the
   JD's explicit instruction: a perfect-on-paper candidate who's inactive
   or has a low recruiter-response-rate gets down-weighted, not excluded.

A honeypot gate flags logically-impossible profiles (overlapping
employment, education years that don't add up, career-history duration
that contradicts stated years of experience) and pushes them to the
bottom of the ranking rather than deleting them, so the decision stays
auditable.

## Why TF-IDF/LSA instead of a downloaded embedding model

The challenge's compute constraints are CPU-only and **no network at
ranking time**. A transformer embedding model (sentence-transformers,
BGE, E5, etc.) means bundling and loading a few hundred MB of weights,
which is unnecessary weight for this problem: the JD spells out most of
its fit criteria explicitly, so rule extraction handles the specific,
nameable signals, and TF-IDF/LSA handles the fuzzy semantic overlap
between JD language and candidate language. This keeps the pipeline
fast (~100s for 100K candidates, see Results below), deterministic,
dependency-light, and easy to defend in an interview.

## Architecture

```
JD (hardcoded rubric, src/jd_config.py)          Candidate pool (jsonl.gz)
        │                                                  │
        ▼                                                  ▼
 JD_TEXT_FOR_SEMANTIC_MATCH ──────────► TF-IDF + LSA ◄── candidate_full_text()
        │                                     │                │
        │                              cosine similarity       │
        │                              (semantic_score)         │
        │                                     │                │
        └──────────────► rule_based_fit_score(candidate) ◄──────┘
                          (must-haves, disqualifiers, YOE band,
                           location fit, title-chaser check)
                                     │
                          availability_multiplier(candidate)
                          (open_to_work, recency, response rate,
                           interview completion, notice period)
                                     │
                          honeypot_flags(candidate)
                          (overlapping dates, impossible education
                           years, YOE/history mismatch)
                                     │
                    final_score = (0.55·rule + 0.45·semantic)
                                   × availability × honeypot_gate
                                     │
                                     ▼
                          sort, take top 100, write submission.csv
```

## Run it

```bash
pip install -r requirements.txt

# On the full pool (expects data/candidates.jsonl.gz or .jsonl)
python -m src.rank --input data/candidates.jsonl.gz --output output/submission.csv --top 100

# Quick check on the 50-candidate sample
python -m src.rank --input data/sample_candidates.json --output output/submission_sample.csv --top 20

# Validate format before submitting
python validate_submission.py output/submission.csv
```

## Results (100K-candidate stress test)

- **Runtime:** ~100s end-to-end (load + semantic scoring + rule scoring
  + write), against a 5-minute budget.
- **Peak memory:** ~2.8GB, against a 16GB budget.
- On the 50-candidate sample, the one candidate with genuine production
  recommendation-system experience scored 4x higher than the next-best
  candidate; every "curious professional dabbling in ChatGPT" trap
  profile and every consulting-only-career profile was correctly pushed
  to the bottom half of the ranking rather than the top, unlike the
  provided `sample_submission.csv` reference (which ranks an HR Manager
  #1 on keyword count alone).

## Repo layout

```
src/
  jd_config.py   – JD rubric: disqualifiers, must-haves, keyword lists
  features.py    – per-candidate feature extraction + honeypot checks
  scorer.py      – semantic scoring, rule scoring, final combination
  rank.py        – CLI entrypoint
data/
  candidate_schema.json, sample_candidates.json
output/
  submission.csv – generated ranking (top 100)
```

## Known limitations / next steps

- Rule-based signal extraction relies on career-history free text; a
  learned classifier trained on labeled recruiter judgments would likely
  outperform hand-written keyword rules at scale, but no labeled data was
  provided for this challenge
- `tech_lead_not_coding` and `title_chaser` heuristics are necessarily
  approximate given only structured career_history fields.
- Honeypot detection is conservative by design (catches only clear
  logical impossibilities) to keep the false-positive rate low, per the
  <10% disqualification threshold.
