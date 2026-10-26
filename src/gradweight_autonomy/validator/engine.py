"""Auswertung eines Falls: Syntax, Schema, Regeln, Positionen."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from gradweight_autonomy.validator.jsonpos import PointerLocator
from gradweight_autonomy.validator.jsonschema_lite import usecase_validator
from gradweight_autonomy.validator.model import Severity
from gradweight_autonomy.validator.rules import RULES, RULES_BY_ID, CaseContext


@dataclass(frozen=True)
class Finding:
    """Ein Befund mit Regel, Schweregrad und Fundstelle."""

    rule_id: str
    severity: Severity
    message: str
    pointer: str = ""
    line: int = 1
    column: int = 1

    def as_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "message": self.message,
            "pointer": self.pointer,
            "line": self.line,
            "column": self.column,
        }


@dataclass(frozen=True)
class CaseReport:
    """Ergebnis für eine Datei bzw. einen Fall."""

    source: str
    case_id: str | None
    level: int | None
    findings: tuple[Finding, ...] = field(default_factory=tuple)

    def count(self, severity: Severity) -> int:
        return sum(1 for f in self.findings if f.severity is severity)

    @property
    def errors(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.severity is Severity.ERROR)

    @property
    def ok(self) -> bool:
        """``True`` ohne Fehler (Warnungen und Hinweise erlaubt)."""
        return not self.errors

    def fails(self, threshold: Severity | None) -> bool:
        """Ob ein Befund mindestens ``threshold`` erreicht (``None``: nie)."""
        if threshold is None:
            return False
        return any(f.severity.rank >= threshold.rank for f in self.findings)

    def rule_ids(self, severity: Severity | None = None) -> set[str]:
        return {f.rule_id for f in self.findings if severity is None or f.severity is severity}


class _DuplicateKeyError(ValueError):
    pass


def _no_duplicates(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError(key)
        result[key] = value
    return result


def _reject_constant(name: str) -> Any:
    raise ValueError(f"{name} ist in JSON nicht zulässig")


def _sort_key(f: Finding) -> tuple[int, str, int, int, str]:
    return (-f.severity.rank, f.rule_id, f.line, f.column, f.message)


def evaluate(
    case: Any,
    *,
    as_of: date,
    base_dir: Path | None = None,
    check_evidence_files: bool = False,
) -> list[tuple[str, Severity, str, str]]:
    """Regeln auf einen bereits geparsten Fall anwenden.

    Rückgabe: Liste von (Regel-ID, Schweregrad, Meldung, JSON Pointer).
    Bei Schemafehlern (GB-01) werden die übrigen Regeln nicht ausgewertet.
    """
    schema_errors = usecase_validator().errors(case)
    if schema_errors:
        return [("GB-01", Severity.ERROR, e.message, e.pointer) for e in schema_errors]
    ctx = CaseContext(
        case=case, as_of=as_of, base_dir=base_dir, check_evidence_files=check_evidence_files
    )
    hits: list[tuple[str, Severity, str, str]] = []
    for rule in RULES:
        if rule.check is None:
            continue
        for hit in rule.check(ctx, rule):
            hits.append((rule.id, hit.severity, hit.message, hit.pointer))
    return hits


def validate_text(
    text: str,
    *,
    source: str = "<stdin>",
    as_of: date,
    base_dir: Path | None = None,
    check_evidence_files: bool = False,
) -> CaseReport:
    """Einen Fall aus JSON-Text prüfen."""
    try:
        case = json.loads(
            text.removeprefix("﻿"),
            object_pairs_hook=_no_duplicates,
            parse_constant=_reject_constant,
        )
    except _DuplicateKeyError as exc:
        return CaseReport(
            source,
            None,
            None,
            (
                Finding(
                    "GB-01", Severity.ERROR, f"Schlüssel {exc.args[0]!r} ist doppelt vorhanden."
                ),
            ),
        )
    except json.JSONDecodeError as exc:
        return CaseReport(
            source,
            None,
            None,
            (
                Finding(
                    "GB-01",
                    Severity.ERROR,
                    f"Kein gültiges JSON: {exc.msg}.",
                    "",
                    exc.lineno,
                    exc.colno,
                ),
            ),
        )
    except ValueError as exc:
        return CaseReport(source, None, None, (Finding("GB-01", Severity.ERROR, f"{exc}."),))

    locator = PointerLocator(text)
    findings: list[Finding] = []
    for rule_id, severity, message, pointer in evaluate(
        case, as_of=as_of, base_dir=base_dir, check_evidence_files=check_evidence_files
    ):
        pos = locator.locate(pointer)
        findings.append(Finding(rule_id, severity, message, pointer, pos.line, pos.column))
    findings.sort(key=_sort_key)
    case_id = case.get("id") if isinstance(case, Mapping) else None
    level = case.get("level") if isinstance(case, Mapping) else None
    return CaseReport(
        source=source,
        case_id=case_id if isinstance(case_id, str) else None,
        level=int(level)
        if isinstance(level, (int, float)) and not isinstance(level, bool)
        else None,
        findings=tuple(findings),
    )


def validate_path(
    path: str | Path,
    *,
    as_of: date,
    check_evidence_files: bool = False,
    display: str | None = None,
) -> CaseReport:
    """Eine Datei prüfen; Nachweis-Pfade sind relativ zum Verzeichnis der Datei."""
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    return validate_text(
        text,
        source=display if display is not None else str(p),
        as_of=as_of,
        base_dir=p.parent,
        check_evidence_files=check_evidence_files,
    )


def validate_case(case: Mapping[str, Any], *, as_of: date | None = None) -> CaseReport:
    """Bequeme Prüfung eines Python-Dicts (ohne Positionen)."""
    when = as_of or date.today()  # noqa: DTZ011 - Stichtag ist ein Kalenderdatum
    text = json.dumps(case, ensure_ascii=False, indent=2)
    return validate_text(text, source="<dict>", as_of=when)


__all__ = [
    "RULES_BY_ID",
    "CaseReport",
    "Finding",
    "evaluate",
    "validate_case",
    "validate_path",
    "validate_text",
]
