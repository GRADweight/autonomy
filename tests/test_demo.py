"""Demo: läuft durch, ist reproduzierbar und nutzt denselben Fall wie examples/."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gradweight_autonomy.cli import main
from gradweight_autonomy.demo import DEMO_CASE, run_demo

ROOT = Path(__file__).resolve().parents[1]


def test_demo_case_matches_example() -> None:
    example = json.loads((ROOT / "examples" / "gw2-kreditorenrechnung.json").read_text("utf-8"))
    example.pop("$schema")
    assert example == DEMO_CASE


def test_demo_runs_and_is_reproducible(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    assert run_demo(tmp_path / "a") == 0
    first = capsys.readouterr().out
    assert run_demo(tmp_path / "b") == 0
    second = capsys.readouterr().out
    assert first == second
    for expected in (
        "Abgleich bestanden",
        "Belegprüfung bestanden.",
        "Vier-Augen-Prinzip",
        "POST /4.0/purchase/bills",
        "DELETE /4.0/purchase/bills/",
        "Kette intakt",
        "Kette verletzt",
        "Demo erfolgreich.",
    ):
        assert expected in first


def test_demo_via_cli(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["demo"]) == 0
    assert "Demo erfolgreich." in capsys.readouterr().out
