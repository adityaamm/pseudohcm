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

    # -- P2.6: performance and role assessment ---------------------------------
    #
    # `rating_cycles = 0` produces none of it, so every existing test keeps the corpus
    # it was written against. Opt-in rather than opt-out: turning this on changes row
    # counts, and a generator that silently starts emitting five new entity types would
    # break assertions that were right when they were written.
    rating_cycles: int = 0                 # annual cycles ending before history_end
    rating_points: int = 5
    # The share of ratings deliberately left without a position. `performance_event`
    # allows a null `position_id`, so the unattributable path is real and Pillar E
    # counts those rows rather than dropping them. A corpus where every rating resolves
    # to a unit never exercises it.
    ratings_without_position: float = 0.02
    role_interaction_density: float = 0.18  # share of ordered job pairs that get an edge

    # -- P2.7: the skills vocabulary --------------------------------------------
    #
    # Opt-in like the rating cycles, and for the same reason: turning it on changes
    # row counts, and a generator that silently starts emitting four more entity types
    # breaks assertions that were right when somebody wrote them.
    #
    # `skill_terms = 0` produces none of it, which is every existing corpus.
    skill_terms: int = 0                   # customer vocabulary terms
    skill_coverage: float = 0.62           # share of employed people holding assertions
    # Share of terms with no mapping to a standard. D40 suppresses a cluster below the
    # coverage threshold and D61 reports in the customer's own words, so a corpus where
    # every term maps cleanly never exercises either. Real vocabularies are messier.
    unmapped_term_share: float = 0.18
    # Share of assertions that have expired by `history_end`. A certification that
    # lapsed is not present supply, and a corpus without any never proves the
    # difference is applied.
    expired_assertion_share: float = 0.09
    # Share of roles whose description will not support content assessment. Above 0.40
    # `role_relevance.organisation_caveat` fires, so the default sits below the line
    # and a test that wants the caveat raises it deliberately.
    thin_description_share: float = 0.22


@dataclass
class Corpus:
    org_units: list[dict] = field(default_factory=list)
    jobs: list[dict] = field(default_factory=list)
    positions: list[dict] = field(default_factory=list)
    people: list[dict] = field(default_factory=list)
    assignments: list[dict] = field(default_factory=list)
    # P2.6. The entities P2.4 wired and nothing had ever produced. Until these existed,
    # `rating_integrity` and `interaction_graph` had unit tests and no end-to-end run,
    # and every CI failure this project has had came from that seam.
    # P2.7. The skills vocabulary — the last entities `role_relevance` needs before
    # its substitutability component can be computed from anything real.
    customer_skill_terms: list[dict] = field(default_factory=list)
    canonical_skills: list[dict] = field(default_factory=list)
    taxonomy_links: list[dict] = field(default_factory=list)
    skill_assertions: list[dict] = field(default_factory=list)
    role_required_terms: list[dict] = field(default_factory=list)
    rating_scales: list[dict] = field(default_factory=list)
    performance_cycles: list[dict] = field(default_factory=list)
    performance_events: list[dict] = field(default_factory=list)
    role_interactions: list[dict] = field(default_factory=list)
    role_requirements: list[dict] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return {
            "OrgUnit": len(self.org_units), "Job": len(self.jobs),
            "Position": len(self.positions), "Person": len(self.people),
            "Assignment": len(self.assignments),
            "CustomerSkillTerm": len(self.customer_skill_terms),
            "CanonicalSkill": len(self.canonical_skills),
            "TaxonomyLink": len(self.taxonomy_links),
            "SkillAssertion": len(self.skill_assertions),
            "RoleRequiredTerm": len(self.role_required_terms),
            "RatingScale": len(self.rating_scales),
            "PerformanceCycle": len(self.performance_cycles),
            "PerformanceEvent": len(self.performance_events),
            "RoleInteraction": len(self.role_interactions),
            "RoleRequirement": len(self.role_requirements),
        }


FAMILIES = ("Engineering", "Commercial", "Operations", "Product", "Corporate Functions")
LEVELS = (("L3", 3), ("L4", 4), ("L5", 5), ("L6", 6), ("L7", 7))


def generate(params: Parameters | None = None) -> Corpus:
    p = params or Parameters()
    rng = random.Random(p.seed)
    corpus = Corpus()

    # `sync_at` IS DERIVED FROM THE PARAMETERS, NOT FROM THE CLOCK.
    #
    # This was `datetime.now(timezone.utc)`, which made the module docstring above and
    # Document 10 §3 — "same seed and same parameters yields byte-identical output" —
    # false for every run since the harness was written. Two corpora from identical
    # parameters differed in every single row.
    #
    # It survived because the determinism test compared `person_id`s and assignment
    # start dates rather than whole records. The test agreed with the code and the
    # prose disagreed with both, which is Document 19's pattern exactly.
    #
    # The end of the described history is the honest value: a corpus covering the world
    # up to `history_end` is a sync taken at `history_end`. Nothing asserts a specific
    # `sync_at` — the integration tests check it is present, or take a max over it —
    # so the data vintage this produces is stable rather than drifting with wall clock.
    now = datetime.combine(p.history_end, datetime.min.time(),
                           tzinfo=timezone.utc).isoformat()

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
            # D67. `exit_date` is the LAST DAY WORKED; `valid_to` is the first day the
            # record version is no longer true. They are one day apart, always.
            #
            # This wrote the exit date straight into valid_to, which ended every
            # assignment a day early and made a same-day engagement inexpressible:
            # `[30 Sept, 30 Sept)` contains no time and assignment_valid_period refuses
            # it. Contract entities.ValidPeriod states the rule for both repositories.
            "valid_to": ((exited + timedelta(days=1)).isoformat() if exited else None),
            # Transaction time: when the record was created, which for most is the same
            # day. The backdated-correction scenario deliberately breaks this.
            "tx_from": datetime.combine(hired, datetime.min.time(), tzinfo=timezone.utc).isoformat(),
            "tx_to": None, "correction_of": None,
            "prov": prov("assignments"),
        }))

    _generate_role_assessment(corpus, p, rng, prov)
    _generate_skills(corpus, p, rng, prov)
    _generate_performance(corpus, p, rng, prov)
    return corpus


# ---------------------------------------------------------------------------
# P2.6 — performance and role assessment
# ---------------------------------------------------------------------------

# The rating distributions a real organisation actually produces, by unit. A generator
# that drew every rank uniformly would hand Pillar E a perfectly calibrated
# organisation, and the integrity pillar would correctly report no compression, no
# inflation and no divergence anywhere — from synthetic data that had none.
#
# That is the harness version of the well-formed 200: a corpus that cannot fail the
# check it exists to exercise. D66 is the precedent — redundancy and unit closure were
# added as injectors precisely because no fixture in the project had ever produced an
# involuntary exit, which is how D65 survived 985 passing tests.
#
# Weights are over ranks 1..N, renormalised to the configured point count.
_RATING_SHAPES: tuple[tuple[str, tuple[float, ...]], ...] = (
    ("healthy", (0.05, 0.15, 0.45, 0.25, 0.10)),
    # Everyone a 3. `spread` collapses and COMPRESSION fires.
    ("compressed", (0.01, 0.04, 0.90, 0.04, 0.01)),
    # Nobody below a 4. The classic inflated unit.
    ("inflated", (0.00, 0.02, 0.13, 0.50, 0.35)),
    ("harsh", (0.18, 0.37, 0.35, 0.08, 0.02)),
)

_DEPENDENCY_TYPES = ("PROVIDES_INPUT_TO", "APPROVES_FOR", "ESCALATES_TO",
                     "COORDINATES_WITH")
# Every basis appears. STRUCTURAL_INFERENCE carries a model version because the schema
# refuses one without it — an inferred edge nobody can reproduce is not defensible
# input to a score that ranks roles (Doc 03C §6.1).
_BASES = ("STATED_IN_DESCRIPTION", "IDEOM_CONFIRMED", "STRUCTURAL_INFERENCE")
_MODEL_VERSION = "pseudohcm-structural-inference-1.0"

_DECISION_RIGHTS_BY_RANK: dict[int, tuple[str, ...]] = {
    3: (),
    4: ("TECHNICAL_AUTHORITY",),
    5: ("TECHNICAL_AUTHORITY", "PRIORITISATION"),
    6: ("TECHNICAL_AUTHORITY", "PRIORITISATION", "HIRING"),
    7: ("TECHNICAL_AUTHORITY", "PRIORITISATION", "HIRING", "SPEND_APPROVAL",
        "EXTERNAL_COMMITMENT"),
}


def _weights_for(shape: tuple[float, ...], points: int) -> list[float]:
    """Fit a five-point shape onto whatever scale is configured.

    Truncated and renormalised rather than interpolated. The shapes above are stated
    over five points because that is what they describe; stretching them across three
    would invent a distribution nobody wrote down.
    """
    trimmed = list(shape[:points]) + [0.0] * max(0, points - len(shape))
    total = sum(trimmed)
    return [w / total for w in trimmed] if total else [1 / points] * points


def _generate_role_assessment(corpus: Corpus, p: Parameters, rng: random.Random,
                              prov) -> None:
    """One requirement per job, and a dependency graph over job codes.

    NOT one per position. `role_requirement.position_id` exists for seat-specific
    requirements and is null here, because a requirement per seat would give a
    50,000-row table describing 25 distinct roles — and substitutability, which
    compares required terms across job codes, would then compare a role with itself
    24,000 times.
    """
    if not corpus.jobs:
        return

    total = len(corpus.jobs)
    thin_count = round(p.thin_description_share * total)
    thin_seen = 0
    for index, job in enumerate(corpus.jobs):
        # Deterministic rather than sampled, so the thin share is exactly the parameter
        # at any corpus size. A sampled share drifts on small corpora, and the tests
        # that matter here run small.
        #
        # Distributed by the Bresenham rule rather than `index % 100 < share * 100`,
        # which is what this said first. With 25 job codes every index is below 22, so
        # 22 of 25 roles came out thin against a parameter of 0.22 — a four-fold
        # overshoot that would have fired `organisation_caveat` on every corpus and
        # made the caveat look like the normal state of the world.
        #
        # It also spreads them: taking the first N would have made every thin role an
        # Engineering one, since jobs are generated family by family.
        thin = (index * thin_count) // total != ((index + 1) * thin_count) // total
        if thin:
            # Alternate on a counter of THIN-eligible roles, not on `index`.
            #
            # Keyed on `index`, the Bresenham selection above happened to pick only
            # even indices, so every thin role came out ABSENT and THIN never appeared
            # at all. The first attempt at a fix used `len(corpus.role_requirements)`,
            # which is exactly `index` here because one requirement is appended per
            # job — the same bug wearing a different expression, and the check caught
            # it a second time.
            #
            # THIN is the more interesting of the two: text exists and does not support
            # assessment, which is the case D24's suppression is really about.
            quality = "THIN" if thin_seen % 2 else "ABSENT"
            thin_seen += 1
        else:
            quality = "RICH" if index % 3 else "ADEQUATE"
        # The schema refuses RICH or ADEQUATE with no text. A quality label the text
        # does not support is the same lie as a figure without its caveat.
        text = (None if quality == "ABSENT"
                else f"Accountable for {job['job_family'].lower()} outcomes at "
                     f"{job['job_level']}. Works with adjacent functions to deliver "
                     "committed scope.")
        corpus.role_requirements.append(mark({
            "requirement_id": f"req-{job['job_code']}",
            "job_id": job["job_id"], "position_id": None,
            "stated_purpose": f"{job['job_family']} delivery at {job['job_level']}",
            "description_text": text,
            "description_quality": quality,
            "required_level": job["job_level"],
            "decision_rights": list(
                _DECISION_RIGHTS_BY_RANK.get(job["job_level_rank"], ())),
            "source": "HCM_JOB_DESCRIPTION",
            "last_reviewed": (p.history_end - timedelta(days=rng.randrange(30, 900))
                              ).isoformat(),
            "valid_from": p.history_start.isoformat(), "valid_to": None,
            "prov": prov("job_descriptions"),
        }))

    # --- the dependency graph ---
    #
    # Edges run between job ids and there is nowhere in the row to put a person. Two
    # constraints the schema enforces and this must not trip: no self-dependency, and
    # STRUCTURAL_INFERENCE must name its model version.
    #
    # Direction is biased up the level ranks, so seniors accumulate dependants and the
    # graph has hubs. A uniformly random graph gives every role the same centrality and
    # makes the ranking meaningless — the same failure as uniform ratings.
    edge = 0
    for source in corpus.jobs:
        for target in corpus.jobs:
            if source["job_id"] == target["job_id"]:
                continue
            lift = 1.6 if target["job_level_rank"] > source["job_level_rank"] else 0.7
            if rng.random() >= p.role_interaction_density * lift:
                continue
            basis = _BASES[edge % len(_BASES)]
            corpus.role_interactions.append(mark({
                "interaction_id": f"int-{edge:06d}",
                "from_job_id": source["job_id"], "from_position_id": None,
                "to_job_id": target["job_id"], "to_position_id": None,
                "dependency_type": _DEPENDENCY_TYPES[edge % len(_DEPENDENCY_TYPES)],
                "strength": round(rng.uniform(0.35, 0.95), 3),
                "basis": basis,
                "confidence": round(rng.uniform(0.55, 0.99), 3),
                "model_version": (_MODEL_VERSION
                                  if basis == "STRUCTURAL_INFERENCE" else None),
                "valid_from": p.history_start.isoformat(), "valid_to": None,
                "prov": prov("job_descriptions"),
            }))
            edge += 1


def _generate_performance(corpus: Corpus, p: Parameters, rng: random.Random,
                          prov) -> None:
    """Annual cycles, one rating per employed person per cycle.

    WHO GETS RATED, AND WHY THE PREDICATE IS THE EMPLOYMENT ONE

    A person is rated in a cycle if they were employed on the cycle end date — using
    the same inclusive `exit_date` rule as D67, because a leaver whose last day is the
    cycle end date did work the cycle. Rating everyone on record would put ratings
    against people who left four years earlier, and Pillar E would report unit
    populations that no headcount could reproduce.
    """
    if p.rating_cycles <= 0 or not corpus.people:
        return

    scale_id = "scale-primary"
    corpus.rating_scales.append(mark({
        "scale_id": scale_id, "label": f"{p.rating_points}-point performance scale",
        "point_count": p.rating_points,
        "points": [str(i) for i in range(1, p.rating_points + 1)],
        "is_forced_distribution": False,
        # Stated, so divergence is computable. Without it the pillar correctly reports
        # "no intended distribution recorded" and the divergence half goes untested.
        "target_distribution": [round(w, 4) for w in
                                _weights_for(_RATING_SHAPES[0][1], p.rating_points)],
        "valid_from": p.history_start.isoformat(), "valid_to": None,
        "prov": prov("rating_scales"),
    }))

    position_of = {a["person_id"]: a["position_id"] for a in corpus.assignments}
    unit_of = {s["position_id"]: s["org_unit_id"] for s in corpus.positions}
    # A unit keeps its distribution shape across cycles. A unit that is compressed one
    # year and inflated the next is noise, and CYCLE_DRIFT would fire on every unit
    # every cycle — a finding that is always present is not a finding.
    shape_of = {u["org_unit_id"]: _RATING_SHAPES[i % len(_RATING_SHAPES)][1]
                for i, u in enumerate(corpus.org_units)}
    ranks = list(range(1, p.rating_points + 1))

    # The most recent year that finished before the corpus ends, then step back one
    # year per cycle.
    #
    # This was computed inside the loop as `history_end.year - cycle_index`, adjusted
    # down when it landed past the end. With a mid-year `history_end`, cycles 0 and 1
    # both resolved to 31 December of the prior year — the same `period_end` AND the
    # same `cycle_id`, which is the primary key of `performance_cycle`. Every person
    # would have been rated twice in one cycle, and the load would have failed on a
    # duplicate key rather than producing a wrong answer.
    #
    # Worth noting which way that failure ran: the constraint in the schema would have
    # caught it. It is only visible here because the harness is checked at all.
    latest_complete = (p.history_end.year - 1
                       if date(p.history_end.year, 12, 31) >= p.history_end
                       else p.history_end.year)

    event = 0
    for cycle_index in range(p.rating_cycles):
        period_end = date(latest_complete - cycle_index, 12, 31)
        if period_end < p.history_start:
            break
        period_start = date(period_end.year, 1, 1)
        cycle_id = f"cycle-{period_end.year}"
        corpus.performance_cycles.append(mark({
            "cycle_id": cycle_id, "label": f"FY{period_end.year}",
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "scale_id": scale_id, "status": "CLOSED",
            "prov": prov("performance_cycles"),
        }))

        for person in corpus.people:
            hired = date.fromisoformat(person["hire_date_current"])
            exited = (date.fromisoformat(person["exit_date"])
                      if person["exit_date"] else None)
            if hired > period_end or (exited is not None and exited < period_end):
                continue
            position_id = position_of.get(person["person_id"])
            unit = unit_of.get(position_id)
            weights = shape_of.get(unit, _RATING_SHAPES[0][1])
            rank = rng.choices(ranks, weights=_weights_for(weights, p.rating_points))[0]
            corpus.performance_events.append(mark({
                "event_id": f"perf-{event:07d}",
                "person_id": person["person_id"],
                # Null for a share of rows on purpose — see `ratings_without_position`.
                "position_id": (None
                                if rng.random() < p.ratings_without_position
                                else position_id),
                "cycle_id": cycle_id,
                "rating_scale_id": scale_id,
                "rating_rank": rank,
                "has_narrative": rng.random() < 0.7,
                "valid_from": period_end.isoformat(), "valid_to": None,
                "tx_from": datetime.combine(period_end, datetime.min.time(),
                                            tzinfo=timezone.utc).isoformat(),
                "tx_to": None, "correction_of": None,
                "prov": prov("performance_reviews"),
            }))
            event += 1


# ---------------------------------------------------------------------------
# P2.7 — the skills vocabulary
# ---------------------------------------------------------------------------

# A customer's own words, by family. Deliberately ordinary business vocabulary and
# deliberately NOT a taxonomy anybody publishes: these are the labels an organisation
# happens to use, which is the whole premise of `CustomerSkillTerm` and D61.
#
# The first two of each family are shared with the family above it. That overlap is
# not decoration — `role_relevance.substitutability` looks for job codes whose required
# terms overlap by 70% or more, and a vocabulary partitioned cleanly by family would
# find no substitutes anywhere and make the component useless.
_FAMILY_TERMS: dict[str, tuple[str, ...]] = {
    "Engineering": ("systems design", "code review", "incident response",
                    "distributed systems", "release management"),
    "Commercial": ("systems design", "code review", "pipeline management",
                   "contract negotiation", "account planning"),
    "Operations": ("incident response", "release management", "capacity planning",
                   "vendor management", "process improvement"),
    "Product": ("pipeline management", "account planning", "discovery research",
                "roadmap planning", "experiment design"),
    "Corporate Functions": ("vendor management", "process improvement",
                            "financial control", "policy drafting",
                            "regulatory reporting"),
}

# Terms every senior role needs regardless of family, which is what makes a senior in
# one family a partial substitute for a senior in another.
_SENIOR_TERMS: tuple[str, ...] = ("stakeholder management", "budget ownership")

_EVIDENCE = ("SELF_DECLARED", "MANAGER_CONFIRMED", "CERTIFICATION", "ASSESSMENT",
             "INFERRED_FROM_ROLE")


def _generate_skills(corpus: Corpus, p: Parameters, rng: random.Random, prov) -> None:
    """The customer's vocabulary, what it maps to, and who has claimed what.

    WHAT THE STANDARD-SIDE ROWS ARE, AND WHAT THEY ARE NOT

    `canonical_skill` exists to hold nodes from a published standard — O*NET or ESCO —
    under that standard's licence. **Nothing here is drawn from either.** The rows this
    generator produces carry synthetic concept identifiers and an attribution that says
    so in the field a reader would check.

    That is a guard-rail requirement and not a convenience. Embedding real standard
    content in a synthetic harness would put third-party material into this repository
    under an attribution the harness cannot honour, and a reviewer comparing a
    `preferred_label` here against the real standard must find them obviously unrelated
    rather than plausibly similar.

    The *shape* is faithful — a concept id, a preferred label never rendered to a
    customer, a crosswalk group, a version, an attribution string — which is what the
    D61 translation path actually exercises. The content is ours.
    """
    if p.skill_terms <= 0 or not corpus.jobs:
        return

    by_job = {j["job_id"]: j for j in corpus.jobs}

    # --- the customer's vocabulary ---
    labels: list[str] = []
    for family in FAMILIES:
        labels.extend(_FAMILY_TERMS[family])
    labels.extend(_SENIOR_TERMS)
    # Deduplicated with order preserved: the family lists share terms on purpose, and
    # a term is one term however many families use it.
    seen: set[str] = set()
    ordered = [x for x in labels if not (x in seen or seen.add(x))]
    ordered = ordered[: p.skill_terms] if p.skill_terms < len(ordered) else ordered

    unmapped_count = round(p.unmapped_term_share * len(ordered))
    term_id_of: dict[str, str] = {}
    for index, label in enumerate(ordered):
        # Bresenham again, for an exact share spread across the list rather than
        # clustered at one end — the same rule and the same reason as the thin
        # descriptions above.
        unmapped = (index * unmapped_count) // len(ordered) != (
            (index + 1) * unmapped_count) // len(ordered)
        term_id = f"term-{index:03d}"
        term_id_of[label] = term_id
        corpus.customer_skill_terms.append(mark({
            "term_id": term_id, "label": label, "parent_term_id": None,
            "source": "CUSTOMER_FRAMEWORK" if index % 3 else "HCM_DERIVED",
            "mapping_status": "UNMAPPED" if unmapped else "MAPPED",
            "valid_from": p.history_start.isoformat(), "valid_to": None,
            "prov": prov("skill_terms"),
        }))

    # --- the standard-side nodes, synthetic throughout ---
    #
    # Two standards and a crosswalk group shared between them, because D61 keys a
    # cluster on `crosswalk_group_id` and never on a label. A corpus with one standard
    # never exercises the crosswalk at all.
    mapped = [t for t in corpus.customer_skill_terms
              if t["mapping_status"] == "MAPPED"]
    for index, term in enumerate(mapped):
        group = f"xwalk-{index // 2:03d}"
        for standard in ("ONET", "ESCO"):
            corpus.canonical_skills.append(mark({
                "canonical_skill_id": f"canon-{standard.lower()}-{index:03d}",
                "standard": standard,
                # SYNTHETIC. Not a real concept identifier from either standard, and
                # shaped so nobody could mistake it for one.
                "standard_concept_id": f"SYNTHETIC-{standard}-{index:05d}",
                "preferred_label": f"synthetic concept {index} ({standard.lower()})",
                "crosswalk_group_id": group,
                "standard_version": "synthetic-0",
                "attribution": (
                    "SYNTHETIC — generated by pseudohcm. Not derived from O*NET, ESCO "
                    "or any published taxonomy, and carrying no third-party licence."
                ),
                "prov": prov("skill_taxonomy"),
            }))

    # --- our mapping claims ---
    link = 0
    for index, term in enumerate(mapped):
        for standard in ("ONET", "ESCO"):
            confirmed = index % 4 == 0
            corpus.taxonomy_links.append(mark({
                "link_id": f"link-{link:04d}",
                "term_id": term["term_id"],
                "canonical_skill_id": f"canon-{standard.lower()}-{index:03d}",
                # D13. A spread of confidence, because a corpus where every mapping is
                # certain never exercises the low-confidence caveat that travels with a
                # substitutability comparison built on weak links.
                "confidence": round(rng.uniform(0.55, 0.99), 3),
                "method": "HUMAN_CONFIRMED" if confirmed else rng.choice(
                    ("EXACT", "LEXICAL", "SEMANTIC")),
                "approved_by": "aditya@builder.local" if confirmed else None,
                "approved_at": (datetime.combine(p.history_end, datetime.min.time(),
                                                 tzinfo=timezone.utc).isoformat()
                                if confirmed else None),
                "recorded_at": datetime.combine(
                    p.history_start, datetime.min.time(),
                    tzinfo=timezone.utc).isoformat(),
                "superseded_at": None,
                "prov": prov("skill_taxonomy"),
            }))
            link += 1

    # --- what each role requires ---
    #
    # Family core terms plus the senior pair above L5. This is what gives
    # substitutability something to find: two seniors in different families share the
    # senior terms and one or two family terms, which lands some pairs above the 70%
    # overlap threshold and leaves others below it.
    requirement_of = {r["job_id"]: r["requirement_id"]
                      for r in corpus.role_requirements}
    for job in corpus.jobs:
        requirement_id = requirement_of.get(job["job_id"])
        if requirement_id is None:
            continue
        wanted = list(_FAMILY_TERMS[job["job_family"]])
        if job["job_level_rank"] >= 5:
            wanted += list(_SENIOR_TERMS)
        for position, label in enumerate(wanted):
            term_id = term_id_of.get(label)
            if term_id is None:
                continue
            corpus.role_required_terms.append(mark({
                "requirement_id": requirement_id, "term_id": term_id,
                # The first three are essential; the rest are desirable. A requirement
                # set where everything is essential makes every role look equally
                # irreplaceable.
                "is_essential": position < 3,
                "prov": prov("job_descriptions"),
            }))

    # --- who has claimed what ---
    employed = [person for person in corpus.people
                if person["exit_date"] is None]
    position_of = {a["person_id"]: a["position_id"] for a in corpus.assignments}
    job_of = {s["position_id"]: s["job_id"] for s in corpus.positions}

    assertion = 0
    for person in employed:
        # D40's coverage denominator is the employed population, so the share of them
        # holding any assertion is the parameter that decides whether a cluster is
        # reported or suppressed. Below it, the pillar must say insufficient coverage
        # rather than no supply.
        if rng.random() >= p.skill_coverage:
            continue
        job_id = job_of.get(position_of.get(person["person_id"]))
        job = by_job.get(job_id)
        if job is None:
            continue
        candidates = list(_FAMILY_TERMS[job["job_family"]])
        if job["job_level_rank"] >= 5:
            candidates += list(_SENIOR_TERMS)
        for label in rng.sample(candidates, k=min(len(candidates),
                                                  rng.randint(2, 4))):
            term_id = term_id_of.get(label)
            if term_id is None:
                continue
            asserted = p.history_start + timedelta(
                days=rng.randrange((p.history_end - p.history_start).days))
            expired = rng.random() < p.expired_assertion_share
            corpus.skill_assertions.append(mark({
                "assertion_id": f"assert-{assertion:06d}",
                "person_id": person["person_id"], "term_id": term_id,
                "proficiency": rng.randint(1, 5), "proficiency_scale_id": None,
                "evidence_type": _EVIDENCE[assertion % len(_EVIDENCE)],
                "asserted_at": asserted.isoformat(),
                # An expired certification is not present supply. `expires_at` before
                # `history_end` is what makes that testable.
                "expires_at": ((p.history_end - timedelta(days=rng.randrange(1, 400)))
                               .isoformat() if expired else None),
                "valid_from": asserted.isoformat(), "valid_to": None,
                "prov": prov("skill_assertions"),
            }))
            assertion += 1
