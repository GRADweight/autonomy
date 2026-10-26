"""Ausgabeformate: Text für Menschen, JSON für Werkzeuge, SARIF 2.1.0 für Code-Scanning."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any

from gradweight_autonomy import __version__
from gradweight_autonomy.validator.engine import CaseReport
from gradweight_autonomy.validator.model import LEVEL_NAMES, Severity
from gradweight_autonomy.validator.rules import RULES, RULES_BY_ID

TOOL_NAME = "gradweight-autonomy"
INFORMATION_URI = "https://github.com/GRADweight/autonomy"
RULES_DOC_URI = f"{INFORMATION_URI}/blob/main/docs/regeln.md"
SARIF_SCHEMA = (
    "https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/schemas/sarif-schema-2.1.0.json"
)
JSON_REPORT_VERSION = "1"


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _counts_text(errors: int, warnings: int, notes: int) -> str:
    return ", ".join(
        (
            _plural(errors, "Fehler", "Fehler"),
            _plural(warnings, "Warnung", "Warnungen"),
            _plural(notes, "Hinweis", "Hinweise"),
        )
    )


def render_text(
    reports: Sequence[CaseReport], *, threshold: Severity | None, exit_code: int
) -> str:
    """Lesbare Ausgabe (Deutsch)."""
    lines: list[str] = []
    for report in reports:
        head = report.source
        if report.case_id:
            level = (
                f", Grad {report.level} ({LEVEL_NAMES[report.level]})"
                if report.level is not None and report.level in LEVEL_NAMES
                else ""
            )
            head += f"  [{report.case_id}{level}]"
        lines.append(head)
        for f in report.findings:
            lines.append(f"  {f.line}:{f.column}  {f.severity.label:<8} {f.rule_id}  {f.message}")
        verdict = "nicht bestanden" if report.fails(threshold) else "bestanden"
        counts = _counts_text(
            report.count(Severity.ERROR),
            report.count(Severity.WARNING),
            report.count(Severity.NOTE),
        )
        lines.append(f"  Ergebnis: {verdict} ({counts})")
        lines.append("")
    total = _counts_text(
        sum(r.count(Severity.ERROR) for r in reports),
        sum(r.count(Severity.WARNING) for r in reports),
        sum(r.count(Severity.NOTE) for r in reports),
    )
    failed = sum(1 for r in reports if r.fails(threshold))
    lines.append(
        f"{_plural(len(reports), 'Datei', 'Dateien')} geprüft, {failed} nicht bestanden "
        f"({total}). Exit-Code {exit_code}."
    )
    return "\n".join(lines) + "\n"


def render_json(
    reports: Sequence[CaseReport], *, threshold: Severity | None, as_of: date, exit_code: int
) -> str:
    """Maschinenlesbarer Bericht."""
    doc: dict[str, Any] = {
        "report_version": JSON_REPORT_VERSION,
        "tool": {"name": TOOL_NAME, "version": __version__},
        "as_of": as_of.isoformat(),
        "fail_on": threshold.value if threshold else "never",
        "files": [
            {
                "path": r.source,
                "case_id": r.case_id,
                "level": r.level,
                "passed": not r.fails(threshold),
                "counts": {s.value: r.count(s) for s in Severity},
                "findings": [f.as_dict() for f in r.findings],
            }
            for r in reports
        ],
        "summary": {
            "files": len(reports),
            "failed": sum(1 for r in reports if r.fails(threshold)),
            **{s.value: sum(r.count(s) for r in reports) for s in Severity},
            "exit_code": exit_code,
        },
    }
    return json.dumps(doc, ensure_ascii=False, indent=2) + "\n"


def _sarif_rule(rule_id: str) -> dict[str, Any]:
    rule = RULES_BY_ID[rule_id]
    refs = "\n".join(f"- {r}" for r in rule.references)
    help_md = (
        f"**{rule.id} {rule.title}**\n\n"
        f"Prüft: {rule.checks}\n\n"
        f"Warum: {rule.rationale}\n\n"
        f"Behebung: {rule.remediation}\n\n"
        f"Referenzen:\n{refs}\n"
    )
    help_text = (
        f"{rule.id} {rule.title}. Prüft: {rule.checks} Warum: {rule.rationale} "
        f"Behebung: {rule.remediation}"
    )
    return {
        "id": rule.id,
        "name": rule.name,
        "shortDescription": {"text": f"{rule.id} {rule.title}"},
        "fullDescription": {"text": rule.checks},
        "helpUri": f"{RULES_DOC_URI}#{rule.id.lower()}",
        "help": {"text": help_text, "markdown": help_md},
        "defaultConfiguration": {"level": rule.default_severity.value},
        "properties": {"tags": ["ai-governance", "policy-as-code"], "precision": "very-high"},
    }


def _artifact_uri(source: str) -> str:
    path = Path(source)
    if path.is_absolute():
        try:
            path = path.relative_to(Path.cwd())
        except ValueError:
            return path.as_uri()
    return str(PurePosixPath(*path.parts)) if path.parts else source


def render_sarif(reports: Sequence[CaseReport]) -> str:
    """SARIF 2.1.0 (ein Run, alle Regeln im Treiber)."""
    rule_ids = [rule.id for rule in RULES]
    index = {rid: i for i, rid in enumerate(rule_ids)}
    results: list[dict[str, Any]] = []
    for report in reports:
        uri = _artifact_uri(report.source)
        for f in report.findings:
            fingerprint = hashlib.sha256(
                f"{f.rule_id}|{uri}|{f.pointer}|{f.message}".encode()
            ).hexdigest()
            results.append(
                {
                    "ruleId": f.rule_id,
                    "ruleIndex": index[f.rule_id],
                    "level": f.severity.value,
                    "message": {"text": f.message},
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {"uri": uri, "uriBaseId": "%SRCROOT%"},
                                "region": {"startLine": f.line, "startColumn": f.column},
                            },
                            "logicalLocations": [
                                {
                                    "name": f.pointer or "/",
                                    "fullyQualifiedName": f"{report.case_id or uri}#{f.pointer}",
                                    "kind": "object",
                                }
                            ],
                        }
                    ],
                    "partialFingerprints": {"gwAutonomyFinding/v1": fingerprint},
                }
            )
    doc = {
        "$schema": SARIF_SCHEMA,
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": TOOL_NAME,
                        "version": __version__,
                        "semanticVersion": __version__,
                        "informationUri": INFORMATION_URI,
                        "rules": [_sarif_rule(rid) for rid in rule_ids],
                    }
                },
                "columnKind": "unicodeCodePoints",
                "results": results,
            }
        ],
    }
    return json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
