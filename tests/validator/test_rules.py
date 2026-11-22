"""Gezielte Tests je Regel (GB-01 bis GB-22) und Konsistenz von Regel-Metadaten."""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from gradweight_autonomy.validator import RULES, RULES_BY_ID, Severity, validate_case
from gradweight_autonomy.validator.engine import CaseReport, validate_path, validate_text
from gradweight_autonomy.validator.model import ALLOWED_AXES, LEVELS, min_level_for_axes

ROOT = Path(__file__).resolve().parents[2]
AS_OF = date(2026, 10, 26)
E, W, N = Severity.ERROR, Severity.WARNING, Severity.NOTE


def load(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((ROOT / "examples" / name).read_text(encoding="utf-8"))
    return data


def check(case: dict[str, Any]) -> CaseReport:
    return validate_case(case, as_of=AS_OF)


def hits(report: CaseReport, rule_id: str) -> list[tuple[Severity, str]]:
    return [(f.severity, f.message) for f in report.findings if f.rule_id == rule_id]


def severities(report: CaseReport, rule_id: str) -> set[Severity]:
    return {s for s, _ in hits(report, rule_id)}


def g4() -> dict[str, Any]:
    return load("gw4-c-teile-nachbestellen.json")


def g5() -> dict[str, Any]:
    return load("gw5-standardretouren.json")


def g2() -> dict[str, Any]:
    return load("gw2-kreditorenrechnung.json")


def add_evidence(case: dict[str, Any], eid: str, typ: str, day: str = "2026-09-01") -> None:
    case["evidence"].append(
        {"id": eid, "type": typ, "ref": f"evidence/x/{eid}.md", "date": day, "description": "d"}
    )


def implement(case: dict[str, Any], control: str, typ: str) -> None:
    eid = f"ev-{control.replace('_', '-')}"
    add_evidence(case, eid, typ)
    case["controls"][control] = {"status": "implemented", "evidence": [eid]}


# ------------------------------------------------------------------ Metadaten
def test_rule_registry_is_complete_and_ordered() -> None:
    assert [r.id for r in RULES] == [f"GB-{i:02d}" for i in range(1, 23)]
    assert len({r.name for r in RULES}) == len(RULES)
    for rule in RULES:
        assert len(rule.matrix) == len(LEVELS)
        assert rule.title
        assert rule.checks
        assert rule.rationale
        assert rule.remediation
        assert rule.references
        assert rule.condition
        assert rule.check is not None or rule.id == "GB-01"


def test_min_level_for_axes() -> None:
    assert min_level_for_axes("model", "per_action") == 2
    assert min_level_for_axes("model", "mandate") == 4
    assert min_level_for_axes("fixed_chain", "mandate") == 3
    assert min_level_for_axes("human", "mandate") is None
    for level, combos in ALLOWED_AXES.items():
        for combo in combos:
            fitting = min_level_for_axes(*combo)
            assert fitting is not None
            assert fitting <= level


# ------------------------------------------------------------------ GB-01
@pytest.mark.parametrize(
    ("text", "fragment"),
    [
        ("{", "Kein gültiges JSON"),
        ('{"a": 1, "a": 2}', "doppelt"),
        ('{"a": NaN}', "NaN ist in JSON nicht zulässig"),
        ("[]", "muss ein Objekt sein"),
    ],
)
def test_gb01_syntax_and_structure(text: str, fragment: str) -> None:
    report = validate_text(text, as_of=AS_OF)
    assert report.rule_ids() == {"GB-01"}
    assert any(fragment in f.message for f in report.findings)
    assert not report.ok


def test_gb01_schema_error_stops_other_rules() -> None:
    case = g4()
    case["level"] = 7
    report = check(case)
    assert report.rule_ids() == {"GB-01"}
    assert report.case_id == "gw4-c-teile-nachbestellen"


def test_json_decode_error_carries_position() -> None:
    report = validate_text('{\n  "a": 1,\n  oops\n}', as_of=AS_OF)
    assert (report.findings[0].line, report.findings[0].column) == (3, 3)


# ------------------------------------------------------------------ GB-02
def test_gb02_axes_not_allowed() -> None:
    case = g5()
    case["human_role"] = "mandate"
    report = check(case)
    assert severities(report, "GB-02") == {E}
    assert "frühestens Grad 4" in hits(report, "GB-02")[0][1]
    case["who_plans"] = "human"
    assert "keinen Grad" in hits(check(case), "GB-02")[0][1]


# ------------------------------------------------------------------ GB-03
@pytest.mark.parametrize("level", LEVELS)
def test_gb03_severity_follows_matrix(level: int) -> None:
    case = g4()
    case["level"] = level
    case["risk"]["foreign_input"] = True
    expected = RULES_BY_ID["GB-03"].severity_at(level)
    assert severities(check(case), "GB-03") == {expected}


def test_gb03_two_of_three_is_fine() -> None:
    assert hits(check(g4()), "GB-03") == []


# ------------------------------------------------------------------ GB-04
def test_gb04_ceiling() -> None:
    case = load("gw2-bewerbungsvorsortierung.json")
    assert severities(check(case), "GB-04") == {N}
    case["level"] = 3
    case["who_plans"] = "fixed_chain"
    case["human_role"] = "per_gate"
    assert E in severities(check(case), "GB-04")


# ------------------------------------------------------------------ GB-05 / GB-18
def test_gb05_foreign_text_without_isolation() -> None:
    case = g2()
    case["risk"]["customer_text_in_decisions"] = True
    assert severities(check(case), "GB-05") == {W}
    implement(case, "input_isolation", "architecture")
    assert severities(check(case), "GB-05") == {N}


def test_gb18_isolation_must_be_evidenced() -> None:
    case = g5()
    del case["controls"]["input_isolation"]
    report = check(case)
    assert severities(report, "GB-18") == {E}
    case["controls"]["input_isolation"] = {"status": "planned"}
    assert "erst geplant" in hits(check(case), "GB-18")[0][1]


# ------------------------------------------------------------------ GB-06
def test_gb06_safety() -> None:
    case = load("gw3-predictive-maintenance.json")
    assert severities(check(case), "GB-06") == {W}
    case = g4()
    case["risk"]["safety_critical"] = True
    assert severities(check(case), "GB-06") == {E}


# ------------------------------------------------------------------ GB-07
def test_gb07_adoption_rate() -> None:
    case = g2()
    del case["controls"]["adoption_rate_monitoring"]
    assert severities(check(case), "GB-07") == {E}
    level1 = load("gw1-produktwissen-innendienst.json")
    assert hits(check(level1), "GB-07") == []


# ------------------------------------------------------------------ GB-08
def test_gb08_mandate_required_and_enforced() -> None:
    case = g4()
    case["mandate"]["limits_in_system"] = False
    assert severities(check(case), "GB-08") == {E}
    del case["mandate"]
    report = check(case)
    assert any("fehlt" in m for _, m in hits(report, "GB-08"))


# ------------------------------------------------------------------ GB-09
def test_gb09_money_limit() -> None:
    case = g4()
    del case["mandate"]["money_limit"]
    assert severities(check(case), "GB-09") == {E}
    case = g5()
    del case["mandate"]
    assert any("kein Mandat" in m for _, m in hits(check(case), "GB-09"))
    assert hits(check(g2()), "GB-09") == []  # Freigabe je Aktion


# ------------------------------------------------------------------ GB-10
def test_gb10_level1_without_external_effect() -> None:
    case = load("gw1-produktwissen-innendienst.json")
    case["risk"]["external_action"] = True
    assert severities(check(case), "GB-10") == {E}


# ------------------------------------------------------------------ GB-11/12/13
@pytest.mark.parametrize(
    ("control", "rule_id", "severity"),
    [
        ("audit_log", "GB-11", E),
        ("agent_identity", "GB-11", E),
        ("kill_switch", "GB-12", E),
        ("automatic_rollback", "GB-12", E),
        ("incident_process", "GB-12", E),
        ("change_management", "GB-12", W),
        ("shadow_run", "GB-13", E),
        ("proposal_mode_first", "GB-13", E),
    ],
)
def test_level_requirements(control: str, rule_id: str, severity: Severity) -> None:
    case = g4()
    case["controls"][control]["status"] = "planned"
    report = check(case)
    assert (severity, "Kontrolle «") in [(s, m[:11]) for s, m in hits(report, rule_id)]
    assert any(control in m for _, m in hits(report, rule_id))


def test_exception_only_needs_grade5_controls_on_any_level() -> None:
    case = load("gw3-predictive-maintenance.json")
    case["human_role"] = "exception_only"
    messages = [m for _, m in hits(check(case), "GB-11")]
    assert any("exception_queue" in m for m in messages)
    assert any("sampling_audit" in m for m in messages)


def test_not_applicable_does_not_satisfy_requirement() -> None:
    case = g4()
    case["controls"]["kill_switch"] = {"status": "not_applicable", "rationale": "kein Bedarf"}
    assert any("nicht anwendbar" in m for _, m in hits(check(case), "GB-12"))


# ------------------------------------------------------------------ GB-14
def test_gb14_measurement() -> None:
    case = g4()
    del case["measurement"]["k"]
    assert severities(check(case), "GB-14") == {E}
    case["measurement"]["k"] = 1
    assert severities(check(case), "GB-14") == {W}
    case = load("gw3-predictive-maintenance.json")
    case["controls"]["shadow_run"]["status"] = "planned"
    assert severities(check(case), "GB-14") == {W}
    del case["measurement"]
    assert severities(check(case), "GB-14") == {E}


# ------------------------------------------------------------------ GB-15
def test_gb15_data_class_and_residency() -> None:
    case = g4()
    case["data"]["classification"] = "geheim"
    msgs = [m for _, m in hits(check(case), "GB-15")]
    assert len(msgs) == 2  # Grad 4 und Standort
    case = load("gw0-marktforschung.json")
    case["risk"]["sensitive_data"] = True
    assert severities(check(case), "GB-15") == {E}
    case = g2()
    case["data"]["residency"] = "public"
    assert severities(check(case), "GB-15") == {W}


# ------------------------------------------------------------------ GB-16
def test_gb16_steps() -> None:
    case = g2()
    case["steps"][2]["human_role"] = "mandate"
    report = check(case)
    assert "frühestens Grad 4" in hits(report, "GB-16")[0][1]
    case["steps"][2]["human_role"] = "none"
    assert "keine menschliche Rolle" in hits(check(case), "GB-16")[0][1]
    case["steps"][2]["money"] = case["steps"][2]["external"] = case["steps"][2]["state_change"] = (
        False
    )
    assert hits(check(case), "GB-16") == []


# ------------------------------------------------------------------ GB-17
@pytest.mark.parametrize(
    ("mutate", "fragment"),
    [
        (lambda c: c["risk"].update(external_action=False), "money_effect=true"),
        (
            lambda c: c["risk"].update(
                customer_facing=True, external_action=False, money_effect=False
            ),
            "customer_facing=true",
        ),
        (lambda c: c["risk"].update(sensitive_data=False), "Datenklasse 'vertraulich'"),
        (
            lambda c: c["data"].update(special_categories=True, personal_data=False),
            "personal_data=true",
        ),
        (
            lambda c: c["data"].update(automated_individual_decisions=True, personal_data=False),
            "automated_individual_decisions",
        ),
    ],
)
def test_gb17_consistency(mutate: Callable[[dict[str, Any]], None], fragment: str) -> None:
    case = g2()
    mutate(case)
    assert any(fragment in m for _, m in hits(check(case), "GB-17"))


def test_gb17_special_categories_need_confidential_class() -> None:
    case = g4()
    case["data"].update(personal_data=True, special_categories=True)
    assert any("mindestens" in m for _, m in hits(check(case), "GB-17"))
    case = load("gw0-marktforschung.json")
    case["data"]["personal_data"] = True
    assert severities(check(case), "GB-17") == {W}


# ------------------------------------------------------------------ GB-19
def test_gb19_evidence_rules() -> None:
    case = g4()
    case["controls"]["audit_log"]["evidence"] = []
    case["controls"]["kill_switch"]["evidence"] = ["ct-audit"]  # falscher Typ
    case["controls"]["agent_identity"]["evidence"] = ["gibt-es-nicht"]
    case["controls"]["change_management"] = {"status": "not_applicable"}
    case["evidence"].append(dict(case["evidence"][0]))  # doppelte ID
    case["mandate"]["evidence"] = []
    case["measurement"]["evidence"] = ["ct-audit"]
    msgs = [m for _, m in hits(check(case), "GB-19")]
    assert any("ohne Nachweis" in m and "Audit-Trail" in m for m in msgs)
    assert any("Typ 'config'" in m and "Notaus" in m for m in msgs)
    assert any("'gibt-es-nicht' ist in 'evidence' nicht definiert" in m for m in msgs)
    assert any("ohne Begründung" in m for m in msgs)
    assert any("doppelt" in m for m in msgs)
    assert any("Mandatsgrenzen" in m for m in msgs)
    assert any("Messung: Nachweis 'ct-audit'" in m for m in msgs)


def test_gb19_unreferenced_evidence_is_note() -> None:
    case = g4()
    add_evidence(case, "lose", "policy")
    assert (N, "Nachweis 'lose' wird von keiner Angabe referenziert.") in hits(check(case), "GB-19")


# ------------------------------------------------------------------ GB-20
def test_gb20_dates() -> None:
    case = g4()
    case["evidence"][0]["date"] = "2026-02-30"
    case["evidence"][1]["date"] = "2027-01-01"
    notaus = next(e for e in case["evidence"] if e["id"] == "ct-notaus")
    notaus["date"] = "2025-09-01"
    msgs = hits(check(case), "GB-20")
    assert (
        E,
        "Nachweis 'ct-notaus' ist 420 Tage alt; für «Notaus (getestet)» gelten höchstens 365 Tage.",
    ) not in msgs
    assert any(s is W and "420 Tage" in m for s, m in msgs)
    assert any(s is E and "ungültiges Datum" in m for s, m in msgs)
    assert any(s is E and "nach dem Stichtag" in m for s, m in msgs)


def _write_case(tmp_path: Path, case: dict[str, Any]) -> Path:
    path = tmp_path / "fall.json"
    path.write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def test_gb20_file_checks(tmp_path: Path) -> None:
    case = g4()
    (tmp_path / "evidence").mkdir()
    for item in case["evidence"]:
        item["ref"] = f"evidence/{item['id']}.md"
        (tmp_path / item["ref"]).write_text(f"Nachweis {item['id']}", encoding="utf-8")
        item.pop("sha256", None)
    good = hashlib.sha256(b"Nachweis ct-notaus").hexdigest()
    case["evidence"][3]["sha256"] = good if case["evidence"][3]["id"] == "ct-notaus" else "0" * 64
    path = _write_case(tmp_path, case)
    assert validate_path(path, as_of=AS_OF, check_evidence_files=True).ok

    case["evidence"][0]["ref"] = "evidence/fehlt.md"
    case["evidence"][1]["sha256"] = "0" * 64
    case["evidence"][2]["ref"] = "https://dms.example.ch/dok/1"
    path = _write_case(tmp_path, case)
    report = validate_path(path, as_of=AS_OF, check_evidence_files=True)
    msgs = [m for _, m in hits(report, "GB-20")]
    assert any("nicht gefunden" in m for m in msgs)
    assert any("SHA-256" in m for m in msgs)
    assert len(msgs) == 2  # URL wird nicht geprüft
    assert validate_path(path, as_of=AS_OF, check_evidence_files=False).ok


def test_gb20_symlink_escape(tmp_path: Path) -> None:
    case = g4()
    outside = tmp_path / "aussen.md"
    outside.write_text("x", encoding="utf-8")
    inner = tmp_path / "fall"
    inner.mkdir()
    (inner / "link.md").symlink_to(outside)
    for item in case["evidence"]:
        item["ref"] = "link.md"
        item.pop("sha256", None)
    path = inner / "fall.json"
    path.write_text(json.dumps(case), encoding="utf-8")
    report = validate_path(path, as_of=AS_OF, check_evidence_files=True)
    assert any("hinaus" in m for _, m in hits(report, "GB-20"))


# ------------------------------------------------------------------ GB-21
def test_gb21_automated_decisions() -> None:
    case = g5()
    case["data"]["automated_individual_decisions"] = True
    assert severities(check(case), "GB-21") == {E}
    case["controls"]["human_review_on_request"] = {
        "status": "not_applicable",
        "rationale": "Art. 21 Abs. 3 lit. b: ausdrückliche Einwilligung",
    }
    assert hits(check(case), "GB-21") == []
    implement(case, "human_review_on_request", "runbook")
    assert hits(check(case), "GB-21") == []


# ------------------------------------------------------------------ GB-22
def test_gb22_high_risk() -> None:
    case = load("gw2-bewerbungsvorsortierung.json")
    assert hits(check(case), "GB-22") == []
    del case["controls"]["human_oversight"]
    del case["regulatory"]["eu_ai_act_category"]
    msgs = hits(check(case), "GB-22")
    assert any(s is E and "Art. 14" in m for s, m in msgs)
    assert any(s is W and "Fundstelle" in m for s, m in msgs)
    case = g4()
    case["regulatory"] = {"eu_ai_act_high_risk": True, "eu_ai_act_category": "Anhang III Nr. 5"}
    implement(case, "human_oversight", "runbook")
    assert severities(check(case), "GB-22") == {W}


# ------------------------------------------------------------------ Bericht
def test_report_helpers() -> None:
    case = copy.deepcopy(g2())
    report = check(case)
    assert report.ok
    assert report.fails(W)
    assert not report.fails(E)
    assert not report.fails(None)
    assert report.count(W) == 1
    assert report.errors == ()
    assert report.findings[0].as_dict()["rule_id"] == "GB-03"
