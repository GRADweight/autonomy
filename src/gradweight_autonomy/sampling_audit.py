"""Stichproben-Audit über den Audit-Trail (Grad 5, GB-11).

Die Auswahl ist systematisch und reproduzierbar (fester Schritt über die nach
Laufnummer sortierten Einträge, kein Zufallsgenerator): Dieselben Daten und
dasselbe ``n`` liefern dieselbe Stichprobe. Jede Stichprobe wird gegen
Kriterien geprüft; der Bericht wird selbst wieder in den Trail geschrieben.

Grenze: Systematische Stichproben sind vorhersehbar. Wer die Schrittweite kennt,
kann Einträge gezielt «zwischen» die Stichprobe legen. Für adversariale
Umgebungen eine zufällige Auswahl mit geheimem Seed ergänzen.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from gradweight_autonomy.audit import AuditEntry, AuditTrail

Criterion = Callable[[AuditEntry], tuple[bool, str]]
SYSTEM_ACTORS = frozenset({"ki", "llm", "model", "system", "agent"})


def human_in_chain(entry: AuditEntry) -> tuple[bool, str]:
    """Der Akteur ist kein Systemakteur."""
    is_system = entry.actor.lower() in SYSTEM_ACTORS
    return (not is_system, f"actor={entry.actor!r}" + (" (Systemakteur)" if is_system else ""))


def rationale_present(entry: AuditEntry) -> tuple[bool, str]:
    """Der Eintrag enthält eine Begründung (``note`` oder ``reason``)."""
    text = str(entry.details.get("note") or entry.details.get("reason") or "").strip()
    return (bool(text), "Begründung vorhanden" if text else "Begründung fehlt")


STANDARD_CRITERIA: tuple[tuple[str, Criterion], ...] = (
    ("human_in_chain", human_in_chain),
    ("rationale_present", rationale_present),
)


@dataclass(frozen=True)
class EntryAssessment:
    """Beurteilung eines Eintrags."""

    seq: int
    actor: str
    action: str
    passed: bool
    results: tuple[tuple[str, bool, str], ...]


@dataclass(frozen=True)
class SamplingReport:
    """Ergebnis eines Stichproben-Audits."""

    population: int
    sample_size: int
    passed: int
    failed: int
    failures_by_criterion: tuple[tuple[str, int], ...]
    assessments: tuple[EntryAssessment, ...]

    @property
    def pass_rate(self) -> float:
        return self.passed / self.sample_size if self.sample_size else 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "population": self.population,
            "sample_size": self.sample_size,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": round(self.pass_rate, 4),
            "failures_by_criterion": dict(self.failures_by_criterion),
            "assessments": [
                {
                    "seq": a.seq,
                    "actor": a.actor,
                    "action": a.action,
                    "passed": a.passed,
                    "results": [
                        {"criterion": n, "passed": p, "detail": d} for n, p, d in a.results
                    ],
                }
                for a in self.assessments
            ],
        }


def systematic_sample(items: Sequence[AuditEntry], n: int) -> list[AuditEntry]:
    """Jeden k-ten Eintrag wählen (k = len/n); ``n >= len`` liefert alle."""
    if n < 1:
        raise ValueError("n muss >= 1 sein")
    total = len(items)
    if n >= total:
        return list(items)
    step = total / n
    return [items[int(i * step)] for i in range(n)]


class SamplingAudit:
    """Reproduzierbares Stichproben-Audit."""

    ACTION = "sampling_audit"

    def __init__(self, audit: AuditTrail) -> None:
        self._audit = audit

    def population(
        self, *, tenant: str | None = None, actions: Sequence[str] | None = None
    ) -> list[AuditEntry]:
        """Grundgesamtheit (ohne frühere Audit-Läufe), alt nach neu."""
        wanted = set(actions) if actions is not None else None
        return [
            e
            for e in self._audit.iter_entries()
            if e.action != self.ACTION
            and (tenant is None or e.tenant == tenant)
            and (wanted is None or e.action in wanted)
        ]

    def run(
        self,
        *,
        n: int,
        actor: str,
        tenant: str | None = None,
        actions: Sequence[str] | None = None,
        criteria: Sequence[tuple[str, Criterion]] = STANDARD_CRITERIA,
    ) -> SamplingReport:
        """Stichprobe ziehen, beurteilen und den Bericht im Trail ablegen."""
        if not criteria:
            raise ValueError("mindestens ein Kriterium nötig")
        population = self.population(tenant=tenant, actions=actions)
        sample = systematic_sample(population, n) if population else []
        assessments: list[EntryAssessment] = []
        for entry in sample:
            results: list[tuple[str, bool, str]] = []
            for name, criterion in criteria:
                try:
                    ok, detail = criterion(entry)
                except Exception as exc:  # noqa: BLE001 - Kriteriumsfehler = Befund, kein Abbruch
                    ok, detail = False, f"Kriterium warf {type(exc).__name__}: {exc}"
                results.append((name, bool(ok), str(detail)))
            assessments.append(
                EntryAssessment(
                    seq=entry.seq,
                    actor=entry.actor,
                    action=entry.action,
                    passed=all(ok for _, ok, _ in results),
                    results=tuple(results),
                )
            )
        passed = sum(1 for a in assessments if a.passed)
        failures = tuple(
            (name, sum(1 for a in assessments for c, ok, _ in a.results if c == name and not ok))
            for name, _ in criteria
        )
        report = SamplingReport(
            population=len(population),
            sample_size=len(sample),
            passed=passed,
            failed=len(sample) - passed,
            failures_by_criterion=failures,
            assessments=tuple(assessments),
        )
        self._audit.append(
            tenant=tenant or "*",
            use_case="*",
            actor=actor,
            action=self.ACTION,
            details={
                "n": n,
                "criteria": [name for name, _ in criteria],
                "report": report.as_dict(),
            },
        )
        return report
