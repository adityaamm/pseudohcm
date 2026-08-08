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
