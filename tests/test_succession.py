"""D174: the synthetic succession pipeline — and whether it can show what the product
exists to find: gaps, shared successors, and records it must refuse."""
from __future__ import annotations

import json
from collections import Counter

from pseudohcm.generator import READINESS_BANDS, Parameters, generate

ON = Parameters(employee_count=4000, units=8, seed=11, succession=True)


def test_off_by_default_and_then_byte_identical():
    before = generate(Parameters(employee_count=400, units=4, seed=3))
    again = generate(Parameters(employee_count=400, units=4, seed=3))
    assert before.succession_nominations == []
    assert "legal_entity_code" not in before.org_units[0]
    assert json.dumps(before.positions) == json.dumps(again.positions)


def test_turning_it_on_shifts_nothing_else():
    off = generate(Parameters(employee_count=400, units=4, seed=3))
    on = generate(Parameters(employee_count=400, units=4, seed=3, succession=True))
    assert json.dumps(off.people) == json.dumps(on.people)
    assert json.dumps(off.positions) == json.dumps(on.positions)


def test_the_mix_has_gaps_shared_successors_and_refusals():
    c = generate(ON)
    flagged = {s["position_id"] for s in c.positions if s["hr_critical_flag"]}
    employed = {p["person_id"] for p in c.people if p["exit_date"] is None}
    on_flagged = [n for n in c.succession_nominations if n["position_id"] in flagged
                  and n["person_id"] in employed]
    per = Counter(n["position_id"] for n in on_flagged)
    assert any(s not in per for s in flagged), "some critical positions have no successor"
    assert any(v >= 2 for v in per.values()), "some have two or more"
    people = Counter(n["person_id"] for n in on_flagged)
    assert any(v >= 2 for v in people.values()), "someone is on several pipelines"
    assert any(n["position_id"] not in flagged for n in c.succession_nominations)
    assert any(n["person_id"] not in employed for n in c.succession_nominations)


def test_plain_generic_bands_only():
    c = generate(ON)
    assert {n["readiness_band"] for n in c.succession_nominations} <= {
        b for b, _ in READINESS_BANDS}


def test_deterministic():
    assert json.dumps(generate(ON).succession_nominations) == \
        json.dumps(generate(ON).succession_nominations)



SCORED = Parameters(employee_count=4000, units=8, seed=11, succession=True,
                    leadership_scores=True)


def test_scores_show_every_rule():
    from pseudohcm.generator import FRAMEWORK_VERSION, PREVIOUS_FRAMEWORK_VERSION
    c = generate(SCORED)
    nominees = {n["person_id"] for n in c.succession_nominations}
    versions = Counter(s["framework_version"] for s in c.leadership_scores)
    assert versions[FRAMEWORK_VERSION] and versions[PREVIOUS_FRAMEWORK_VERSION]
    per = Counter(s["person_id"] for s in c.leadership_scores)
    assert any(v >= 2 for v in per.values()), "someone carries an older score too"
    assert any(s["person_id"] not in nominees for s in c.leadership_scores)
    assert min(s["assessed_on"] for s in c.leadership_scores) < "2024-08-07"
    assert {"competency", "competencies"}.isdisjoint(
        {k for s in c.leadership_scores for k in s}), "one overall score only (D150)"


def test_scores_shift_nothing_else():
    a = generate(ON)
    b = generate(SCORED)
    assert json.dumps(a.succession_nominations) == json.dumps(b.succession_nominations)
    assert json.dumps(a.people) == json.dumps(b.people)
