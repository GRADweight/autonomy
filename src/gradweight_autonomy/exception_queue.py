"""Ausnahme-Queue: deterministische Weiterleitung an Menschen (Grad 5, GB-11).

Eine Aktion, die eine Schwelle überschreitet (Betrag, sensible Daten,
Fehlerhäufung), wird nicht «nach Ermessen des Modells», sondern nach fester
Policy einem Menschen vorgelegt. Gleiche Eingabe ergibt immer denselben
Entscheid; das macht die Policy test- und revisionsfähig.

Entscheidete Einträge sind final; jeder Schritt landet im Audit-Trail.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from gradweight_autonomy._canonical import canonical_json, to_jsonable
from gradweight_autonomy._resources import Closable
from gradweight_autonomy.audit import AuditTrail

STATUS_OPEN = "open"
STATUS_RESOLVED = "resolved"
STATUS_DISMISSED = "dismissed"
_FINAL = (STATUS_RESOLVED, STATUS_DISMISSED)


class ExceptionQueueError(RuntimeError):
    """Fehler der Ausnahme-Queue."""


@dataclass(frozen=True)
class ExceptionPolicy:
    """Schwellen; ``None`` bzw. ``False`` heisst «nicht geprüft».

    Ohne gesetzte Schwelle leitet die Policy nichts weiter. Für Grad 5 ist
    mindestens eine Schwelle zu setzen – das prüft der Aufrufer, nicht die Policy.
    """

    money_limit: Decimal | None = None
    sensitive_requires_review: bool = False
    error_threshold: int | None = None

    def __post_init__(self) -> None:
        if self.money_limit is not None and self.money_limit < 0:
            raise ValueError("money_limit darf nicht negativ sein")
        if self.error_threshold is not None and self.error_threshold < 0:
            raise ValueError("error_threshold darf nicht negativ sein")


@dataclass(frozen=True)
class ExceptionDecision:
    """Ergebnis der Policy-Prüfung."""

    requires_human: bool
    reason: str
    rule_id: str = ""


@dataclass(frozen=True)
class ExceptionItem:
    """Ein Eintrag der Queue."""

    id: int
    tenant: str
    use_case: str
    title: str
    payload: Mapping[str, Any]
    status: str
    reason: str
    rule_id: str
    raised_by: str
    created_at: str
    resolved_at: str | None
    resolved_by: str | None


def evaluate(
    policy: ExceptionPolicy,
    *,
    amount: Decimal = Decimal(0),
    sensitive: bool = False,
    error_count: int = 0,
) -> ExceptionDecision:
    """Policy deterministisch anwenden (reine Funktion, keine Seiteneffekte).

    Reihenfolge: Betrag (GB-09), sensible Daten (GB-15), Fehlerhäufung (GB-12).
    Grenzwerte sind exklusiv: genau am Limit bleibt die Aktion im System.
    """
    if policy.money_limit is not None and amount > policy.money_limit:
        return ExceptionDecision(True, f"Betrag {amount} über Limit {policy.money_limit}", "GB-09")
    if sensitive and policy.sensitive_requires_review:
        return ExceptionDecision(True, "sensible Daten: menschliche Prüfung verlangt", "GB-15")
    if policy.error_threshold is not None and error_count > policy.error_threshold:
        return ExceptionDecision(
            True, f"Fehlerhäufung {error_count} über Schwelle {policy.error_threshold}", "GB-12"
        )
    return ExceptionDecision(False, "keine Schwelle überschritten")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS exceptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant TEXT NOT NULL,
    use_case TEXT NOT NULL,
    title TEXT NOT NULL,
    payload TEXT NOT NULL,
    status TEXT NOT NULL,
    reason TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    raised_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    resolved_by TEXT
);
CREATE INDEX IF NOT EXISTS idx_exceptions_status ON exceptions (status);
"""
_COLUMNS = (
    "id, tenant, use_case, title, payload, status, reason, rule_id, raised_by, "
    "created_at, resolved_at, resolved_by"
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ExceptionQueue(Closable):
    """Queue für Ausnahmen, die ein Mensch bearbeiten muss."""

    def __init__(
        self,
        db_path: str | Path = ":memory:",
        *,
        audit: AuditTrail,
        policy: ExceptionPolicy,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._audit = audit
        self._policy = policy
        self._clock = clock
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    @property
    def policy(self) -> ExceptionPolicy:
        return self._policy

    def evaluate(
        self, *, amount: Decimal = Decimal(0), sensitive: bool = False, error_count: int = 0
    ) -> ExceptionDecision:
        """Policy anwenden (siehe :func:`evaluate`)."""
        return evaluate(self._policy, amount=amount, sensitive=sensitive, error_count=error_count)

    def enqueue(
        self,
        *,
        tenant: str,
        use_case: str,
        title: str,
        payload: Mapping[str, Any],
        decision: ExceptionDecision,
        raised_by: str = "system",
    ) -> int:
        """Ausnahme einreihen; der Policy-Entscheid wird mitgespeichert."""
        if not decision.requires_human:
            raise ExceptionQueueError("Nur Entscheide mit requires_human=True gehören in die Queue")
        now = self._clock().astimezone(timezone.utc).isoformat(timespec="microseconds")
        with self._lock:
            cur = self._conn.execute(
                f"INSERT INTO exceptions ({_COLUMNS.removeprefix('id, ')}) "  # noqa: S608
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)",
                (
                    tenant,
                    use_case,
                    title,
                    canonical_json(to_jsonable(dict(payload))),
                    STATUS_OPEN,
                    decision.reason,
                    decision.rule_id,
                    raised_by,
                    now,
                ),
            )
            self._conn.commit()
            item_id = cur.lastrowid
        if item_id is None:  # pragma: no cover
            raise ExceptionQueueError("INSERT lieferte keine ID")
        self._audit.append(
            tenant=tenant,
            use_case=use_case,
            actor=raised_by,
            action="exception_raised",
            details={
                "exception_id": item_id,
                "title": title,
                "reason": decision.reason,
                "rule_id": decision.rule_id,
            },
        )
        return int(item_id)

    def resolve(self, item_id: int, *, status: str, actor: str, reason: str) -> ExceptionItem:
        """Ausnahme abschliessen (``resolved`` oder ``dismissed``); final."""
        if status not in _FINAL:
            raise ValueError(f"status muss einer von {_FINAL} sein")
        if not actor or not reason:
            raise ValueError("actor und reason sind Pflicht")
        item = self.get(item_id)
        now = self._clock().astimezone(timezone.utc).isoformat(timespec="microseconds")
        with self._lock:
            cur = self._conn.execute(
                "UPDATE exceptions SET status = ?, resolved_at = ?, resolved_by = ? "
                "WHERE id = ? AND status = ?",
                (status, now, actor, item_id, STATUS_OPEN),
            )
            self._conn.commit()
            changed = cur.rowcount
        if changed != 1:
            raise ExceptionQueueError(f"Ausnahme {item_id} ist bereits {item.status!r} (final)")
        self._audit.append(
            tenant=item.tenant,
            use_case=item.use_case,
            actor=actor,
            action=f"exception_{status}",
            details={"exception_id": item_id, "reason": reason},
        )
        return self.get(item_id)

    def _to_item(self, row: tuple[Any, ...]) -> ExceptionItem:
        (iid, tenant, use_case, title, payload, status, reason, rule_id, raised_by, created_at,
         resolved_at, resolved_by) = row  # fmt: skip
        return ExceptionItem(
            id=int(iid),
            tenant=tenant,
            use_case=use_case,
            title=title,
            payload=json.loads(payload),
            status=status,
            reason=reason,
            rule_id=rule_id,
            raised_by=raised_by,
            created_at=created_at,
            resolved_at=resolved_at,
            resolved_by=resolved_by,
        )

    def get(self, item_id: int) -> ExceptionItem:
        """Eintrag laden."""
        with self._lock:
            row = self._conn.execute(
                f"SELECT {_COLUMNS} FROM exceptions WHERE id = ?",  # noqa: S608
                (item_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Keine Ausnahme mit ID {item_id}")
        return self._to_item(row)

    def pending(self, *, tenant: str | None = None) -> list[ExceptionItem]:
        """Offene Ausnahmen, älteste zuerst."""
        sql = f"SELECT {_COLUMNS} FROM exceptions WHERE status = ?"  # noqa: S608
        params: list[Any] = [STATUS_OPEN]
        if tenant is not None:
            sql += " AND tenant = ?"
            params.append(tenant)
        with self._lock:
            rows = self._conn.execute(sql + " ORDER BY id", params).fetchall()
        return [self._to_item(r) for r in rows]

    def summary(self, *, tenant: str | None = None) -> dict[str, int]:
        """Anzahl je Status."""
        sql = "SELECT status, COUNT(*) FROM exceptions"
        params: list[Any] = []
        if tenant is not None:
            sql += " WHERE tenant = ?"
            params.append(tenant)
        with self._lock:
            counts = {s: int(n) for s, n in self._conn.execute(sql + " GROUP BY status", params)}
        return {
            STATUS_OPEN: counts.get(STATUS_OPEN, 0),
            STATUS_RESOLVED: counts.get(STATUS_RESOLVED, 0),
            STATUS_DISMISSED: counts.get(STATUS_DISMISSED, 0),
            "total": sum(counts.values()),
        }

    def close(self) -> None:
        """Verbindung schliessen."""
        with self._lock:
            self._conn.close()
