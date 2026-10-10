"""D189 — opt-in manager links, and one lenient team in some units."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict

import pseudohcm.generator as g

BASE = dict(employee_count=400, units=6, seed=47, rating_cycles=2)


def test_off_by_default_and_nothing_else_moves():
    plain = g.generate(g.Parameters(**BASE))
    on = g.generate(g.Parameters(**BASE, managers=True))
    assert all(a["manager_person_id"] is None for a in plain.assignments)
    assert sum(a["manager_person_id"] is not None for a in on.assignments) > 0
    for attr in ("org_units", "jobs", "positions", "people"):
        assert getattr(plain, attr) == getattr(on, attr), attr
    assert len(plain.performance_events) == len(on.performance_events)


def test_deterministic():
    p = g.Parameters(**BASE, managers=True)
    assert asdict(g.generate(p)) == asdict(g.generate(p))


def test_managers_are_in_the_same_unit_as_their_reports():
    c = g.generate(g.Parameters(**BASE, managers=True))
    unit_of_pos = {s["position_id"]: s["org_unit_id"] for s in c.positions}
    unit_of = {a["person_id"]: unit_of_pos[a["position_id"]] for a in c.assignments}
    for a in c.assignments:
        if a["manager_person_id"]:
            assert unit_of[a["manager_person_id"]] == unit_of[a["person_id"]]


def test_lenient_teams_are_rated_higher_and_stay_on_the_scale():
    plain = g.generate(g.Parameters(**BASE))
    on = g.generate(g.Parameters(**BASE, managers=True))
    moved = [(a, b) for a, b in zip(plain.performance_events, on.performance_events)
             if a["rating_rank"] != b["rating_rank"]]
    assert moved and all(b["rating_rank"] == a["rating_rank"] + 1 for a, b in moved)
    assert all(1 <= e["rating_rank"] <= 5 for e in on.performance_events)
    assert all(e["rating_value"] == str(e["rating_rank"]) for e in on.performance_events)
