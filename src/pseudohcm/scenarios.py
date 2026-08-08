"""Scenario injection — D50.

This is what makes the harness a test fixture rather than decoration. Each scenario
declares an injected condition and the product behaviour that must follow, so the
test suite can assert rather than squint.

Every row here exists because a design decision claimed the software would behave in
a particular way. Document 10 §4.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from pseudohcm.generator import Corpus
from pseudohcm.marking import mark


@dataclass(frozen=True)
class Scenario:
    key: str
    injects: str
    expected: str
    decision: str


CATALOGUE: tuple[Scenario, ...] = (
    Scenario("backdated_correction",
             "An assignment recorded six weeks after it took effect",
             "A bi-temporal read returns two different correct answers for one report date",
             "D7 / Doc 01B"),
    Scenario("vacant_critical_position",
             "A critical position with no incumbent",
             "Position exists with no Person; latent demand surfaces in Pillar D unsummed",
             "D47 / Doc 03A §3.2"),
    Scenario("contingent_population",
             "A contingent workforce alongside employees",
             "Headcount basis declaration correct; contingent never folded into an employee total",
             "D2 / D30"),
    Scenario("small_unit",
             "A unit below the anonymity threshold",
             "Person-adjacent figures suppressed; unit rolls into its parent",
             "D15"),
    Scenario("marked_record_rejection",
             "Any harness record presented to production ingestion",
             "Hard rejection with an alert, not a warning",
             "Gate 7"),
)


def inject_backdated_correction(corpus: Corpus) -> dict:
    """The Jane scenario from Document 01B, made concrete.

    Moved 1 March 2021. Recorded 14 April 2021. A report run on 20 March 2021 said
    one thing then and says another now. Both correct.
    """
    moved = date(2021, 3, 1)
    recorded = datetime(2021, 4, 14, tzinfo=timezone.utc)
    aid = "asg-jane-0001"

    belief_before = mark({
        "assignment_id": aid, "person_id": "per-jane", "position_id": "pos-eng-001",
        "assignment_type": "PRIMARY", "fte": 1.0, "manager_person_id": None,
        "valid_from": date(2019, 1, 1).isoformat(), "valid_to": None,
        "tx_from": datetime(2019, 1, 1, tzinfo=timezone.utc).isoformat(),
        "tx_to": recorded.isoformat(), "correction_of": None,
        "prov": {"src_system": "pseudohcm", "src_object": "assignments",
                 "sync_id": "sync-0001", "sync_at": recorded.isoformat(),
                 "derived": False, "derivation": None, "confidence": None},
    })
    belief_after = mark({
        **belief_before,
        "valid_to": moved.isoformat(),
        "tx_from": recorded.isoformat(), "tx_to": None,
        "correction_of": aid,
    })
    corpus.assignments.extend([belief_before, belief_after])
    return {
        "scenario": "backdated_correction",
        "assignment_id": aid,
        "report_date": date(2021, 3, 20).isoformat(),
        "expected_as_believed_then": "assignment open",
        "expected_as_known_today": "assignment ended 2021-03-01",
        "gap_days": (recorded.date() - moved).days,
    }
