"""D201 — the emulated recruiting system that is separate from the HR system."""
from __future__ import annotations

import json

import pseudohcm.emit as emit
import pseudohcm.generator as g


def load(path):
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def corpus():
    return g.generate(g.Parameters(employee_count=200, units=3, seed=201,
                                   talent_acquisition=True))


def test_its_own_keys_and_its_own_catalogue(tmp_path):
    c = corpus()
    v = emit.emit_recruiting_system(c, tmp_path)
    hr_jobs = {j["job_id"] for j in c.jobs}
    reqs = load(tmp_path / "Requisition.jsonl")
    assert reqs and not {r["job_id"] for r in reqs} & hr_jobs
    refs = load(tmp_path / "RecruitingReference.jsonl")
    assert {r["reference_id"] for r in refs if r["reference_kind"] == "JOB"} == \
        {r["job_id"] for r in reqs}
    assert v["references"] == len(refs)


def test_only_the_named_jobs_have_a_loosened_code(tmp_path):
    c = corpus()
    v = emit.emit_recruiting_system(c, tmp_path, near_codes=2)
    codes = {j["job_code"] for j in c.jobs}
    jobs = [r for r in load(tmp_path / "RecruitingReference.jsonl")
            if r["reference_kind"] == "JOB"]
    assert sum(r["code"] not in codes for r in jobs) == len(v["near_code_jobs"]) == 2


def test_employee_numbers_only_on_internal_applicants(tmp_path):
    c = corpus()
    v = emit.emit_recruiting_system(c, tmp_path, unknown_employee_refs=1)
    people = {p["person_id"] for p in c.people}
    cands = load(tmp_path / "Candidate.jsonl")
    with_ref = [x for x in cands if x.get("employee_ref")]
    assert with_ref and all(x["source"] == "INTERNAL" for x in with_ref)
    assert sum(x["employee_ref"] not in people for x in with_ref) == 1
    assert set(v["employee_refs_linkable"].values()) <= people


def test_everything_else_is_the_same(tmp_path):
    c = corpus()
    emit.emit_recruiting_system(c, tmp_path)
    reqs = load(tmp_path / "Requisition.jsonl")
    strip = lambda r: {k: v for k, v in r.items()
                       if k not in ("job_id", "position_id", "org_unit_id")}
    assert [strip(r) for r in reqs] == [strip(json.loads(json.dumps(r, default=str)))
                                        for r in c.requisitions]
    assert len(load(tmp_path / "Application.jsonl")) == len(c.applications)
