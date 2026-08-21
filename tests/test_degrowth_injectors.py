"""The de-growth injectors produce a corpus that does not contradict itself — D66.

WHY THE HARNESS NEEDS ITS OWN TESTS

It had none. Its correctness was established entirely by `aiecona-hr`'s integration
suite, which installs this package **from GitHub**. So a fault introduced here is
invisible until it is published, and then it fails in a repository that did not change.

That is not a hypothetical. Both injectors were wrong when first written, in ways only
an internal-consistency check finds:

**`REMOVED` is not a position status.** Migration 001 permits FILLED, VACANT, FROZEN and
ABOLISHED. A plausible-sounding invented value would have been refused by the CHECK
constraint on first ingestion — the exact class of defect this project spent two phases
removing.

**`valid_to is None` is not "still open".** The generator records a person's eventual
exit up front, so an assignment for somebody leaving in 2025 already carries a
`valid_to`. Testing for null found 64 of 300 people; the other 236 would have kept an
assignment running eighteen months past their own redundancy.

**A closed unit cannot receive joiners.** Hires are spread uniformly across the span and
the generator cannot know a unit will close, so 24 people were hired into it afterwards.
Left alone, the unit's headcount rises after its own closure.

None of those three would have been caught by any assertion about counts. They are all
caught by asking whether the corpus can be true.
"""
from __future__ import annotations

from datetime import date

import pytest

from pseudohcm.generator import Parameters, generate
from pseudohcm.scenarios import (
    CATALOGUE, inject_redundancy_programme, inject_unit_closure,
)

# Migration 001, `position.status`. Duplicated here rather than imported because the
# harness must not depend on the product — that separation is Gate 1, and a test that
# broke it would be a worse failure than the one it prevents.
POSITION_STATUS = {"FILLED", "VACANT", "FROZEN", "ABOLISHED"}
EXIT_CLASS = {"REGRETTED", "NON_REGRETTED", "INVOLUNTARY", "END_OF_TERM"}

REDUNDANCY_DATE = date(2024, 3, 31)
CLOSURE_DATE = date(2024, 9, 30)


def as_date(value):
    return None if value is None else date.fromisoformat(value)


def in_force(record, when):
    starts = as_date(record["valid_from"])
    ends = as_date(record.get("valid_to"))
    return starts <= when and (ends is None or ends > when)


@pytest.fixture
def corpus():
    return generate(Parameters(employee_count=2000, units=12, seed=7))


class TestTheCorpusOnlyUsesValuesTheSchemaAllows:
    def test_position_status_stays_within_the_enum(self, corpus):
        inject_redundancy_programme(corpus, on=REDUNDANCY_DATE, count=300)
        inject_unit_closure(corpus, on=CLOSURE_DATE)
        found = {p["status"] for p in corpus.positions}
        assert found <= POSITION_STATUS, f"invented status value(s): {found - POSITION_STATUS}"

    def test_exit_class_stays_within_the_enum(self, corpus):
        inject_redundancy_programme(corpus, on=REDUNDANCY_DATE, count=300)
        found = {p["exit_class"] for p in corpus.people if p["exit_class"]}
        assert found <= EXIT_CLASS, f"invented exit class(es): {found - EXIT_CLASS}"

    def test_the_involuntary_class_is_actually_produced(self):
        """The whole point of D66. Before it, no fixture in this project had ever
        emitted an involuntary exit, and a live defect hid behind that gap."""
        c = generate(Parameters(employee_count=500, units=6, seed=3))
        assert not any(p["exit_class"] == "INVOLUNTARY" for p in c.people)
        inject_redundancy_programme(c, on=REDUNDANCY_DATE, count=50)
        assert sum(1 for p in c.people if p["exit_class"] == "INVOLUNTARY") == 50


class TestTheRedundancyIsInternallyConsistent:
    def test_every_exit_is_on_the_redundancy_date(self, corpus):
        result = inject_redundancy_programme(corpus, on=REDUNDANCY_DATE, count=300)
        affected = set(result["person_ids"])
        for person in corpus.people:
            if person["person_id"] in affected:
                assert as_date(person["exit_date"]) == REDUNDANCY_DATE

    def test_no_assignment_outlives_its_own_redundancy(self, corpus):
        """The `valid_to is None` bug, pinned.

        236 of 300 people already carried a future exit date, so their assignment was
        not null-terminated and was skipped — leaving a person marked redundant in
        March 2024 with an assignment running to November 2025.
        """
        result = inject_redundancy_programme(corpus, on=REDUNDANCY_DATE, count=300)
        affected = set(result["person_ids"])
        outliving = [
            a for a in corpus.assignments
            if a["person_id"] in affected and in_force(a, REDUNDANCY_DATE)
        ]
        assert outliving == []

    def test_a_position_is_abolished_for_every_person_made_redundant(self, corpus):
        """What separates a redundancy from a mass resignation. If the positions stayed
        open the establishment would be unchanged and Pillar D would read the gap as
        demand to hire back."""
        result = inject_redundancy_programme(corpus, on=REDUNDANCY_DATE, count=300)
        assert result["positions_removed"] == result["people_exited"] == 300

    def test_it_brings_forward_an_exit_rather_than_inventing_a_second_one(self, corpus):
        """Somebody already leaving in November 2025 who is made redundant in March
        2024 has one exit, not two."""
        result = inject_redundancy_programme(corpus, on=REDUNDANCY_DATE, count=300)
        affected = set(result["person_ids"])
        assignments = [a for a in corpus.assignments if a["person_id"] in affected]
        assert len(assignments) == 300

    def test_it_is_deterministic(self):
        """Same seed, same parameters, same people. Document 10 §3 — the harness's
        central claim, and an injector that picked at random would break it."""
        picks = []
        for _ in range(2):
            c = generate(Parameters(employee_count=2000, units=12, seed=7))
            picks.append(inject_redundancy_programme(
                c, on=REDUNDANCY_DATE, count=300)["person_ids"])
        assert picks[0] == picks[1]


class TestTheUnitClosureIsInternallyConsistent:
    def test_the_unit_is_absent_after_and_present_before(self, corpus):
        result = inject_unit_closure(corpus, on=CLOSURE_DATE)
        unit = next(u for u in corpus.org_units
                    if u["org_unit_id"] == result["org_unit_id"])
        assert in_force(unit, date(2024, 6, 30))
        assert not in_force(unit, date(2025, 6, 30))

    def test_nobody_is_still_assigned_to_a_closed_unit(self, corpus):
        result = inject_unit_closure(corpus, on=CLOSURE_DATE)
        in_unit = {p["position_id"] for p in corpus.positions
                   if p["org_unit_id"] == result["org_unit_id"]}
        assert [a for a in corpus.assignments
                if a["position_id"] in in_unit and in_force(a, CLOSURE_DATE)] == []

    def test_nobody_joins_a_unit_after_it_closes(self, corpus):
        """24 people did, in the first version.

        Hires are spread uniformly and the generator cannot know a unit will close.
        Left alone the unit's headcount rises after its own closure — not a shrinking
        organisation, a broken fixture.
        """
        result = inject_unit_closure(corpus, on=CLOSURE_DATE)
        assert result["joiners_removed"] > 0, (
            "this corpus has no post-closure joiners, so this test is asserting "
            "nothing — pick a closure date inside the hiring span"
        )
        in_unit = {p["position_id"] for p in corpus.positions
                   if p["org_unit_id"] == result["org_unit_id"]}
        assert [a for a in corpus.assignments
                if a["position_id"] in in_unit
                and as_date(a["valid_from"]) > CLOSURE_DATE] == []

    def test_removing_the_joiners_leaves_no_orphans(self, corpus):
        """They are removed rather than exited — an exit implies employment and these
        people were never hired. Both halves have to go or the assignment references a
        person who does not exist."""
        inject_unit_closure(corpus, on=CLOSURE_DATE)
        people = {p["person_id"] for p in corpus.people}
        assert [a for a in corpus.assignments
                if a["person_id"] not in people] == []

    def test_the_unit_headcount_falls_to_nothing(self, corpus):
        result = inject_unit_closure(corpus, on=CLOSURE_DATE)
        in_unit = {p["position_id"] for p in corpus.positions
                   if p["org_unit_id"] == result["org_unit_id"]}

        def headcount(at):
            return sum(1 for a in corpus.assignments
                       if a["position_id"] in in_unit and in_force(a, at))

        assert headcount(date(2024, 6, 30)) > 0
        assert headcount(date(2025, 6, 30)) == 0

    def test_it_closes_a_leaf_rather_than_orphaning_children(self, corpus):
        """The default target is the last unit, which is a leaf. Closing a line of
        business would orphan its children, and this fixture is about closure rather
        than about reparenting."""
        result = inject_unit_closure(corpus, on=CLOSURE_DATE)
        children = [u for u in corpus.org_units
                    if u["parent_unit_id"] == result["org_unit_id"]]
        assert children == []


class TestTheCatalogueDescribesWhatWasBuilt:
    def test_both_scenarios_are_declared(self):
        keys = {s.key for s in CATALOGUE}
        assert {"redundancy_programme", "unit_closure"} <= keys

    def test_each_names_the_decision_it_serves(self):
        for scenario in CATALOGUE:
            assert scenario.decision, f"{scenario.key} cites no decision"
            assert scenario.expected, f"{scenario.key} states no expected behaviour"


class TestTheBaseCorpusIsUnchanged:
    def test_generate_still_produces_no_involuntary_exits(self):
        """De-growth is injected, never generated.

        `generate` is deterministic and every existing test rests on that — same seed,
        same parameters, byte-identical output. Teaching it to shrink would silently
        change every corpus this project has ever produced.
        """
        c = generate(Parameters(employee_count=1000, units=8, seed=99))
        assert {p["exit_class"] for p in c.people if p["exit_class"]} <= {
            "REGRETTED", "NON_REGRETTED"}
        assert all(p["status"] in {"FILLED", "VACANT"} for p in c.positions)

    def test_the_dead_parameter_is_gone(self):
        """`growth_curve_start` was declared and referenced nowhere. The class docstring
        claims every parameter is adjustable; one that does nothing is worse than a
        missing one, because somebody tunes it and concludes the generator ignores them.
        """
        assert not hasattr(Parameters(), "growth_curve_start")
