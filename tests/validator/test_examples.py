"""Vertrag der Beispiele: Positive bestehen, Negative scheitern an genau ihren Regeln."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from gradweight_autonomy.validator import Severity, validate_path

ROOT = Path(__file__).resolve().parents[2]
AS_OF = date(2026, 10, 26)
POSITIVE = sorted((ROOT / "examples").glob("*.json"))
NEGATIVE = {
    "n1-dunkelbuchung-grad5.json": {"GB-03", "GB-09", "GB-11", "GB-12", "GB-13", "GB-14"},
    "n2-geldwirkung-ohne-aussenwirkung.json": {"GB-07", "GB-12", "GB-14", "GB-17"},
    "n3-kontrollen-ohne-nachweis.json": {"GB-07", "GB-19", "GB-20"},
    "n4-isolation-nur-behauptet.json": {"GB-07", "GB-18"},
}


def test_example_inventory() -> None:
    names = {p.name for p in POSITIVE}
    assert {f"gw{level}" for level in range(6)} <= {n[:3] for n in names}
    assert set(NEGATIVE) == {p.name for p in (ROOT / "examples" / "negativ").glob("*.json")}


@pytest.mark.parametrize("path", POSITIVE, ids=lambda p: p.stem)
def test_positive_examples_pass_with_evidence_files(path: Path) -> None:
    report = validate_path(path, as_of=AS_OF, check_evidence_files=True)
    assert report.ok, [f.as_dict() for f in report.errors]
    assert report.case_id == path.stem


@pytest.mark.parametrize(("name", "expected"), sorted(NEGATIVE.items()))
def test_negative_examples_fail_for_the_intended_reasons(name: str, expected: set[str]) -> None:
    report = validate_path(ROOT / "examples" / "negativ" / name, as_of=AS_OF)
    assert not report.ok
    assert report.rule_ids(Severity.ERROR) == expected


def test_example_evidence_files_are_marked_fictional() -> None:
    files = list((ROOT / "examples" / "evidence").rglob("*.md"))
    assert files
    for f in files:
        assert "Fiktives Beispiel" in f.read_text(encoding="utf-8"), f
