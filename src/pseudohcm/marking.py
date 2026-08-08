"""Marking every emitted record. Gate 7 — the poison pill.

Gates 1 to 6 prevent this harness reaching production. This assumes they all failed,
and ensures the product refuses the data anyway.
"""
from contract.markers import (
    RESERVED_ID_NAMESPACE,
    SYNTHETIC_MARKER_FIELD,
    SYNTHETIC_MARKER_VALUE,
)


def mark(record: dict) -> dict:
    """Stamp a record so production ingestion will reject it."""
    marked = dict(record)
    marked[SYNTHETIC_MARKER_FIELD] = SYNTHETIC_MARKER_VALUE
    for key, value in list(marked.items()):
        if (key.endswith("_id") or key == "id") and isinstance(value, str):
            if not value.startswith(RESERVED_ID_NAMESPACE):
                marked[key] = RESERVED_ID_NAMESPACE + value
    return marked
