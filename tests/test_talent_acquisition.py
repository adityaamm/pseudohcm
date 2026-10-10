"""D185 — the recruiting module: opt-in, invented, coherent with the rest of the corpus."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict

import pseudohcm.emit as emit
import pseudohcm.generator as g

ON = g.Parameters(employee_count=600, units=5, seed=47, talent_acquisition=True)
STAGES = ("APPLIED", "SCREENED", "INTERVIEWING", "FINAL_STAGE", "OFFER", "ACCEPTED")
EXITS = {"DECLINED", "WITHDRAWN", "REJECTED"}


def corpus():
    return g.generate(ON)


def test_off_by_default_and_nothing_else_moves():
    plain = g.generate(g.Parameters(employee_count=600, units=5, seed=47))
    on = corpus()
    for entity in ("Requisition", "Candidate", "Application", "PipelineStageEvent"):
        assert plain.counts()[entity] == 0
        assert on.counts()[entity] > 0
    # Its own seeded generator: switching it on shifts no other draw.
    for attr in ("org_units", "jobs", "positions", "people", "assignments"):
        assert getattr(plain, attr) == getattr(on, attr), attr


def test_deterministic():
    assert asdict(corpus()) == asdict(corpus())


def test_every_vacancy_has_a_live_requisition_and_every_recent_hire_a_filled_one():
    c = corpus()
    current = {r["requisition_id"]: r for r in c.requisitions if r["valid_to"] is None}
    by_position = defaultdict(set)
    for r in current.values():
        by_position[r["position_id"]].add(r["status"])
    for seat in c.positions:
        if seat["status"] == "VACANT":
            assert by_position[seat["position_id"]] & {"OPEN", "ON_HOLD", "DRAFT"}
    filled = [r for r in current.values() if r["status"] == "FILLED"]
    assert filled and all(r["filled_on"] >= r["opened_on"] for r in filled)
    assert Counter(r["status"] for r in current.values()).keys() >= {
        "OPEN", "FILLED", "CANCELLED", "ON_HOLD"}


def test_a_closed_requisition_was_open_until_it_closed():
    c = corpus()
    versions = defaultdict(list)
    for r in c.requisitions:
        versions[r["requisition_id"]].append(r)
    for rows in versions.values():
        rows.sort(key=lambda r: r["valid_from"])
        if len(rows) == 2:
            assert rows[0]["status"] == "OPEN" and rows[0]["valid_to"] == rows[1]["valid_from"]
            assert rows[1]["status"] in ("FILLED", "CANCELLED")


def test_funnels_are_ordered_and_one_hire_per_filled_requisition():
    c = corpus()
    status = {r["requisition_id"]: r["status"] for r in c.requisitions if r["valid_to"] is None}
    req_of = {a["application_id"]: a["requisition_id"] for a in c.applications}
    events = defaultdict(list)
    for e in c.pipeline_stage_events:
        events[e["application_id"]].append(e)
    hires = Counter()
    for app, rows in events.items():
        rows.sort(key=lambda e: (e["entered_on"], STAGES.index(e["stage"])
                                 if e["stage"] in STAGES else 99))
        assert rows[0]["stage"] == "APPLIED"
        progression = [e["stage"] for e in rows if e["stage"] in STAGES]
        assert progression == list(STAGES[:len(progression)]), progression
        assert sum(e["stage"] in EXITS for e in rows) <= 1
        assert not ("ACCEPTED" in progression and any(e["stage"] in EXITS for e in rows))
        if "ACCEPTED" in progression:
            hires[req_of[app]] += 1
        if status[req_of[app]] in ("FILLED", "CANCELLED") and "ACCEPTED" not in progression:
            assert rows[-1]["stage"] in EXITS, "a closed requisition leaves nobody in flight"
    for req, s in status.items():
        assert hires[req] == (1 if s == "FILLED" else 0), (req, s)


def test_no_score_rank_or_assessment_anywhere():
    c = corpus()
    allowed_reasons = {None, "withdrawn by candidate", "offer declined", "requisition cancelled"}
    assert {e["exit_reason"] for e in c.pipeline_stage_events} <= allowed_reasons
    for row in c.candidates + c.applications:
        assert not {k for k in row if any(w in k for w in ("score", "rank", "rating"))}
    assert all(r["retain_until"] > r["first_seen_on"] for r in c.candidates)


def test_emitted(tmp_path):
    written = emit.emit(corpus(), tmp_path)
    for entity in ("Requisition", "Candidate", "Application", "PipelineStageEvent"):
        assert written[entity] > 0
        first = json.loads((tmp_path / f"{entity}.jsonl").read_text().splitlines()[0])
        assert first["prov"]["src_system"] == "pseudohcm"
