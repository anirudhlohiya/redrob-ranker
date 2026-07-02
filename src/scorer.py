"""
Hybrid scoring: TF-IDF/LSA semantic similarity (local, no network, no
downloaded model weights) + rule-based fit score derived from the JD
rubric + a behavioral-availability multiplier + a honeypot gate.

Why TF-IDF/LSA instead of a downloaded embedding model: the compute
constraints are CPU-only / no network at ranking time. A transformer
embedding model requires bundling ~100-500MB of weights in the repo and
loading them, which is heavier than this problem needs. The JD's fit
criteria are highly rule-derivable (the JD spells out most of them
explicitly), so we let TF-IDF/LSA handle the "fuzzy" semantic overlap
between JD language and candidate language, and let explicit rules
handle the specific disqualifiers/must-haves the JD calls out by name.
This keeps the pipeline fast, deterministic, dependency-light, and easy
to explain in the interview.
"""
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.metrics.pairwise import cosine_similarity

from src import jd_config as cfg
from src import features as feat


def build_semantic_scores(candidate_texts, jd_text, n_components=64):
    """Return cosine similarity of each candidate to the JD in LSA space."""
    corpus = [jd_text] + candidate_texts
    vectorizer = TfidfVectorizer(
        max_features=8000, ngram_range=(1, 2), stop_words="english", min_df=3,
        max_df=0.6, sublinear_tf=True,
    )
    tfidf = vectorizer.fit_transform(corpus)
    n_components = min(n_components, tfidf.shape[1] - 1, tfidf.shape[0] - 1)
    svd = TruncatedSVD(n_components=max(n_components, 2), random_state=42)
    lsa = svd.fit_transform(tfidf)
    jd_vec = lsa[0:1]
    cand_vecs = lsa[1:]
    sims = cosine_similarity(jd_vec, cand_vecs)[0]
    # normalize 0-1
    sims = (sims - sims.min()) / (sims.max() - sims.min() + 1e-9)
    return sims


def rule_based_fit_score(cand):
    """Returns (score in [0,1], list of (label, weight_applied) for reasoning)."""
    text = feat.candidate_full_text(cand).lower()
    notes = []
    score = 0.0
    max_score = 0.0

    # Hard disqualifiers -> heavy penalty, not necessarily zero (recruiter still sees them, ranked low)
    disqualified = False
    if feat.consulting_only_career(cand):
        disqualified = True
        notes.append("entire career at a consulting firm (JD disqualifier)")
    if feat.research_only_career(cand):
        disqualified = True
        notes.append("pure-research background, no production evidence (JD disqualifier)")
    if feat.cv_speech_only_misfit(cand):
        disqualified = True
        notes.append("CV/speech/robotics background without NLP/IR exposure (JD disqualifier)")
    if feat.recent_langchain_only(cand):
        disqualified = True
        notes.append("AI experience limited to recent LangChain/API usage, no pre-LLM ML depth (JD disqualifier)")

    # Must-have signals
    prod_ml_hits = feat.keyword_hit_count(text, cfg.PRODUCTION_ML_KEYWORDS)
    max_score += 40
    score += min(prod_ml_hits, 5) / 5 * 40
    if prod_ml_hits:
        notes.append(f"{prod_ml_hits} production ML/retrieval keyword(s) in career history")

    eval_hits = feat.keyword_hit_count(text, cfg.EVAL_FRAMEWORK_KEYWORDS)
    max_score += 15
    score += min(eval_hits, 2) / 2 * 15
    if eval_hits:
        notes.append("evaluation-framework experience (NDCG/MRR/A-B testing)")

    python_signal = "python" in text
    max_score += 5
    score += 5 if python_signal else 0

    # Nice-to-haves
    nice_hits = feat.keyword_hit_count(text, cfg.NICE_TO_HAVE_KEYWORDS)
    max_score += 10
    score += min(nice_hits, 3) / 3 * 10

    # YOE band fit
    yoe = (cand.get("profile") or {}).get("years_of_experience", 0) or 0
    max_score += 15
    if cfg.IDEAL_YOE_MIN <= yoe <= cfg.IDEAL_YOE_MAX:
        score += 15
    elif cfg.IDEAL_YOE_SOFT_MIN <= yoe <= cfg.IDEAL_YOE_SOFT_MAX:
        score += 8
    else:
        score += 0

    # Location fit
    loc_fit = feat.location_fit(cand)
    max_score += 10
    score += loc_fit * 10

    # Title-chaser / tech-lead-not-coding: soft penalties
    if feat.title_chaser(cand):
        score -= 8
        notes.append("title-hopping pattern (short senior-title stints)")
    if feat.tech_lead_not_coding(cand):
        score -= 8
        notes.append("senior/lead title with no recent hands-on coding evidence")

    score = max(score, 0)
    normalized = score / max_score if max_score else 0
    if disqualified:
        normalized *= 0.15  # keep visible but push to bottom of ranking, not deleted

    return normalized, notes, disqualified


def score_candidate(cand, semantic_score):
    rule_score, notes, disqualified = rule_based_fit_score(cand)
    avail_mult = feat.availability_multiplier(cand)
    honeypot = feat.honeypot_flags(cand)

    base = 0.55 * rule_score + 0.45 * semantic_score
    final = base * avail_mult
    if honeypot:
        final *= 0.05  # gate honeypots to the bottom without hard-deleting (defensible, auditable)

    return {
        "final_score": final,
        "rule_score": rule_score,
        "semantic_score": semantic_score,
        "availability_multiplier": avail_mult,
        "notes": notes,
        "disqualified": disqualified,
        "honeypot_flags": honeypot,
    }


def build_reasoning(cand, result):
    prof = cand.get("profile") or {}
    yoe = prof.get("years_of_experience", 0)
    title = prof.get("current_title", "")
    rr = cand.get("redrob_signals", {}).get("recruiter_response_rate", None)
    bits = [f"{title} with {yoe} yrs"]
    if result["notes"]:
        bits.append(result["notes"][0])
    if rr is not None:
        bits.append(f"response rate {rr:.2f}")
    if result["honeypot_flags"]:
        bits.append(f"FLAGGED: {result['honeypot_flags'][0]}")
    reasoning = "; ".join(bits)
    return reasoning[:280]
