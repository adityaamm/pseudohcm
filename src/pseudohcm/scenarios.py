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
    # D66. Until this existed, no fixture anywhere in this project had ever produced an
    # involuntary exit. The canonical schema has allowed INVOLUNTARY and END_OF_TERM
    # since migration 001; this harness emitted only REGRETTED and NON_REGRETTED, at
    # random. So every figure was verified against an organisation that only ever grew
    # or drifted downward through ordinary attrition — never one that made a decision
    # to shrink.
    #
    # That gap hid a live defect: regretted share divided by *all* exits, so a year
    # with 300 redundancies reported regretted attrition improving fourfold (D65).
    Scenario("redundancy_programme",
             "A cluster of involuntary exits on one date, with their positions removed",
             "Regretted share is unmoved — it is a share of voluntary exits. The "
             "overall attrition rate rises. The two are never reconciled into one",
             "D65 / Doc 06 §4.3"),
    Scenario("unit_closure",
             "An org unit closed: unit, positions and assignments all end on one date",
             "Headcount falls; the unit disappears from an as-of read after the "
             "closure and remains in an as-of read before it; the as-restated lens "
             "names it as unmappable rather than dropping it silently",
             "D66 / Doc 01C §4"),
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


def _employed_on(corpus: Corpus, when: date) -> list[dict]:
    """People employed on a date, in corpus order so selection is deterministic."""
    return [
        p for p in corpus.people
        if date.fromisoformat(p["hire_date_current"]) <= when
        and (p["exit_date"] is None or date.fromisoformat(p["exit_date"]) > when)
    ]


def _day_after(day: date) -> str:
    """The record window closes the day AFTER the last day worked — D67.

    `exit_date` and `engagement_end` are real-world facts and inclusive; `valid_to` is
    a record boundary and exclusive. Conflating them ends every engagement a day early
    and makes a same-day one impossible to express.
    """
    return (day + timedelta(days=1)).isoformat()


def _in_force(record: dict, when: date) -> bool:
    """Is this row in force on a date — **not** 'is its end date empty'.

    THE DISTINCTION THAT BROKE THE FIRST VERSION OF THESE INJECTORS

    The generator records a person's eventual exit up front, so an assignment for
    somebody leaving in November 2025 already carries `valid_to = 2025-11-07` today.
    Testing `valid_to is None` therefore finds only the people who never leave at all —
    64 of 300 in the first run of the redundancy injector.

    The other 236 would have kept an assignment running until 2025 while their person
    record said they were made redundant in March 2024. A corpus that contradicts
    itself, and one the temporal integrity constraints would have refused.

    Ending a record early is the normal case here: a redundancy **brings forward** an
    exit that was already scheduled. So the question is always "is this in force on the
    date", and the answer is a window test, never a null check.
    """
    starts = date.fromisoformat(record["valid_from"])
    ends = record.get("valid_to")
    if starts > when:
        return False
    return ends is None or date.fromisoformat(ends) > when


def inject_redundancy_programme(corpus: Corpus, *, on: date, count: int) -> dict:
    """A redundancy: `count` people exited involuntarily on one date. D66.

    WHY THIS IS AN INJECTOR AND NOT A GENERATOR PARAMETER

    `generate()` is deterministic and every existing test rests on that — same seed,
    same parameters, byte-identical output. Teaching `generate` to shrink would change
    every corpus that has ever been produced, so de-growth is injected into a corpus
    instead. The base data is untouched and the decline is explicit.

    WHAT A REDUNDANCY IS, IN DATA

    Three things happen together and a fixture that does only the first is not a
    redundancy, it is a mass resignation:

      the people exit, with `exit_class = INVOLUNTARY` — they did not choose
      their assignments close on the same date
      **their positions are ABOLISHED** — a redundancy eliminates the role

    That last one is what separates it from attrition. If the positions stayed open
    the establishment would be unchanged and Pillar D would read the gap as demand.

    `ABOLISHED` is the canonical model's own word — migration 001 permits FILLED,
    VACANT, FROZEN and ABOLISHED. The first draft of this wrote `REMOVED`, which is in
    no enum anywhere and would have been refused by the CHECK constraint on the first
    real ingestion. Inventing a value that reads plausibly is the exact defect this
    project has spent two phases removing.

    Selection is the longest-serving first, deterministically. Real programmes do not
    select that way; this is a fixture and a reproducible rule beats a realistic one
    that cannot be reasoned about.
    """
    # Employed *before* the date, not on it. Nobody is made redundant on their first
    # day, and more to the point a person hired on `on` would get an assignment window
    # of `[on, on)` — zero length, which `assignment_valid_period` refuses because a
    # closed-open interval with equal bounds contains no time.
    #
    # The unit-closure injector had this same fault and it reached CI. Fixed in both,
    # because the two are the same mistake and finding it once should close it twice.
    candidates = sorted(_employed_on(corpus, on),
                        key=lambda p: (p["hire_date_current"], p["person_id"]))
    affected = candidates[:count]
    person_ids = {p["person_id"] for p in affected}

    for person in affected:
        person["exit_date"] = on.isoformat()
        person["exit_class"] = "INVOLUNTARY"

    closed_positions: set[str] = set()
    for assignment in corpus.assignments:
        if assignment["person_id"] in person_ids and _in_force(assignment, on):
            assignment["valid_to"] = _day_after(on)
            closed_positions.add(assignment["position_id"])

    for position in corpus.positions:
        if position["position_id"] in closed_positions and _in_force(position, on):
            position["valid_to"] = _day_after(on)
            position["status"] = "ABOLISHED"

    return {
        "scenario": "redundancy_programme",
        "effective_date": on.isoformat(),
        "people_exited": len(affected),
        "positions_removed": len(closed_positions),
        "exit_class": "INVOLUNTARY",
        "person_ids": sorted(person_ids),
        # What the product must do with it. Asserted by the consuming test rather than
        # described in prose that nobody checks.
        "expected_regretted_share_unmoved": True,
        "expected_attrition_rate_rises": True,
    }


def inject_unit_closure(corpus: Corpus, *, on: date, unit_id: str | None = None) -> dict:
    """An org unit closed on a date — unit, positions, people and assignments. D66.

    The case the as-was / as-restated lens exists for, and one nothing had exercised.
    A unit that closed still held people last year, so an as-of read before the closure
    must still see it, and an as-of read after must not.

    Under the as-restated lens the unit cannot be mapped to anything current, so it is
    **named as excluded** rather than dropped — `LensedRows` carries that, and Doc 01C
    §4 is explicit that silently distributing its people would be fabricating history.

    `unit_id` defaults to the last unit in the corpus, which is a leaf rather than a
    line of business: closing a root would orphan its children and this fixture is
    about closure, not about reparenting.
    """
    if unit_id is None:
        unit_id = corpus.org_units[-1]["org_unit_id"]

    unit = next(u for u in corpus.org_units if u["org_unit_id"] == unit_id)
    unit["valid_to"] = _day_after(on)

    in_unit = {pos["position_id"] for pos in corpus.positions
               if pos["org_unit_id"] == unit_id}
    for position in corpus.positions:
        if position["position_id"] in in_unit and _in_force(position, on):
            position["valid_to"] = _day_after(on)
            position["status"] = "ABOLISHED"

    # People the base corpus hired into this unit AFTER the closure date. The generator
    # spreads hires uniformly across the span and cannot know a unit will close, so it
    # produces joiners for a unit that no longer exists — 24 of them in the first run.
    #
    # They are removed rather than exited: an exit implies employment, and these people
    # were never hired. Leaving them would make the unit's headcount rise after its own
    # closure, which is not a shrinking organisation, it is a broken fixture.
    # Strictly AFTER the closure. Somebody hired on the closure day worked one day and
    # is a legitimate one-day engagement under D67 — `[30 Sept, 1 Oct)`.
    #
    # An earlier version used `>=` here to dodge a zero-length window. That was papering
    # over the real fault, which was writing the exit date straight into `valid_to`:
    # the fix belongs in the mapping, not in deleting the person. D67 makes the
    # boundary hire expressible, so this reverts to the honest predicate.
    never_hired = {
        a["person_id"] for a in corpus.assignments
        if a["position_id"] in in_unit
        and date.fromisoformat(a["valid_from"]) > on
    }
    if never_hired:
        corpus.assignments[:] = [a for a in corpus.assignments
                                 if a["person_id"] not in never_hired]
        corpus.people[:] = [p for p in corpus.people
                            if p["person_id"] not in never_hired]

    displaced: set[str] = set()
    for assignment in corpus.assignments:
        if assignment["position_id"] in in_unit and _in_force(assignment, on):
            assignment["valid_to"] = _day_after(on)
            displaced.add(assignment["person_id"])

    for person in corpus.people:
        if person["person_id"] in displaced and (
                person["exit_date"] is None
                or date.fromisoformat(person["exit_date"]) > on):
            person["exit_date"] = on.isoformat()
            person["exit_class"] = "INVOLUNTARY"

    return {
        "scenario": "unit_closure",
        "effective_date": on.isoformat(),
        "org_unit_id": unit_id,
        "positions_removed": len(in_unit),
        "people_displaced": len(displaced),
        "joiners_removed": len(never_hired),
        "expected_visible_before": True,
        "expected_absent_after": True,
        "expected_named_not_dropped_when_restated": True,
    }
