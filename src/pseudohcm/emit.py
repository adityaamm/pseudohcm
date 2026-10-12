"""File emission — one half of D52.

Contract-shaped files for fast pillar tests. The mock API server is the other half,
and tests what files cannot: a source system behaving badly.
"""
from __future__ import annotations

import json
from pathlib import Path

from pseudohcm.generator import Corpus

ENTITY_FILES = {
    "OrgUnit": "org_units", "Job": "jobs", "Position": "positions",
    "Person": "people", "Assignment": "assignments",
    # P2.6. Written even when empty, which is deliberate: an absent file and an empty
    # one say different things to whoever is loading them. Absent reads as "this
    # harness does not know about ratings"; empty reads as "it does, and this run
    # produced none" — which is the true statement when `rating_cycles` is 0.
    # P2.7. The skills vocabulary. `CanonicalSkill` rows are SYNTHETIC throughout —
    # synthetic concept ids and an attribution saying so — because embedding real
    # O*NET or ESCO content in this harness would put third-party material here under
    # a licence the harness cannot honour.
    "CustomerSkillTerm": "customer_skill_terms",
    "CanonicalSkill": "canonical_skills",
    "TaxonomyLink": "taxonomy_links",
    "SkillAssertion": "skill_assertions",
    # D129. Emitted because an assertion cites it, and a proficiency with no
    # scale is uninterpretable — the database says so and refuses the row.
    "ProficiencyScale": "proficiency_scales",
    "RoleRequiredTerm": "role_required_terms",
    "RatingScale": "rating_scales", "PerformanceCycle": "performance_cycles",
    "PerformanceEvent": "performance_events",
    "RoleInteraction": "role_interactions", "RoleRequirement": "role_requirements",
    # D174. Empty unless the corpus was generated with `succession` on.
    "SuccessionNomination": "succession_nominations",
    # D175. Empty unless generated with `leadership_scores` on.
    "LeadershipScore": "leadership_scores",
    # D185. The recruiting module. Empty unless generated with `talent_acquisition` on;
    # read only by a talent_acquisition profile, never by the core HR one.
    "Requisition": "requisitions", "Candidate": "candidates",
    "Application": "applications", "PipelineStageEvent": "pipeline_stage_events",
}


# D198 (F4) — THE EMULATED HR SYSTEM'S OWN FIELD NAMES.
#
# Every emulator wrote canonical column names, so a profile's field map renamed nothing
# and was tested against a source that did not need it. With `source_names=True` this
# harness writes these fields under its OWN names — invented for this emulator, no
# vendor's — and the example HCM profile is written to them, so the mapping layer does
# real work. Canonical name → the name this system sends. The temporal fields
# (`valid_from`, `tx_from`) keep their names: the example profile declares them as the
# source names (D123), and `test_temporal_mapping` drives a source that renames them.
SOURCE_NAMES: dict[str, dict[str, str]] = {
    "Person": {"display_ref": "worker_reference", "employment_type": "employment_category",
               "hire_date_original": "original_hire_date",
               "hire_date_current": "continuous_service_date"},
    "Position": {"title": "position_title", "status": "position_status"},
    "OrgUnit": {"name": "org_name", "parent_unit_id": "parent_org"},
    "Assignment": {"assignment_type": "assignment_category", "fte": "fte_value"},
    "RatingScale": {"label": "scale_label", "point_count": "scale_points"},
    "PerformanceCycle": {"label": "cycle_label"},
    "PerformanceEvent": {"rating_rank": "normalised_rank"},
    "RoleInteraction": {"dependency_type": "relationship_type"},
    "CustomerSkillTerm": {"label": "term_label"},
    "SkillAssertion": {"proficiency": "proficiency_level",
                       "evidence_type": "evidence_category"},
    "RoleRequirement": {"description_text": "job_description",
                        "description_quality": "description_assessment"},
}


def _source_shaped(entity: str, record: dict) -> dict:
    names = SOURCE_NAMES.get(entity, {})
    return {names.get(k, k): v for k, v in record.items()}


def emit(corpus: Corpus, out: Path, *, source_names: bool = False) -> dict[str, int]:
    out.mkdir(parents=True, exist_ok=True)
    written: dict[str, int] = {}
    for entity, attribute in ENTITY_FILES.items():
        records = getattr(corpus, attribute)
        if source_names:
            records = [_source_shaped(entity, r) for r in records]
        (out / f"{entity}.jsonl").write_text(
            "\n".join(json.dumps(r, default=str) for r in records) + "\n", encoding="utf-8"
        )
        written[entity] = len(records)
    return written
