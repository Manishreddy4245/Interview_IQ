"""
Deterministic Skill Gap Prioritization Engine for InterviewIQ Module 04.

Connects target-role benchmarks and four-tier resume skill-gap evaluations
to interview question generation, ordering competencies by validation urgency.
"""
from typing import Dict, List, Optional, Set
from pydantic import BaseModel, Field

from app.schemas.resume import (
    ResumeAnalysisResult,
    SkillEvidenceCategory,
    SkillEvidenceItem,
    TargetRoleBenchmark,
    RoleBenchmarkCompetency,
)
from app.services.skill_normalizer import (
    canonical_skill_key,
    normalize_skill_name,
    skills_match,
)


class PrioritizedGapItem(BaseModel):
    """Structured representation of a skill gap prioritized for interview validation."""
    skill_name: str
    normalized_skill: str
    priority_tier: int = Field(
        ...,
        ge=1,
        le=5,
        description=(
            "1: Core role competency requiring validation; "
            "2: Skill mentioned without sufficient evidence; "
            "3: Skill not demonstrated in resume but expected for role; "
            "4: Other competency requiring interview validation; "
            "5: Demonstrated baseline competency"
        ),
    )
    priority_rank: int = Field(..., ge=1, description="Sequential priority rank (1-indexed)")
    priority_reason: str = Field(..., description="Evidence-based rationale for prioritization")
    category: SkillEvidenceCategory
    importance: str = Field(default="Core", description="'Core', 'Recommended', 'Advanced', or 'Not Specified'")
    requires_interview_validation: bool = Field(default=True)
    is_expected_for_role: bool = Field(default=False)
    evidence: str = Field(default="")
    source_excerpt: Optional[str] = None
    relevance_to_role: str = Field(default="")


def prioritize_skill_gaps(
    analysis: ResumeAnalysisResult,
    max_count: Optional[int] = None,
) -> List[PrioritizedGapItem]:
    """
    Deterministically prioritizes skill gaps for interview question generation.

    Prioritization Order:
    1. Core role competencies requiring validation (Core expected + needs validation or ungrounded).
    2. Skills mentioned without sufficient evidence (INSUFFICIENTLY_EVIDENCED).
    3. Skills not demonstrated in the analyzed resume but expected for the role (NOT_DEMONSTRATED + expected).
    4. Other relevant competencies that require further validation (Recommended/Advanced or candidate claims).
    5. Demonstrated baseline skills (for technical depth probing when needed).

    Rules:
    - Never equates 'Not Demonstrated in Resume' with candidate inability.
    - Never treats a bare mention as proof of proficiency.
    - Preserves independent requires_interview_validation flag.
    - Deduplicates by normalized skill using canonical matching.
    - Substring collisions (Java vs JavaScript, C vs C++, psql vs PostgreSQL) remain distinct.
    """
    if not analysis.skill_evaluations:
        return []

    # Map benchmark expected competencies for quick importance lookup
    benchmark_map: Dict[str, RoleBenchmarkCompetency] = {}
    if analysis.target_role_benchmark and analysis.target_role_benchmark.expected_competencies:
        for comp in analysis.target_role_benchmark.expected_competencies:
            c_key = canonical_skill_key(comp.skill_name)
            benchmark_map[c_key] = comp

    candidate_items: List[dict] = []

    for item in analysis.skill_evaluations:
        norm_skill = item.normalized_skill or normalize_skill_name(item.skill_name)
        c_key = canonical_skill_key(norm_skill)

        # Look up matching benchmark competency
        comp = benchmark_map.get(c_key)
        if not comp:
            for b_key, b_comp in benchmark_map.items():
                if skills_match(norm_skill, b_comp.skill_name):
                    comp = b_comp
                    break

        importance_raw = comp.importance if comp else ("Core" if item.is_expected_for_role else "Not Specified")
        importance_lower = importance_raw.lower()

        is_core = importance_lower in ("core", "required") or (
            item.is_expected_for_role and importance_lower not in ("recommended", "advanced", "optional")
        )
        is_recommended = importance_lower in ("recommended", "expected")
        is_advanced = importance_lower in ("advanced", "nice-to-have")

        # Determine Priority Tier (1 to 5)
        # Tier 1: Core role competencies requiring validation
        if is_core and (
            item.category == SkillEvidenceCategory.REQUIRES_VALIDATION
            or (item.requires_interview_validation and item.category not in (SkillEvidenceCategory.INSUFFICIENTLY_EVIDENCED, SkillEvidenceCategory.NOT_DEMONSTRATED))
        ):
            tier = 1
            reason = f"Core expected competency for {analysis.target_role} requiring live interview validation."
        # Tier 2: Skills mentioned without sufficient evidence
        elif item.category == SkillEvidenceCategory.INSUFFICIENTLY_EVIDENCED:
            tier = 2
            reason = "Skill appears in resume without sufficient project or practical context to substantiate proficiency."
        # Tier 3: Skills not demonstrated in the analyzed resume but expected for the role
        elif item.category == SkillEvidenceCategory.NOT_DEMONSTRATED and item.is_expected_for_role:
            tier = 3
            reason = (
                f"Expected competency for {analysis.target_role} not evidenced in resume; "
                "interview assessment provides candidate opportunity to demonstrate practical capability."
            )
        # Tier 4: Other relevant competencies that require further validation (e.g. Recommended/Advanced)
        elif item.requires_interview_validation or item.category == SkillEvidenceCategory.REQUIRES_VALIDATION:
            tier = 4
            reason = "Competency where resume text alone cannot establish practical depth; live assessment recommended."
        # Tier 5: Baseline demonstrated competencies
        else:
            tier = 5
            reason = "Demonstrated competency in resume text; suitable for validating advanced depth or architecture."

        # Importance weight for secondary sorting (Core = 0, Recommended = 1, Advanced = 2, Other = 3)
        if is_core:
            imp_weight = 0
        elif is_recommended:
            imp_weight = 1
        elif is_advanced:
            imp_weight = 2
        else:
            imp_weight = 3

        # Grounding weight (prefer verified source excerpts over ungrounded claims within the same tier)
        grounding_weight = 0 if item.is_source_grounded else 1

        candidate_items.append({
            "item": item,
            "norm_skill": norm_skill,
            "canonical_key": c_key,
            "tier": tier,
            "imp_weight": imp_weight,
            "grounding_weight": grounding_weight,
            "importance": importance_raw,
            "reason": reason,
        })

    # Sort deterministically
    candidate_items.sort(
        key=lambda x: (
            x["tier"],
            x["imp_weight"],
            x["grounding_weight"],
            x["norm_skill"].lower(),
        )
    )

    # Deduplicate by canonical normalized skill key
    prioritized: List[PrioritizedGapItem] = []
    seen_canonical_keys: Set[str] = set()

    for entry in candidate_items:
        c_key = entry["canonical_key"]
        if c_key in seen_canonical_keys:
            continue
        seen_canonical_keys.add(c_key)

        it: SkillEvidenceItem = entry["item"]
        rank = len(prioritized) + 1

        prioritized.append(
            PrioritizedGapItem(
                skill_name=it.skill_name,
                normalized_skill=entry["norm_skill"],
                priority_tier=entry["tier"],
                priority_rank=rank,
                priority_reason=entry["reason"],
                category=it.category,
                importance=entry["importance"],
                requires_interview_validation=it.requires_interview_validation,
                is_expected_for_role=it.is_expected_for_role,
                evidence=it.evidence,
                source_excerpt=it.source_excerpt,
                relevance_to_role=it.relevance_to_role,
            )
        )

        if max_count and len(prioritized) >= max_count:
            break

    return prioritized
