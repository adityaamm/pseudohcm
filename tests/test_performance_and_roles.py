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


SKILLED = Parameters(employee_count=400, units=8, seed=7, skill_terms=40)


@pytest.fixture(scope="module")
def skilled():
    return generate(SKILLED)


class TestTheSkillsVocabularyIsOffUnlessAskedFor:
    def test_no_skills_by_default(self):
        plain = generate(Parameters(employee_count=120, units=5, seed=3))
        for entity in ("CustomerSkillTerm", "SkillAssertion", "TaxonomyLink",
                       "CanonicalSkill", "RoleRequiredTerm"):
            assert plain.counts()[entity] == 0, entity

    def test_it_is_deterministic(self):
        a = generate(Parameters(employee_count=150, units=5, seed=11, skill_terms=30))
        b = generate(Parameters(employee_count=150, units=5, seed=11, skill_terms=30))
        for entity in ("customer_skill_terms", "skill_assertions", "taxonomy_links",
                       "canonical_skills", "role_required_terms"):
            assert getattr(a, entity) == getattr(b, entity), entity


class TestNothingHereIsRealStandardContent:
    """A guard rail, asserted rather than trusted.

    `canonical_skill` exists to hold O*NET or ESCO nodes under those standards'
    licences. Embedding real content in a synthetic harness would put third-party
    material in this repository under an attribution the harness cannot honour — and a
    reviewer comparing a label here against the real standard must find them obviously
    unrelated rather than plausibly similar.
    """

    def test_every_concept_id_is_marked_synthetic(self, skilled):
        """Doubly marked, and the second mark was not planned.

        `standard_concept_id` ends in `_id`, so Gate 7's poison pill prefixes it too —
        the value reads `PSEUDO::SYNTHETIC-ONET-00000`. Asserted as a substring rather
        than a prefix because of that, and it is a better outcome than the one intended:
        a reviewer sees both that the row is synthetic and that it came from the
        harness.
        """
        assert skilled.canonical_skills
        for node in skilled.canonical_skills:
            assert "SYNTHETIC-" in node["standard_concept_id"]
            assert "PSEUDO::" in node["standard_concept_id"]

    def test_every_node_says_so_in_its_attribution(self, skilled):
        for node in skilled.canonical_skills:
            assert "SYNTHETIC" in node["attribution"]
            assert "no third-party licence" in node["attribution"]

    def test_no_label_claims_to_be_a_real_standard_version(self, skilled):
        for node in skilled.canonical_skills:
            assert node["standard_version"] == "synthetic-0"


class TestTheVocabularyCanProduceAFinding:
    def test_terms_are_shared_across_families(self, skilled):
        """The property substitutability depends on. A vocabulary partitioned cleanly
        by family finds no substitutes anywhere and makes the component useless."""
        by_job = {j["job_id"]: j for j in skilled.jobs}
        req_job = {r["requirement_id"]: r["job_id"]
                   for r in skilled.role_requirements}
        by_family: dict[str, set] = {}
        for rt in skilled.role_required_terms:
            family = by_job[req_job[rt["requirement_id"]]]["job_family"]
            by_family.setdefault(family, set()).add(rt["term_id"])
        families = list(by_family.values())
        shared = [a & b for i, a in enumerate(families) for b in families[i + 1:]]
        assert any(shared), "no two families share a required term"

    def test_the_overlap_discriminates_rather_than_matching_everything(self, skilled):
        """Both failure directions matter. If no pair clears the 70% threshold the
        component always says 'irreplaceable'; if every pair clears it, always
        'replaceable'. Either is a component that cannot distinguish."""
        import itertools

        req_job = {r["requirement_id"]: r["job_id"]
                   for r in skilled.role_requirements}
        terms: dict[str, set] = {}
        for rt in skilled.role_required_terms:
            terms.setdefault(req_job[rt["requirement_id"]], set()).add(rt["term_id"])
        overlaps = [len(terms[a] & terms[b]) / len(terms[a])
                    for a, b in itertools.permutations(sorted(terms), 2) if terms[a]]
        above = sum(1 for o in overlaps if o >= 0.70)
        assert 0 < above < len(overlaps), (
            f"{above} of {len(overlaps)} ordered job pairs clear the threshold")

    def test_some_assertions_have_expired(self, skilled):
        """An expired certification is not present supply, and a corpus without any
        never proves the difference is applied."""
        expired = [a for a in skilled.skill_assertions if a["expires_at"]]
        assert 0 < len(expired) < len(skilled.skill_assertions)

    def test_some_terms_reach_no_standard(self, skilled):
        """D61 reports in the customer's own words and D40 suppresses a cluster below
        the coverage threshold. A vocabulary where every term maps cleanly exercises
        neither."""
        unmapped = [t for t in skilled.customer_skill_terms
                    if t["mapping_status"] == "UNMAPPED"]
        assert 0 < len(unmapped) < len(skilled.customer_skill_terms)
        linked = {link["term_id"] for link in skilled.taxonomy_links}
        assert all(t["term_id"] not in linked for t in unmapped)

    def test_coverage_is_partial_so_the_denominator_means_something(self, skilled):
        """Everyone holding an assertion makes D40's coverage suppression unreachable."""
        employed = [p for p in skilled.people if p["exit_date"] is None]
        holders = {a["person_id"] for a in skilled.skill_assertions}
        share = len(holders) / len(employed)
        assert 0.3 < share < 0.9, share

    def test_only_employed_people_hold_assertions(self, skilled):
        """G15's lesson. Assertions against leavers inflate the coverage numerator
        against a denominator that excludes them."""
        leavers = {p["person_id"] for p in skilled.people if p["exit_date"]}
        assert not {a["person_id"] for a in skilled.skill_assertions} & leavers

    def test_every_evidence_type_appears(self, skilled):
        """The evidence weighting orders these, and that ordering is a claim. A corpus
        using one type never tests it."""
        assert len({a["evidence_type"] for a in skilled.skill_assertions}) >= 4

    def test_the_crosswalk_group_is_shared_between_standards(self, skilled):
        """D61 keys a cluster on `crosswalk_group_id` and never on a label. A corpus
        where each standard has its own groups never exercises the crosswalk."""
        groups: dict[str, set] = {}
        for node in skilled.canonical_skills:
            groups.setdefault(node["crosswalk_group_id"], set()).add(node["standard"])
        assert any(len(s) > 1 for s in groups.values())

    def test_mapping_confidence_varies(self, skilled):
        """D13. A comparison built on weak links inherits their confidence, and a
        corpus where every mapping is certain never carries that caveat."""
        assert len({link["confidence"] for link in skilled.taxonomy_links}) > 3

    def test_some_mappings_are_human_confirmed_and_some_are_not(self, skilled):
        approved = [link for link in skilled.taxonomy_links if link["approved_by"]]
        assert 0 < len(approved) < len(skilled.taxonomy_links)


class TestRoleRequirementsCarryTheirTerms:
    def test_every_role_requires_something(self, skilled):
        required = {rt["requirement_id"] for rt in skilled.role_required_terms}
        assert len(required) == len(skilled.role_requirements)

    def test_essential_and_desirable_both_appear(self, skilled):
        """A requirement set where everything is essential makes every role look
        equally irreplaceable."""
        flags = {rt["is_essential"] for rt in skilled.role_required_terms}
        assert flags == {True, False}

    def test_senior_roles_require_more_than_junior_ones(self, skilled):
        by_job = {j["job_id"]: j for j in skilled.jobs}
        req_job = {r["requirement_id"]: r["job_id"]
                   for r in skilled.role_requirements}
        counts: dict[int, int] = {}
        for rt in skilled.role_required_terms:
            rank = by_job[req_job[rt["requirement_id"]]]["job_level_rank"]
            counts[rank] = counts.get(rank, 0) + 1
        assert counts[max(counts)] > counts[min(counts)]

    def test_every_required_term_is_a_real_term(self, skilled):
        """A dangling reference here would make substitutability compare against terms
        nobody declared."""
        known = {t["term_id"] for t in skilled.customer_skill_terms}
        assert all(rt["term_id"] in known for rt in skilled.role_required_terms)
