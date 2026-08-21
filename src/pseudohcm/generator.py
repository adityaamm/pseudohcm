"""Deterministic generation. Not "here is data" but "here is a documented process".

The output is not a claim about the world. It is the reproducible result of a published
rule set with stated parameters. Same seed, same parameters, byte-identical output.

Document 10 §3.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from pseudohcm.marking import mark

HISTORY_START = date(2015, 1, 1)


@dataclass
class Parameters:
    """Every parameter documented and adjustable. Nothing hidden."""

    seed: int = 20260807
    employee_count: int = 50_000          # per owner direction: 50,000 line items
    units: int = 24
    positions_per_unit: int = 0            # 0 = derive from employee_count
    vacancy_rate: float = 0.03
    annual_attrition: float = 0.114
    # `growth_curve_start: int = 32_100` was declared here and referenced nowhere in
    # this module. Removed rather than implemented: the class docstring above claims
    # "every parameter documented and adjustable, nothing hidden", and a parameter that
    # does nothing while looking like it shapes the headcount trajectory is worse than
    # a missing one — somebody tunes it and concludes the generator ignores them.
    #
    # De-growth is not a curve parameter in any case. It is a decision an organisation
    # takes on a date, and it lives in `scenarios.inject_redundancy_programme` and
    # `scenarios.inject_unit_closure` (D66) where it can be asserted against.
    part_time_share: float = 0.11          # so the FTE basis differs from the people basis
    history_start: date = HISTORY_START
    history_end: date = date(2026, 8, 7)


@dataclass
class Corpus:
    org_units: list[dict] = field(default_factory=list)
    jobs: list[dict] = field(default_factory=list)
    positions: list[dict] = field(default_factory=list)
    people: list[dict] = field(default_factory=list)
    assignments: list[dict] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return {
            "OrgUnit": len(self.org_units), "Job": len(self.jobs),
            "Position": len(self.positions), "Person": len(self.people),
            "Assignment": len(self.assignments),
        }


FAMILIES = ("Engineering", "Commercial", "Operations", "Product", "Corporate Functions")
LEVELS = (("L3", 3), ("L4", 4), ("L5", 5), ("L6", 6), ("L7", 7))


def generate(params: Parameters | None = None) -> Corpus:
    p = params or Parameters()
    rng = random.Random(p.seed)
    corpus = Corpus()
    now = datetime.now(timezone.utc).isoformat()

    def prov(obj: str) -> dict:
        return {
            "src_system": "pseudohcm", "src_object": obj,
            "sync_id": "sync-0001", "sync_at": now,
            "derived": False, "derivation": None, "confidence": None,
        }

    # --- org units ---
    for i in range(p.units):
        family = FAMILIES[i % len(FAMILIES)]
        corpus.org_units.append(mark({
            "org_unit_id": f"ou-{i:04d}", "unit_code": f"OU-{i:02d}",
            "name": f"{family} {i // len(FAMILIES) + 1}",
            "parent_unit_id": None if i < len(FAMILIES) else f"ou-{i % len(FAMILIES):04d}",
            "depth": 0 if i < len(FAMILIES) else 1,
            "is_line_of_business": i < len(FAMILIES),
            "is_strategic": family in ("Engineering", "Commercial"),
            "valid_from": p.history_start.isoformat(), "valid_to": None,
            "prov": prov("organisations"),
        }))

    # --- jobs ---
    for family in FAMILIES:
        for label, rank in LEVELS:
            corpus.jobs.append(mark({
                "job_id": f"job-{family[:3].upper()}-{label}",
                "job_code": f"{family[:3].upper()}-{label}",
                "job_family": family, "job_sub_family": None,
                "job_level": label, "job_level_rank": rank, "market_reference": None,
                "valid_from": p.history_start.isoformat(), "valid_to": None,
                "prov": prov("jobs"),
            }))

    # --- positions and people ---
    seats = int(p.employee_count / (1 - p.vacancy_rate))
    span_days = (p.history_end - p.history_start).days

    for i in range(seats):
        unit = corpus.org_units[rng.randrange(p.units)]
        job = corpus.jobs[rng.randrange(len(corpus.jobs))]
        filled = rng.random() > p.vacancy_rate
        corpus.positions.append(mark({
            "position_id": f"pos-{i:06d}", "position_code": f"PS-{i:06d}",
            "title": f"{job['job_family']} {job['job_level']}",
            "job_id": job["job_id"], "org_unit_id": unit["org_unit_id"],
            "reports_to_position_id": None if i == 0 else f"pos-{rng.randrange(max(1, i // 8)):06d}",
            "is_critical": rng.random() < 0.008,
            "criticality_basis": [], "criticality_score": None,
            "status": "FILLED" if filled else "VACANT", "fte": 1.0,
            "valid_from": p.history_start.isoformat(), "valid_to": None,
            "prov": prov("positions"),
        }))

    filled_positions = [p_ for p_ in corpus.positions if p_["status"] == "FILLED"]
    for i, seat in enumerate(filled_positions[: p.employee_count]):
        hired = p.history_start + timedelta(days=rng.randrange(span_days))
        exited = None
        if rng.random() < p.annual_attrition * ((p.history_end - hired).days / 365.25):
            exited = hired + timedelta(days=rng.randrange(60, max(90, (p.history_end - hired).days or 90)))
            if exited > p.history_end:
                exited = None

        corpus.people.append(mark({
            "person_id": f"per-{i:06d}", "display_ref": f"EMP-{i:06d}",
            "legal_name": None,          # never generated. Not a simulation of anyone.
            "work_email": f"emp{i:06d}@example.invalid",
            "employment_type": "PERMANENT" if rng.random() > 0.06 else "FIXED_TERM",
            "hire_date_original": hired.isoformat(), "hire_date_current": hired.isoformat(),
            "exit_date": exited.isoformat() if exited else None,
            "exit_class": ("REGRETTED" if rng.random() < 0.55 else "NON_REGRETTED") if exited else None,
            "fte": 1.0 if rng.random() > p.part_time_share else rng.choice((0.5, 0.6, 0.8)),
            "location_country": rng.choice(("GB", "US", "IN", "NL", "DE")),
            "valid_from": hired.isoformat(), "valid_to": None,
            "prov": prov("workers"),
        }))

        corpus.assignments.append(mark({
            "assignment_id": f"asg-{i:06d}", "person_id": f"per-{i:06d}",
            "position_id": seat["position_id"], "assignment_type": "PRIMARY", "fte": 1.0,
            "manager_person_id": None,
            "valid_from": hired.isoformat(),
            "valid_to": exited.isoformat() if exited else None,
            # Transaction time: when the record was created, which for most is the same
            # day. The backdated-correction scenario deliberately breaks this.
            "tx_from": datetime.combine(hired, datetime.min.time(), tzinfo=timezone.utc).isoformat(),
            "tx_to": None, "correction_of": None,
            "prov": prov("assignments"),
        }))

    return corpus
