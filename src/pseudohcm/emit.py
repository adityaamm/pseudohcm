"""File emission — one half of D52.

Contract-shaped files for fast pillar tests. The mock API server is the other half,
and tests what files cannot: a source system behaving badly.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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


# D201 (F29) — A RECRUITING SYSTEM SEPARATE FROM THE HR SYSTEM.
#
# The same requisitions, candidates, applications and stage events, written as a
# second, separate system would hold them: its own keys for every job, position and
# org unit its requisitions name, and its own catalogue of those entries
# (`RecruitingReference`) carrying the codes it publishes. Invented for this harness,
# no vendor's. By default every code is the HR system's exactly, except:
#
#   * `near_codes` jobs whose code is written in a different case and spacing — the
#     product may only PROPOSE these, never link them;
#   * internal applicants carry the HR system's key for an employee (`employee_ref`),
#     and `unknown_employee_refs` of them carry a number no employee has.
#
# Nothing else differs, so once a Master confirms the proposals the product's
# Pillar D figures must equal those from the single-system emission.

RECRUITING_ENTITIES = ("Requisition", "Candidate", "Application", "PipelineStageEvent")


def _ats_key(value: str) -> str:
    from pseudohcm.marking import RESERVED_ID_NAMESPACE as NS

    return (NS + "ats-" + value[len(NS):]) if value.startswith(NS) else "ats-" + value


def _loosened(code: str) -> str:
    return code.lower().replace("-", " ")


def emit_recruiting_system(corpus: Corpus, out: Path, *, near_codes: int = 2,
                           unknown_employee_refs: int = 1) -> dict[str, Any]:
    """Write the recruiting data as a separate system holds it. Returns what was
    varied, so a test can expect exactly that."""
    import hashlib

    from pseudohcm.marking import mark

    out.mkdir(parents=True, exist_ok=True)
    jobs = {j["job_id"]: j for j in corpus.jobs}
    seats = {s["position_id"]: s for s in corpus.positions}
    units = {u["org_unit_id"]: u for u in corpus.org_units}
    named_jobs = sorted({r["job_id"] for r in corpus.requisitions})
    loosened = set(named_jobs[:near_codes])

    requisitions = [{**r, "job_id": _ats_key(r["job_id"]),
                     "position_id": _ats_key(r["position_id"]) if r.get("position_id") else None,
                     "org_unit_id": _ats_key(r["org_unit_id"])} for r in corpus.requisitions]

    start = min((r["valid_from"] for r in corpus.requisitions), default="2000-01-01")
    references = []
    for job_id in named_jobs:
        code = jobs[job_id]["job_code"]
        references.append(mark({
            "reference_id": _ats_key(job_id), "reference_kind": "JOB",
            "code": _loosened(code) if job_id in loosened else code, "title": None,
            "valid_from": start, "valid_to": None}))
    for pos_id in sorted({r["position_id"] for r in corpus.requisitions if r.get("position_id")}):
        references.append(mark({
            "reference_id": _ats_key(pos_id), "reference_kind": "POSITION",
            "code": seats[pos_id]["position_code"], "title": seats[pos_id]["title"],
            "valid_from": start, "valid_to": None}))
    for unit_id in sorted({r["org_unit_id"] for r in corpus.requisitions}):
        references.append(mark({
            "reference_id": _ats_key(unit_id), "reference_kind": "ORG_UNIT",
            "code": units[unit_id]["unit_code"], "title": units[unit_id]["name"],
            "valid_from": start, "valid_to": None}))

    people = sorted(p["person_id"] for p in corpus.people)
    internal = [c for c in corpus.candidates if c["source"] == "INTERNAL"]
    unknown = {c["candidate_id"] for c in internal[:unknown_employee_refs]}
    candidates, linked = [], {}
    for c in corpus.candidates:
        if c["source"] != "INTERNAL" or not people:
            candidates.append(dict(c))
            continue
        if c["candidate_id"] in unknown:
            ref = "per-999999"
        else:
            pick = int(hashlib.sha256(c["candidate_id"].encode()).hexdigest(), 16)
            ref = people[pick % len(people)]
            linked[c["candidate_id"]] = ref
        candidates.append({**c, "employee_ref": ref})

    files = {"Requisition": requisitions, "Candidate": candidates,
             "Application": corpus.applications,
             "PipelineStageEvent": corpus.pipeline_stage_events,
             "RecruitingReference": references}
    for entity, records in files.items():
        (out / f"{entity}.jsonl").write_text(
            "\n".join(json.dumps(r, default=str) for r in records) + "\n", encoding="utf-8")
    return {"near_code_jobs": sorted(loosened), "internal_applicants": len(internal),
            "employee_refs_linkable": linked, "employee_refs_unknown": len(unknown),
            "references": len(references)}
