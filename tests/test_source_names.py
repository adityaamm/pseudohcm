"""D198 (F4) — the emulated HR system can speak its own field names."""
from __future__ import annotations

import json

import pseudohcm.emit as emit
import pseudohcm.generator as g


def lines(path):
    return [json.loads(l) for l in path.read_text().splitlines() if l]


def test_off_by_default_the_files_are_unchanged(tmp_path):
    c = g.generate(g.Parameters(employee_count=50, units=2, seed=1))
    emit.emit(c, tmp_path / "a")
    emit.emit(c, tmp_path / "b", source_names=False)
    for f in (tmp_path / "a").iterdir():
        assert f.read_text() == (tmp_path / "b" / f.name).read_text()


def test_on_every_named_field_is_sent_under_its_own_name_and_nothing_else_moves(tmp_path):
    c = g.generate(g.Parameters(employee_count=50, units=2, seed=1))
    emit.emit(c, tmp_path, source_names=True)
    person = lines(tmp_path / "Person.jsonl")[0]
    assert "worker_reference" in person and "display_ref" not in person
    assert person["worker_reference"] == c.people[0]["display_ref"]
    assert person["person_id"] == c.people[0]["person_id"]           # keys untouched
    assert person["valid_from"] == c.people[0]["valid_from"]         # temporal untouched
    assert len(person) == len(c.people[0])
