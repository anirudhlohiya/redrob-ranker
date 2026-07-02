"""Turn a raw candidate JSON record into structured features for scoring."""
from datetime import date, datetime
from src import jd_config as cfg


def _lower(s):
    return (s or "").lower()


def candidate_full_text(cand):
    """All free-text fields concatenated, for keyword & TF-IDF matching."""
    profile = cand.get("profile") or {}
    parts = [
        profile.get("headline", ""),
        profile.get("summary", ""),
        profile.get("current_title", ""),
    ]
    for job in cand.get("career_history", []):
        parts.append(job.get("title", ""))
        parts.append(job.get("description", ""))
    for sk in cand.get("skills", []):
        parts.append(sk.get("name", ""))
    return " ".join(p for p in parts if p)


def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def keyword_hit_count(text_lower, keywords):
    return sum(1 for kw in keywords if kw in text_lower)


def months_with_keyword_evidence(cand, keywords):
    """Sum duration_months of career_history entries whose description/title
    contains any of the given keywords."""
    total = 0
    for job in cand.get("career_history", []):
        blob = _lower(job.get("title", "") + " " + job.get("description", ""))
        if any(kw in blob for kw in keywords):
            total += job.get("duration_months", 0) or 0
    return total


def location_fit(cand):
    loc = _lower((cand.get("profile") or {}).get("location", ""))
    country = _lower((cand.get("profile") or {}).get("country", ""))
    willing = cand.get("redrob_signals", {}).get("willing_to_relocate", False)
    if country and country != "india":
        return 0.3 if willing else 0.05  # JD: outside India is case-by-case, no visa sponsorship
    if any(p in loc for p in cfg.PREFERRED_LOCATIONS):
        return 1.0
    if any(w in loc for w in cfg.WELCOME_LOCATIONS):
        return 0.9
    return 0.6 if willing else 0.35


def consulting_only_career(cand):
    companies = [_lower(j.get("company", "")) for j in cand.get("career_history", [])]
    if not companies:
        return False
    return all(any(cf in c for cf in cfg.CONSULTING_FIRMS) for c in companies)


def research_only_career(cand):
    text = _lower(candidate_full_text(cand))
    has_research_signal = any(kw in text for kw in cfg.RESEARCH_ONLY_KEYWORDS)
    has_production_signal = any(kw in text for kw in cfg.PRODUCTION_EVIDENCE_KEYWORDS)
    return has_research_signal and not has_production_signal


def cv_speech_only_misfit(cand):
    text = _lower(candidate_full_text(cand))
    cv_hits = keyword_hit_count(text, cfg.CV_SPEECH_ROBOTICS_KEYWORDS)
    nlp_hits = keyword_hit_count(text, cfg.NLP_IR_KEYWORDS)
    return cv_hits >= 3 and nlp_hits == 0


def recent_langchain_only(cand):
    text = _lower(candidate_full_text(cand))
    has_framework_kw = any(kw in text for kw in cfg.FRAMEWORK_ENTHUSIAST_KEYWORDS)
    if not has_framework_kw:
        return False
    pre_llm_months = months_with_keyword_evidence(cand, cfg.PRE_LLM_ML_EVIDENCE_KEYWORDS)
    return pre_llm_months < 12  # no substantial pre-LLM-era production ML evidence


def tech_lead_not_coding(cand):
    title = _lower((cand.get("profile") or {}).get("current_title", ""))
    current_job = next((j for j in cand.get("career_history", []) if j.get("is_current")), None)
    if not current_job:
        return False
    tenure = current_job.get("duration_months", 0) or 0
    if tenure <= 18:
        return False
    if not any(w in title for w in cfg.NON_CODING_TITLE_WORDS):
        return False
    desc = _lower(current_job.get("description", ""))
    return not any(kw in desc for kw in cfg.CODING_EVIDENCE_KEYWORDS)


def title_chaser(cand):
    jobs = sorted(cand.get("career_history", []), key=lambda j: j.get("start_date") or "")
    short_senior_hops = 0
    for j in jobs:
        title = _lower(j.get("title", ""))
        dur = j.get("duration_months", 0) or 0
        if dur < 18 and any(w in title for w in cfg.SENIOR_TITLE_WORDS):
            short_senior_hops += 1
    return short_senior_hops >= 2


def availability_multiplier(cand):
    sig = cand.get("redrob_signals", {})
    m = 1.0
    if not sig.get("open_to_work_flag", False):
        m *= 0.75
    last_active = _parse_date(sig.get("last_active_date"))
    if last_active:
        days_inactive = (date(2026, 7, 2) - last_active).days
        if days_inactive > 180:
            m *= 0.5
        elif days_inactive > 90:
            m *= 0.75
        elif days_inactive > 30:
            m *= 0.9
    rr = sig.get("recruiter_response_rate", 0.5)
    m *= 0.6 + 0.4 * min(max(rr, 0), 1)  # scales 0.6x - 1.0x
    icr = sig.get("interview_completion_rate", 0.7)
    m *= 0.8 + 0.2 * min(max(icr, 0), 1)
    notice = sig.get("notice_period_days", 60)
    if notice <= cfg.MAX_NOTICE_DAYS_PREFERRED:
        m *= 1.05
    elif notice > 90:
        m *= 0.9
    return round(m, 4)


def honeypot_flags(cand):
    """Conservative logical-impossibility checks. Returns list of reasons."""
    flags = []
    prof = cand.get("profile", {})
    jobs = cand.get("career_history", [])
    yoe = prof.get("years_of_experience", 0) or 0

    # 1. Multiple simultaneous "is_current" roles
    if sum(1 for j in jobs if j.get("is_current")) > 1:
        flags.append("multiple concurrent current roles")

    # 2. Overlapping employment periods across different companies
    intervals = []
    for j in jobs:
        s = _parse_date(j.get("start_date"))
        e = _parse_date(j.get("end_date")) or date(2026, 7, 2)
        if s:
            intervals.append((s, e))
    intervals.sort()
    for i in range(1, len(intervals)):
        if intervals[i][0] < intervals[i - 1][1]:
            overlap_days = (intervals[i - 1][1] - intervals[i][0]).days
            if overlap_days > 45:  # allow small transition overlaps
                flags.append("overlapping employment dates")
                break

    # 3. Total career_history duration wildly exceeds stated years_of_experience
    total_months = sum(j.get("duration_months", 0) or 0 for j in jobs)
    if yoe > 0 and total_months > (yoe * 12 + 24):
        flags.append("career history duration far exceeds stated YOE")

    # 4. Education end_year before start_year, or degree completed before age ~21 plausible start
    for edu in cand.get("education", []):
        sy, ey = edu.get("start_year"), edu.get("end_year")
        if sy and ey and ey < sy:
            flags.append("education end_year before start_year")

    # 5. Skill duration_months exceeds total plausible working months (yoe*12 + 24 buffer for pre-YOE learning)
    for sk in cand.get("skills", []):
        d = sk.get("duration_months", 0) or 0
        if yoe > 0 and d > (yoe * 12 + 36):
            flags.append(f"skill '{sk.get('name')}' duration exceeds plausible career length")
            break

    return flags
