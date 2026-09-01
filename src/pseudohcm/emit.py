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
    "RoleRequiredTerm": "role_required_terms",
    "RatingScale": "rating_scales", "PerformanceCycle": "performance_cycles",
    "PerformanceEvent": "performance_events",
    "RoleInteraction": "role_interactions", "RoleRequirement": "role_requirements",
}


def emit(corpus: Corpus, out: Path) -> dict[str, int]:
    out.mkdir(parents=True, exist_ok=True)
    written: dict[str, int] = {}
    for entity, attribute in ENTITY_FILES.items():
        records = getattr(corpus, attribute)
        (out / f"{entity}.jsonl").write_text(
            "\n".join(json.dumps(r, default=str) for r in records) + "\n", encoding="utf-8"
        )
        written[entity] = len(records)
    return written
