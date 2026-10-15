"""
Deterministic Resume Evidence Grounding Service.

Verifies claimed verbatim evidence against actual extracted resume text,
distinguishing verified source excerpts from LLM-generated summaries or unverified claims.
"""
import re
from typing import Optional, Tuple

from app.schemas.resume import SkillEvidenceCategory


def normalize_text_for_search(text: Optional[str]) -> str:
    """
    Normalizes text for robust substring and phrase searching:
    - Replaces all newlines, carriage returns, and tabs with single spaces.
    - Strips surrounding whitespace and lowercases.
    - Removes zero-width and non-printable control characters.
    """
    if not text:
        return ""
    # Remove control characters except standard whitespace
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
    # Collapse any sequence of whitespace to a single space
    cleaned = re.sub(r'\s+', ' ', cleaned).strip().lower()
    return cleaned


def extract_matching_excerpt(raw_resume_text: str, search_query: str) -> Optional[str]:
    """
    Finds a verbatim or whitespace-normalized match in the raw resume text
    and extracts a clean snippet with original casing.
    """
    if not raw_resume_text or not search_query:
        return None

    norm_resume = normalize_text_for_search(raw_resume_text)
    norm_query = normalize_text_for_search(search_query)

    if not norm_query or norm_query not in norm_resume:
        return None

    lines = [l.strip() for l in raw_resume_text.splitlines() if l.strip()]
    for line in lines:
        if norm_query in normalize_text_for_search(line):
            return line

    # Fallback to multi-line search if query spans line breaks
    collapsed = " ".join(lines)
    norm_collapsed = normalize_text_for_search(collapsed)
    idx = norm_collapsed.find(norm_query)
    if idx != -1:
        c_start = max(0, idx - 20)
        c_end = min(len(collapsed), idx + len(norm_query) + 20)
        snippet = collapsed[c_start:c_end].strip()
        if c_start > 0:
            snippet = "..." + snippet
        if c_end < len(collapsed):
            snippet = snippet + "..."
        return snippet

    return search_query.strip()


PRACTICAL_ACTION_INDICATORS = {
    "develop", "developed", "developing", "developer",
    "engineer", "engineered", "engineering",
    "architect", "architected", "architecture",
    "build", "built", "building",
    "implement", "implemented", "implementing", "implementation",
    "design", "designed", "designing",
    "deploy", "deployed", "deploying", "deployment",
    "maintain", "maintained", "maintaining",
    "manage", "managed", "managing", "management",
    "scale", "scaled", "scaling", "scalability",
    "optimize", "optimized", "optimizing", "optimization",
    "lead", "led", "leading",
    "create", "created", "creating",
    "configure", "configured", "configuring", "configuration",
    "integrate", "integrated", "integrating", "integration",
    "migrate", "migrated", "migrating", "migration",
    "test", "tested", "testing",
    "refactor", "refactored", "refactoring",
    "automate", "automated", "automating", "automation",
    "monitor", "monitored", "monitoring",
    "year", "years", "production", "system", "service", "services",
    "pipeline", "platform", "cluster", "database", "api", "apis",
    "microservices", "infrastructure"
}

LIST_SECTION_INDICATORS = {
    "skills", "technical skills", "core skills", "technologies",
    "tools", "proficiencies", "frameworks", "languages", "competencies"
}


def has_practical_experience_evidence(text: Optional[str], skill_name: Optional[str] = None) -> bool:
    """
    Evaluates whether text contains practical, experiential context (actions, years,
    architecture, project details) rather than being merely a list or brief mention.
    """
    if not text:
        return False

    norm = normalize_text_for_search(text)
    words = set(re.findall(r'\b[a-z]{3,}\b', norm))

    # Check for presence of practical actions or project indicators
    has_action = bool(words & PRACTICAL_ACTION_INDICATORS)

    # Check if the text indicates years or numerical experience (e.g. "4 years", "5+ yrs")
    has_years = bool(re.search(r'\b\d+\+?\s*(years?|yrs?)\b', norm))

    if has_action or has_years:
        return True

    return False


def find_skill_evidence_in_resume(
    resume_text: str,
    skill_name: str,
) -> Tuple[bool, Optional[str], bool]:
    """
    Deterministically searches the analyzed resume text for a skill name or approved alias.
    Respects strict collision boundaries (e.g. Java != JavaScript, C != C++, psql != PostgreSQL).

    Returns:
    - found: bool (True if the skill appears in the resume text)
    - excerpt: Optional[str] (verbatim line or snippet where skill appears)
    - has_practical_context: bool (True if the context demonstrates practical project experience)
    """
    if not resume_text or not skill_name:
        return False, None, False

    from app.services.skill_normalizer import (
        normalize_skill_name,
        canonical_skill_key,
        CANONICAL_SKILL_MAP,
        DISALLOWED_COLLISIONS,
    )

    clean_skill = normalize_skill_name(skill_name)
    target_key = canonical_skill_key(skill_name)

    # Gather search terms (the skill itself + any canonical alias that maps to it)
    search_terms = {clean_skill.lower(), skill_name.strip().lower()}
    for alias_key, canonical_val in CANONICAL_SKILL_MAP.items():
        if canonical_skill_key(canonical_val) == target_key:
            search_terms.add(alias_key.lower())

    lines = [line.strip() for line in resume_text.splitlines() if line.strip()]

    matched_excerpt: Optional[str] = None
    has_practical = False

    for line in lines:
        norm_line = normalize_text_for_search(line)
        for term in search_terms:
            escaped = re.escape(term)
            pattern = rf'(?:^|[\s,;/()\[\]:])({escaped})(?:$|[\s,;/()\[\]:])'
            if re.search(pattern, norm_line):
                matched_excerpt = line
                if has_practical_experience_evidence(line, skill_name):
                    has_practical = True
                    return True, line, True

    if matched_excerpt:
        return True, matched_excerpt, has_practical

    # Multi-line / collapsed search if not found in isolated single lines
    collapsed = " ".join(lines)
    norm_collapsed = normalize_text_for_search(collapsed)
    for term in search_terms:
        escaped = re.escape(term)
        pattern = rf'(?:^|[\s,;/()\[\]:])({escaped})(?:$|[\s,;/()\[\]:])'
        m = re.search(pattern, norm_collapsed)
        if m:
            snippet = extract_matching_excerpt(resume_text, term) or term
            practical = has_practical_experience_evidence(snippet, skill_name)
            return True, snippet, practical

    return False, None, False


def verify_evidence_grounding(
    resume_text: str,
    evidence: str,
    category: SkillEvidenceCategory,
    skill_name: Optional[str] = None,
) -> Tuple[bool, str, Optional[str], SkillEvidenceCategory]:
    """
    Evaluates evidence text against the candidate's actual resume text.

    Returns:
    - is_source_grounded: bool (True if a verified verbatim excerpt is located in resume text)
    - evidence_type: str ("verbatim_quote", "inferred_summary", or "unverified")
    - source_excerpt: Optional[str] (verbatim matching text if grounded)
    - resolved_category: SkillEvidenceCategory (downgrades ungrounded DEMONSTRATED claims to REQUIRES_VALIDATION)
    """
    if not evidence or not evidence.strip():
        resolved_cat = (
            SkillEvidenceCategory.REQUIRES_VALIDATION
            if category == SkillEvidenceCategory.DEMONSTRATED
            else category
        )
        return False, "unverified", None, resolved_cat

    # If category is "Not demonstrated in resume", evidence explains absence by design
    if category == SkillEvidenceCategory.NOT_DEMONSTRATED:
        return False, "inferred_summary", None, category

    norm_resume = normalize_text_for_search(resume_text)
    norm_evidence = normalize_text_for_search(evidence)
    norm_skill = normalize_text_for_search(skill_name) if skill_name else ""

    # 1. Check for quoted excerpts inside the evidence string
    quotes = re.findall(r'["\']([^"\']{8,})["\']', evidence)
    if quotes:
        for q in quotes:
            norm_q = normalize_text_for_search(q)
            if norm_q and norm_q in norm_resume:
                excerpt = extract_matching_excerpt(resume_text, q) or q
                return True, "verbatim_quote", excerpt, category
        # Quotation marks were provided as a citation, but none matched the source text
        resolved_cat = (
            SkillEvidenceCategory.REQUIRES_VALIDATION
            if category == SkillEvidenceCategory.DEMONSTRATED
            else category
        )
        return False, "unverified", None, resolved_cat

    # 2. Check if the entire evidence string exists in the resume text
    if len(norm_evidence) >= 15 and norm_evidence in norm_resume:
        excerpt = extract_matching_excerpt(resume_text, evidence) or evidence
        return True, "verbatim_quote", excerpt, category

    # 3. Check for continuous multi-word sequence (at least 5 words or >= 25 chars)
    words = norm_evidence.split()
    if len(words) >= 5:
        for i in range(len(words) - 4):
            window = " ".join(words[i:i + 5])
            if len(window) >= 20 and window in norm_resume:
                excerpt = extract_matching_excerpt(resume_text, window) or window
                return True, "verbatim_quote", excerpt, category

    # 4. Check if skill itself is present in the resume text
    skill_in_resume = False
    if norm_skill and norm_skill in norm_resume:
        skill_in_resume = True
    elif skill_name:
        from app.services.skill_normalizer import canonical_skill_key
        c_key = canonical_skill_key(skill_name)
        if c_key and c_key in norm_resume:
            skill_in_resume = True

    # 5. Check if evidence is an analytical summary of absence / brief mention
    summary_indicators = [
        "not mentioned",
        "not demonstrated",
        "without project",
        "without details",
        "only listed",
        "listed under",
        "mentioned but",
        "brief mention",
        "lacks context",
        "requires validation",
        "ambiguous claim",
        "insufficient evidence",
    ]
    is_analytical_summary = any(ind in norm_evidence for ind in summary_indicators)
    if is_analytical_summary:
        return False, "inferred_summary", None, category

    # 6. If claimed category was DEMONSTRATED, but the skill is NOT in the resume at all:
    # Cannot be verified as demonstrated.
    if category == SkillEvidenceCategory.DEMONSTRATED and not skill_in_resume:
        return False, "unverified", None, SkillEvidenceCategory.REQUIRES_VALIDATION

    # 7. If skill is present in resume, but evidence is an LLM paraphrase rather than verbatim quote:
    # Retain category as an inferred summary
    return False, "inferred_summary", None, category


def resolve_deterministic_gap_classification(
    initial_category: SkillEvidenceCategory,
    is_source_grounded: bool,
    evidence_type: str,
    skill_in_resume: bool,
    is_expected_for_role: bool,
    evidence: str,
    skill_name: Optional[str] = None,
) -> Tuple[SkillEvidenceCategory, str, bool]:
    """
    Applies deterministic four-tier classification rules across candidate claims and benchmarks:

    1. Demonstrated in Resume:
       Supported by verifiable source evidence located directly in the candidate's resume text.
    2. Mentioned but Insufficiently Evidenced:
       The skill appears in the resume, but the available text does not sufficiently substantiate
       practical proficiency or project context.
    3. Not Demonstrated in Resume:
       The skill is an expected requirement for the selected target role, but no evidence was found in the resume.
    4. Requires Interview Validation:
       Resume text alone cannot establish practical competency, an ungrounded claim was downgraded,
       or live assessment is needed to confirm depth.

    Returns:
    - final_category: SkillEvidenceCategory
    - classification_rationale: str
    - requires_interview_validation: bool
    """
    # 1. Skill is absent from resume text
    if not skill_in_resume:
        if is_expected_for_role or initial_category == SkillEvidenceCategory.NOT_DEMONSTRATED:
            return (
                SkillEvidenceCategory.NOT_DEMONSTRATED,
                "Expected competency for the target role, but not evidenced in the analyzed resume text. "
                "(Note: Absence from resume does not imply lack of candidate ability).",
                True,
            )
        # Absence when initially claimed as demonstrated must be downgraded
        return (
            SkillEvidenceCategory.REQUIRES_VALIDATION,
            "Skill is not evidenced in the candidate's resume text and requires live interview assessment.",
            True,
        )

    # 2. Skill is present in resume text
    has_practical = has_practical_experience_evidence(evidence, skill_name)

    if initial_category == SkillEvidenceCategory.DEMONSTRATED:
        if evidence_type == "unverified":
            # Fabricated or ungrounded citation cannot qualify as grounded evidence
            return (
                SkillEvidenceCategory.REQUIRES_VALIDATION,
                "Claimed demonstration lacks verifiable source evidence in resume text; requires live interview validation.",
                True,
            )
        elif not has_practical:
            # Skill name appears in resume, but evidence is merely a list or brief mention without practical context
            return (
                SkillEvidenceCategory.INSUFFICIENTLY_EVIDENCED,
                "Skill appears in the resume (e.g. listed under skills or tools), but the available text "
                "does not sufficiently substantiate practical proficiency or project context.",
                True,
            )
        elif is_source_grounded and evidence_type == "verbatim_quote":
            return (
                SkillEvidenceCategory.DEMONSTRATED,
                "Supported by verifiable source evidence extracted directly from candidate resume text.",
                False,
            )
        else:
            # Skill is present in resume text and accompanied by descriptive experience context
            return (
                SkillEvidenceCategory.DEMONSTRATED,
                "Demonstrated in candidate resume text based on described experience and context.",
                False,
            )

    if initial_category == SkillEvidenceCategory.INSUFFICIENTLY_EVIDENCED:
        return (
            SkillEvidenceCategory.INSUFFICIENTLY_EVIDENCED,
            "Skill appears in the resume (e.g. listed under skills or tools), but the available text "
            "does not sufficiently substantiate practical proficiency or project context.",
            True,
        )

    if initial_category == SkillEvidenceCategory.REQUIRES_VALIDATION:
        if is_source_grounded:
            return (
                SkillEvidenceCategory.REQUIRES_VALIDATION,
                "Resume contains grounded source evidence, but practical competency requires live interview validation.",
                True,
            )
        return (
            SkillEvidenceCategory.REQUIRES_VALIDATION,
            "Resume evidence alone cannot establish practical competency; targeted assessment during an interview is required.",
            True,
        )

    if initial_category == SkillEvidenceCategory.NOT_DEMONSTRATED:
        # Since skill_in_resume is True, classifying as NOT_DEMONSTRATED is contradictory
        if has_practical:
            return (
                SkillEvidenceCategory.DEMONSTRATED,
                "Evidenced in resume text; targeted live assessment can confirm practical depth.",
                True,
            )
        return (
            SkillEvidenceCategory.INSUFFICIENTLY_EVIDENCED,
            "Skill is mentioned in the resume text, but available context is brief and requires interview validation.",
            True,
        )

    # Default conservative fallback
    return (
        SkillEvidenceCategory.REQUIRES_VALIDATION,
        "Practical competency cannot be verified from resume text alone and requires live interview assessment.",
        True,
    )
