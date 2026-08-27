"""The P2.6 entities — and whether the corpus can actually fail the checks it feeds.

WHY THIS FILE IS MOSTLY ABOUT DISTRIBUTIONS

Generating rows is the easy half. The half that matters is whether the rows can produce
a finding.

A generator drawing every rating rank uniformly would hand Pillar E a perfectly
calibrated organisation. The integrity pillar would report no compression, no inflation
and no divergence anywhere — correctly, from data that had none — and the whole pillar
would pass its integration test while being incapable of failing it. Likewise a
uniformly random dependency graph gives every role the same centrality, so a ranking
over it means nothing.

That is the harness form of the confident empty answer this project keeps meeting. D66
is the precedent: redundancy and unit closure exist as injectors because no fixture had
ever produced an involuntary exit, which is how D65 survived 985 passing tests.

So these tests assert that the corpus contains the *shapes* the pillars exist to find.
"""
from __future__ import annotations

from collections import Counter
from datetime import date

import pytest

from pseudohcm.generator import Parameters, generate

SMALL = Parameters(employee_count=400, units=8, seed=7, rating_cycles=3)


@pytest.fixture(scope="module")
def corpus():
    return generate(SMALL)


class TestItIsOffUnlessAskedFor:
    def test_no_performance_data_by_default(self):
        """Existing tests keep the corpus they were written against. A generator that
        silently starts emitting five new entity types breaks assertions that were
        right when somebody wrote them."""
        plain = generate(Parameters(employee_count=120, units=5, seed=3))
        assert plain.counts()["PerformanceEvent"] == 0
        assert plain.counts()["RatingScale"] == 0
        assert plain.counts()["PerformanceCycle"] == 0

    def test_role_assessment_is_always_generated(self):
        """Role requirements and interactions do not depend on a cycle count — they
        describe the job architecture, which exists whether or not anyone was rated."""
        plain = generate(Parameters(employee_count=120, units=5, seed=3))
        assert plain.counts()["RoleRequirement"] == len(plain.jobs)
        assert plain.counts()["RoleInteraction"] > 0

    def test_the_same_parameters_give_the_same_corpus(self):
        a = generate(Parameters(employee_count=150, units=5, seed=11, rating_cycles=2))
        b = generate(Parameters(employee_count=150, units=5, seed=11, rating_cycles=2))
        assert a.counts() == b.counts()
        assert a.performance_events == b.performance_events
        assert a.role_interactions == b.role_interactions


class TestTheRatingsCanProduceAFinding:
    def test_the_ranks_are_not_uniform(self, corpus):
        """The whole point. Uniform ranks make the integrity pillar untestable."""
        counts = Counter(e["rating_rank"] for e in corpus.performance_events)
        assert len(counts) > 1
        spread = max(counts.values()) / min(counts.values())
        assert spread > 2, f"ranks are near-uniform ({dict(counts)}), so no unit can " \
                           "diverge from the intended distribution"

    def test_units_differ_from_one_another(self, corpus):
        """A compressed unit and an inflated one both exist, or the pillar has nothing
        to distinguish."""
        unit_of = {p["position_id"]: p["org_unit_id"] for p in corpus.positions}
        by_unit: dict[str, list[int]] = {}
        for event in corpus.performance_events:
            unit = unit_of.get(event["position_id"])
            if unit:
                by_unit.setdefault(unit, []).append(event["rating_rank"])
        means = {u: sum(r) / len(r) for u, r in by_unit.items() if len(r) >= 8}
        assert len(means) >= 2
        assert max(means.values()) - min(means.values()) > 0.4, (
            "every unit rates alike, so no unit can be found anomalous")

    def test_at_least_one_unit_is_compressed(self, corpus):
        """`spread <= 0.5` is what fires COMPRESSION. A corpus where every unit uses
        the whole scale never exercises the finding."""
        unit_of = {p["position_id"]: p["org_unit_id"] for p in corpus.positions}
        by_unit: dict[str, set[int]] = {}
        for event in corpus.performance_events:
            unit = unit_of.get(event["position_id"])
            if unit:
                by_unit.setdefault(unit, set()).add(event["rating_rank"])
        assert any(len(distinct) / SMALL.rating_points <= 0.6
                   for distinct in by_unit.values())

    def test_some_ratings_carry_no_position(self, corpus):
        """`performance_event.position_id` is nullable, so the unattributable path is
        real. Pillar E counts these rather than dropping them, and a corpus where every
        rating resolves to a unit never proves it."""
        orphans = [e for e in corpus.performance_events if e["position_id"] is None]
        assert 0 < len(orphans) < len(corpus.performance_events) * 0.1

    def test_the_scale_states_its_intended_distribution(self, corpus):
        """Without it the pillar correctly reports 'no intended distribution recorded'
        and the divergence half of the check goes untested."""
        scale = corpus.rating_scales[0]
        assert len(scale["target_distribution"]) == scale["point_count"]
        assert abs(sum(scale["target_distribution"]) - 1.0) < 0.01


class TestTheCyclesAreWellFormed:
    def test_each_cycle_is_distinct(self, corpus):
        """This failed on the first run. `history_end.year - cycle_index` with a
        mid-year end date resolved cycles 0 and 1 to the same 31 December — the same
        `period_end` and the same `cycle_id`, which is the primary key of
        `performance_cycle`. Everyone would have been rated twice in one cycle."""
        ids = [c["cycle_id"] for c in corpus.performance_cycles]
        assert len(set(ids)) == len(ids)
        ends = [c["period_end"] for c in corpus.performance_cycles]
        assert len(set(ends)) == len(ends)

    def test_no_cycle_runs_past_the_corpus(self, corpus):
        for cycle in corpus.performance_cycles:
            assert date.fromisoformat(cycle["period_end"]) < SMALL.history_end
            assert cycle["period_end"] > cycle["period_start"]

    def test_nobody_is_rated_before_they_joined_or_after_they_left(self, corpus):
        """D67's inclusive `exit_date`: somebody whose last day is the cycle end date
        did work that cycle and is rated."""
        ends = {c["cycle_id"]: date.fromisoformat(c["period_end"])
                for c in corpus.performance_cycles}
        people = {p["person_id"]: p for p in corpus.people}
        for event in corpus.performance_events:
            person = people[event["person_id"]]
            end = ends[event["cycle_id"]]
            assert date.fromisoformat(person["hire_date_current"]) <= end
            if person["exit_date"]:
                assert date.fromisoformat(person["exit_date"]) >= end

    def test_one_rating_per_person_per_cycle(self, corpus):
        seen = Counter((e["person_id"], e["cycle_id"])
                       for e in corpus.performance_events)
        assert max(seen.values()) == 1


class TestTheGraphRespectsTheSchemaConstraints:
    def test_no_role_depends_on_itself(self, corpus):
        """`role_interaction_no_self_dependency`. A self-edge inflates a role's own
        in-degree — the exact component it must not be able to inflate."""
        assert not [e for e in corpus.role_interactions
                    if e["from_job_id"] == e["to_job_id"]]

    def test_every_inferred_edge_names_its_model(self, corpus):
        """`role_interaction_derived_edges_name_their_model`, Doc 03C §6.1. An
        unreproducible input to a score that ranks roles is not defensible."""
        assert not [e for e in corpus.role_interactions
                    if e["basis"] == "STRUCTURAL_INFERENCE" and not e["model_version"]]

    def test_all_three_bases_appear(self, corpus):
        """Including the one the constraint above guards. A corpus of only stated
        edges never tests it."""
        assert {e["basis"] for e in corpus.role_interactions} == {
            "STATED_IN_DESCRIPTION", "IDEOM_CONFIRMED", "STRUCTURAL_INFERENCE"}

    def test_strength_and_confidence_are_in_range(self, corpus):
        for edge in corpus.role_interactions:
            assert 0 <= edge["strength"] <= 1
            assert 0 <= edge["confidence"] <= 1

    def test_the_graph_has_hubs_rather_than_being_flat(self, corpus):
        """Direction is biased up the level ranks so seniors accumulate dependants. A
        uniformly random graph gives every role the same centrality and makes the
        ranking meaningless."""
        dependants = Counter(e["to_job_id"] for e in corpus.role_interactions)
        assert max(dependants.values()) >= 2 * min(dependants.values())


class TestRoleRequirementsCarryWhatD77Needs:
    def test_one_per_job_code_not_one_per_seat(self, corpus):
        """A requirement per position would be 50,000 rows describing 25 roles, and
        substitutability would compare a role against itself 24,000 times."""
        assert len(corpus.role_requirements) == len(corpus.jobs)
        assert all(r["position_id"] is None for r in corpus.role_requirements)

    def test_all_four_description_qualities_appear(self, corpus):
        """THIN kept vanishing while this was being written. The Bresenham selection
        picked only even indices, so every thin role came out ABSENT; the first fix
        keyed on `len(role_requirements)`, which equals the index because one row is
        appended per job — the same bug in different clothing."""
        assert {r["description_quality"] for r in corpus.role_requirements} == {
            "RICH", "ADEQUATE", "THIN", "ABSENT"}

    def test_rich_and_adequate_descriptions_actually_have_text(self, corpus):
        """The migration refuses otherwise, and a quality label the text does not
        support is the same lie as a figure without its caveat."""
        assert not [r for r in corpus.role_requirements
                    if r["description_quality"] in ("RICH", "ADEQUATE")
                    and not r["description_text"]]

    def test_the_thin_share_is_close_to_the_parameter(self, corpus):
        thin = [r for r in corpus.role_requirements
                if r["description_quality"] in ("THIN", "ABSENT")]
        share = len(thin) / len(corpus.role_requirements)
        assert abs(share - SMALL.thin_description_share) < 0.05

    def test_the_default_share_sits_below_the_organisation_caveat(self, corpus):
        """`organisation_caveat` fires above 40%. The default belongs below it so a
        test that wants the caveat has to ask for it."""
        assert SMALL.thin_description_share < 0.40

    def test_thin_roles_are_spread_across_families(self, corpus):
        """Taking the first N would make every thin role an Engineering one, since
        jobs are generated family by family — and the caveat would then be a statement
        about one function rather than about documentation."""
        by_job = {j["job_id"]: j for j in corpus.jobs}
        families = {by_job[r["job_id"]]["job_family"] for r in corpus.role_requirements
                    if r["description_quality"] in ("THIN", "ABSENT")}
        assert len(families) >= 3

    def test_decision_rights_widen_with_level(self, corpus):
        """The component exists to recognise authority that is not budget — a
        principal engineer owning an architecture decision holds real authority."""
        by_job = {j["job_id"]: j for j in corpus.jobs}
        pairs = [(by_job[r["job_id"]]["job_level_rank"], len(r["decision_rights"]))
                 for r in corpus.role_requirements]
        lowest = min(rank for rank, _ in pairs)
        highest = max(rank for rank, _ in pairs)
        assert dict(pairs)[highest] > dict(pairs)[lowest]
