"""Kommandozeile: Exit-Codes, Formate, Audit-Befehle, SARIF."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from gradweight_autonomy import __version__
from gradweight_autonomy.audit import AuditTrail
from gradweight_autonomy.cli import main
from gradweight_autonomy.validator.docs import rules_markdown

ROOT = Path(__file__).resolve().parents[2]
EX = ROOT / "examples"
NEG = EX / "negativ"
KEY_HEX = bytes(range(16)).hex()  # Testschlüssel, kein Geheimnis


@pytest.fixture(autouse=True)
def _fixed_date(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GW_AUTONOMY_AS_OF", "2026-10-26")
    monkeypatch.chdir(ROOT)


def run(args: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    code = main(args)
    out, err = capsys.readouterr()
    return code, out, err


# --------------------------------------------------------------- validate
def test_validate_examples_directory_passes(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(["validate", "examples"], capsys)
    assert code == 0
    assert "0 nicht bestanden" in out
    assert out.rstrip().endswith("Exit-Code 0.")


def test_validate_negative_fails(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(["validate", str(NEG)], capsys)
    assert code == 1
    assert "nicht bestanden" in out


def test_fail_on_threshold(capsys: pytest.CaptureFixture[str]) -> None:
    case = str(EX / "gw2-kreditorenrechnung.json")  # eine Warnung
    assert run(["validate", case], capsys)[0] == 0
    assert run(["validate", "--fail-on", "warning", case], capsys)[0] == 1
    assert run(["validate", "--fail-on", "never", str(NEG)], capsys)[0] == 0
    assert (
        run(
            ["validate", "--fail-on", "note", str(EX / "gw2-bewerbungsvorsortierung.json")], capsys
        )[0]
        == 1
    )


def test_json_format(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(
        ["validate", "--format", "json", str(NEG / "n4-isolation-nur-behauptet.json")], capsys
    )
    doc = json.loads(out)
    assert code == 1
    assert doc["tool"] == {"name": "gradweight-autonomy", "version": __version__}
    assert doc["as_of"] == "2026-10-26"
    assert doc["summary"]["exit_code"] == 1
    first = doc["files"][0]
    assert first["passed"] is False
    assert {f["rule_id"] for f in first["findings"]} == {"GB-07", "GB-18"}
    assert all(f["line"] > 1 for f in first["findings"])


def test_output_file_keeps_text_on_stdout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "bericht.sarif"
    code, out, _ = run(["validate", "--format", "sarif", "-o", str(target), "examples"], capsys)
    assert code == 0
    assert "Dateien geprüft" in out
    assert json.loads(target.read_text(encoding="utf-8"))["version"] == "2.1.0"


def test_stdin(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(
        "sys.stdin", io.StringIO((EX / "gw0-marktforschung.json").read_text("utf-8"))
    )
    code, out, _ = run(["validate", "-"], capsys)
    assert code == 0
    assert "<stdin>" in out


def test_as_of_option_overrides_env(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(
        ["validate", "--as-of", "2028-01-01", str(EX / "gw4-c-teile-nachbestellen.json")], capsys
    )
    assert code == 0
    assert "GB-20" in out  # Notaus-Test ist dann älter als 365 Tage


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["validate", "fehlt.json"], "nicht gefunden"),
        (["validate", "docs"], "keine .json-Dateien"),
    ],
)
def test_usage_errors(args: list[str], message: str, capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = run(args, capsys)
    assert code == 2
    assert message in err


def test_invalid_env_date(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("GW_AUTONOMY_AS_OF", "gestern")
    code, _, err = run(["validate", "examples"], capsys)
    assert code == 2
    assert "GW_AUTONOMY_AS_OF" in err


def test_unreadable_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = tmp_path / "bad.json"
    bad.write_bytes(b"\xff\xfe\x00")
    code, _, err = run(["validate", str(bad)], capsys)
    assert code == 2
    assert "nicht lesbar" in err


def test_argparse_errors_return_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert run(["validate", "--as-of", "morgen", "examples"], capsys)[0] == 2
    assert run(["unbekannt"], capsys)[0] == 2
    assert run(["--version"], capsys)[1].strip() == f"gw-autonomy {__version__}"


# --------------------------------------------------------------- rules/schema
def test_rules_and_schema(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(["rules"], capsys)
    assert code == 0
    assert out.splitlines()[0].startswith("GB-01")
    assert run(["rules", "--format", "markdown"], capsys)[1] == rules_markdown()
    rules = json.loads(run(["rules", "--format", "json"], capsys)[1])
    assert rules[2]["severity_by_level"]["4"] == "error"
    schema = json.loads(run(["schema"], capsys)[1])
    jsonschema.Draft202012Validator.check_schema(schema)


# --------------------------------------------------------------- audit
def _trail(path: Path, key: bytes | None = None) -> tuple[int, str]:
    with AuditTrail(path, hmac_key=key) as trail:
        for i in range(3):
            trail.append(tenant="K", use_case="u", actor="a", action=f"s{i}")
        return trail.head()


def test_audit_verify_and_export(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "a.db"
    seq, head = _trail(db)
    code, out, _ = run(["audit", "verify", str(db), "--expect-head", f"{seq}:{head}"], capsys)
    assert code == 0
    assert "intakt" in out
    jsonl = tmp_path / "a.jsonl"
    code, out, _ = run(["audit", "export", str(db), "-o", str(jsonl)], capsys)
    assert code == 0
    assert f"Kopf {seq}:{head}" in out
    assert run(["audit", "verify-export", str(jsonl)], capsys)[0] == 0
    csv_path = tmp_path / "a.csv"
    assert run(["audit", "export", str(db), "-o", str(csv_path), "--format", "csv"], capsys)[0] == 0
    assert csv_path.read_text(encoding="utf-8").startswith("seq,")
    lines = jsonl.read_text(encoding="utf-8").splitlines()
    jsonl.write_text("\n".join(lines[:1] + lines[2:]) + "\n", encoding="utf-8")
    code, out, _ = run(["audit", "verify-export", str(jsonl)], capsys)
    assert code == 1
    assert "verletzt" in out


def test_audit_hmac_key_from_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    db = tmp_path / "a.db"
    _trail(db, bytes.fromhex(KEY_HEX))
    monkeypatch.setenv("GW_AUDIT_KEY", KEY_HEX)
    assert run(["audit", "verify", str(db), "--hmac-key-env", "GW_AUDIT_KEY"], capsys)[0] == 0
    code, _, err = run(["audit", "verify", str(db)], capsys)
    assert code == 2
    assert "passen nicht" in err


@pytest.mark.parametrize(
    ("env", "message"),
    [({}, "nicht gesetzt"), ({"K": "zz"}, "hexadezimal"), ({"K": "00ff"}, "16 Bytes")],
)
def test_audit_key_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    env: dict[str, str],
    message: str,
) -> None:
    monkeypatch.delenv("K", raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    code, _, err = run(["audit", "verify", "x.db", "--hmac-key-env", "K"], capsys)
    assert code == 2
    assert message in err


def test_audit_usage_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(["audit", "verify", str(tmp_path / "fehlt.db")], capsys)[0] == 2
    assert run(["audit", "verify-export", str(tmp_path / "fehlt.jsonl")], capsys)[0] == 2
    db = tmp_path / "a.db"
    _trail(db)
    code, _, err = run(["audit", "verify", str(db), "--expect-head", "1:abc"], capsys)
    assert code == 2
    assert "SEQ:HASH" in err
    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"seq": 1}\n', encoding="utf-8")
    assert run(["audit", "verify-export", str(bad)], capsys)[0] == 2


# --------------------------------------------------------------- SARIF
def _sarif(capsys: pytest.CaptureFixture[str], *paths: str) -> dict[str, Any]:
    code, out, _ = run(["validate", "--format", "sarif", *paths], capsys)
    assert code in (0, 1)
    doc: dict[str, Any] = json.loads(out)
    return doc


def test_sarif_structure(capsys: pytest.CaptureFixture[str]) -> None:
    doc = _sarif(capsys, "examples/negativ", "examples/gw2-kreditorenrechnung.json")
    run_ = doc["runs"][0]
    rules = run_["tool"]["driver"]["rules"]
    assert [r["id"] for r in rules] == [f"GB-{i:02d}" for i in range(1, 23)]
    assert all(r["help"]["markdown"].startswith(f"**{r['id']}") for r in rules)
    results = run_["results"]
    assert results
    fingerprints = set()
    for res in results:
        assert rules[res["ruleIndex"]]["id"] == res["ruleId"]
        loc = res["locations"][0]["physicalLocation"]
        assert loc["artifactLocation"]["uri"].startswith("examples/")
        assert loc["region"]["startLine"] >= 1
        assert res["level"] in ("error", "warning", "note")
        fingerprints.add(res["partialFingerprints"]["gwAutonomyFinding/v1"])
    assert len(fingerprints) == len(results)


def test_sarif_absolute_paths(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    inside = _sarif(capsys, str(EX / "gw2-kreditorenrechnung.json"))
    uri = inside["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"][
        "uri"
    ]
    assert uri == "examples/gw2-kreditorenrechnung.json"
    outside = tmp_path / "fall.json"
    outside.write_text((EX / "gw2-kreditorenrechnung.json").read_text("utf-8"), encoding="utf-8")
    doc = _sarif(capsys, str(outside))
    uri = doc["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"][
        "uri"
    ]
    assert uri.startswith("file://")


SARIF_SCHEMA = os.environ.get("GW_SARIF_SCHEMA")


@pytest.mark.skipif(
    not SARIF_SCHEMA, reason="GW_SARIF_SCHEMA nicht gesetzt (CI lädt das OASIS-Schema)"
)
def test_sarif_validates_against_oasis_schema(capsys: pytest.CaptureFixture[str]) -> None:
    schema = json.loads(Path(str(SARIF_SCHEMA)).read_text(encoding="utf-8"))
    for paths in (["examples"], ["examples/negativ"]):
        doc = _sarif(capsys, *paths)
        jsonschema.Draft4Validator(schema).validate(doc)


def test_text_report_is_deterministic(capsys: pytest.CaptureFixture[str]) -> None:
    first = run(["validate", "examples/negativ"], capsys)[1]
    second = run(["validate", "examples/negativ"], capsys)[1]
    assert first == second
    assert datetime.now(timezone.utc).year >= 2026


def test_python_dash_m_entry_point() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "gradweight_autonomy", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == f"gw-autonomy {__version__}"
