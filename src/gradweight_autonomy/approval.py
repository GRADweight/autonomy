"""Freigabe-Queue: Vorschlag -> Freigabe / Anpassung / Rückweisung je Aktion.

Grundlage für Grad 2 («Copilot»): Die KI schlägt eine schreibende Aktion vor,
ein Mensch mit berechtigter Rolle entscheidet. Jeder Schritt landet im
:class:`~gradweight_autonomy.audit.AuditTrail`.

Durchgesetzt wird (fail-closed):

* Entscheiden lässt sich nur eine offene Aktion – einmal entschieden ist final.
* Freigeben und Anpassen verlangen eine Rolle, die die
  :class:`~gradweight_autonomy.authz.ApprovalPolicy` für den Anwendungsfall erlaubt.
* Vier-Augen-Prinzip: Wer vorgeschlagen hat, darf nicht selbst freigeben.
* Blockierende Vorprüfungen (z. B. die Belegprüfung) müssen bestanden sein;
  sonst wird die Freigabe verweigert. Beim Anpassen werden neue
  Prüfergebnisse für die geänderte Nutzlast verlangt.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gradweight_autonomy._canonical import canonical_json, to_jsonable
from gradweight_autonomy._resources import Closable
from gradweight_autonomy.audit import AuditTrail
from gradweight_autonomy.authz import ApprovalPolicy

STATUS_OPEN = "open"
STATUS_APPROVED = "approved"
STATUS_AMENDED = "amended"
STATUS_REJECTED = "rejected"


class ApprovalError(RuntimeError):
    """Basis für Fehler der Freigabe-Queue."""


class ActionNotFoundError(ApprovalError, KeyError):
    """Es gibt keine Aktion mit dieser ID."""


class ActionAlreadyDecidedError(ApprovalError):
    """Die Aktion ist bereits entschieden (append-only)."""


class ApprovalDeniedError(ApprovalError, PermissionError):
    """Die Freigabe wurde verweigert (Rolle, Vier-Augen, Vorprüfung)."""


@dataclass(frozen=True)
class CheckOutcome:
    """Ergebnis einer Vorprüfung, die einer Aktion beigelegt wird."""

    name: str
    passed: bool
    blocking: bool = True
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "blocking": self.blocking,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class Action:
    """Eine vorgeschlagene schreibende Aktion."""

    id: int
    tenant: str
    use_case: str
    title: str
    payload: Mapping[str, Any]
    status: str
    proposed_by: str
    approver_must_be: str | None
    checks: tuple[CheckOutcome, ...]
    note: str
    created_at: str
    decided_at: str | None
    decided_by: str | None

    @property
    def checks_passed(self) -> bool:
        """``True``, wenn keine blockierende Vorprüfung fehlgeschlagen ist."""
        return all(c.passed for c in self.checks if c.blocking)


@dataclass(frozen=True)
class ApprovalSummary:
    """Kennzahlen der Queue (z. B. für die Übernahmequote, GB-07)."""

    open: int
    approved: int
    amended: int
    rejected: int

    @property
    def total(self) -> int:
        return self.open + self.approved + self.amended + self.rejected

    @property
    def human_override_rate(self) -> float:
        """Anteil angepasster oder zurückgewiesener an allen entschiedenen Aktionen.

        Ein Wert nahe 0 über längere Zeit kann auf Automation Bias hindeuten
        (Durchklicken); er ist ein Signal zur Stichprobe, kein Beweis.
        """
        decided = self.approved + self.amended + self.rejected
        return (self.amended + self.rejected) / decided if decided else 0.0


_SCHEMA = """
CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant TEXT NOT NULL,
    use_case TEXT NOT NULL,
    title TEXT NOT NULL,
    payload TEXT NOT NULL,
    status TEXT NOT NULL,
    proposed_by TEXT NOT NULL,
    approver_must_be TEXT,
    checks TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    decided_at TEXT,
    decided_by TEXT
);
CREATE INDEX IF NOT EXISTS idx_actions_tenant ON actions (tenant);
CREATE INDEX IF NOT EXISTS idx_actions_status ON actions (status);
"""

_COLUMNS = (
    "id, tenant, use_case, title, payload, status, proposed_by, approver_must_be, "
    "checks, note, created_at, decided_at, decided_by"
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _checks_from_json(text: str) -> tuple[CheckOutcome, ...]:
    raw = json.loads(text)
    return tuple(
        CheckOutcome(
            name=str(c["name"]),
            passed=bool(c["passed"]),
            blocking=bool(c["blocking"]),
            detail=str(c["detail"]),
        )
        for c in raw
    )


class ApprovalQueue(Closable):
    """Freigabe je Aktion mit Rollenprüfung, Vier-Augen-Prinzip und Audit-Trail.

    >>> from gradweight_autonomy.audit import AuditTrail
    >>> from gradweight_autonomy.authz import ApprovalPolicy
    >>> policy = ApprovalPolicy({"kreditoren": ["buchhaltung"]})
    >>> q = ApprovalQueue(audit=AuditTrail(), policy=policy)
    >>> aid = q.propose(tenant="K1", use_case="kreditoren", title="Rechnung buchen", payload={})
    >>> q.approve(aid, actor="m.muster", role="buchhaltung").status
    'approved'
    """

    def __init__(
        self,
        db_path: str | Path = ":memory:",
        *,
        audit: AuditTrail,
        policy: ApprovalPolicy,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._audit = audit
        self._policy = policy
        self._clock = clock
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def _now(self) -> str:
        return self._clock().astimezone(timezone.utc).isoformat(timespec="microseconds")

    # -------------------------------------------------------------- propose
    def propose(
        self,
        *,
        tenant: str,
        use_case: str,
        title: str,
        payload: Mapping[str, Any],
        proposed_by: str = "ki",
        checks: Sequence[CheckOutcome] = (),
        approver_must_be: str | None = None,
    ) -> int:
        """Aktion vorschlagen (Status ``open``); gibt die ID zurück."""
        if not title:
            raise ValueError("title darf nicht leer sein")
        payload_json = canonical_json(to_jsonable(dict(payload)))
        checks_json = canonical_json([c.as_dict() for c in checks])
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO actions (tenant, use_case, title, payload, status, proposed_by, "
                "approver_must_be, checks, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    tenant,
                    use_case,
                    title,
                    payload_json,
                    STATUS_OPEN,
                    proposed_by,
                    approver_must_be,
                    checks_json,
                    self._now(),
                ),
            )
            self._conn.commit()
            action_id = cur.lastrowid
        if action_id is None:  # pragma: no cover - sqlite liefert immer eine ID
            raise ApprovalError("INSERT lieferte keine ID")
        self._audit.append(
            tenant=tenant,
            use_case=use_case,
            actor=proposed_by,
            action="action_proposed",
            details={
                "action_id": action_id,
                "title": title,
                "checks": [c.as_dict() for c in checks],
            },
        )
        return int(action_id)

    # ------------------------------------------------------------- decide
    def _refuse(self, action: Action, actor: str, reason: str) -> ApprovalDeniedError:
        self._audit.append(
            tenant=action.tenant,
            use_case=action.use_case,
            actor=actor,
            action="decision_refused",
            details={"action_id": action.id, "reason": reason},
        )
        return ApprovalDeniedError(reason)

    def _authorize(self, action: Action, *, actor: str, role: str) -> None:
        if not actor:
            raise ValueError("actor darf nicht leer sein")
        if action.status != STATUS_OPEN:
            raise ActionAlreadyDecidedError(
                f"Aktion {action.id} ist bereits {action.status!r}; Entscheide sind final."
            )
        if actor == action.proposed_by:
            raise self._refuse(
                action, actor, "Vier-Augen-Prinzip: Vorschlagende dürfen nicht freigeben."
            )
        if action.approver_must_be and actor != action.approver_must_be:
            raise self._refuse(
                action,
                actor,
                f"Nur {action.approver_must_be!r} darf Aktion {action.id} entscheiden.",
            )
        decision = self._policy.check(role=role, use_case=action.use_case)
        if not decision.allowed:
            raise self._refuse(action, actor, decision.reason)

    def _store_decision(
        self,
        action: Action,
        *,
        status: str,
        actor: str,
        role: str | None,
        note: str,
        payload: Mapping[str, Any] | None = None,
        checks: Sequence[CheckOutcome] | None = None,
    ) -> Action:
        decided_at = self._now()
        with self._lock:
            cur = self._conn.execute(
                "UPDATE actions SET status = ?, note = ?, decided_at = ?, decided_by = ?, "
                "payload = COALESCE(?, payload), checks = COALESCE(?, checks) "
                "WHERE id = ? AND status = ?",
                (
                    status,
                    note,
                    decided_at,
                    actor,
                    canonical_json(to_jsonable(dict(payload))) if payload is not None else None,
                    canonical_json([c.as_dict() for c in checks]) if checks is not None else None,
                    action.id,
                    STATUS_OPEN,
                ),
            )
            self._conn.commit()
            changed = cur.rowcount
        if changed != 1:
            raise ActionAlreadyDecidedError(f"Aktion {action.id} wurde parallel entschieden.")
        details: dict[str, Any] = {"action_id": action.id, "role": role, "note": note}
        if checks is not None:
            details["checks"] = [c.as_dict() for c in checks]
        self._audit.append(
            tenant=action.tenant,
            use_case=action.use_case,
            actor=actor,
            action=f"action_{status}",
            details=details,
        )
        return self.get(action.id)

    def approve(self, action_id: int, *, actor: str, role: str, note: str = "") -> Action:
        """Aktion freigeben. Danach darf der App-Code sie ausführen."""
        action = self.get(action_id)
        self._authorize(action, actor=actor, role=role)
        if not action.checks_passed:
            failed = ", ".join(c.name for c in action.checks if c.blocking and not c.passed)
            raise self._refuse(action, actor, f"Blockierende Vorprüfung nicht bestanden: {failed}")
        return self._store_decision(
            action, status=STATUS_APPROVED, actor=actor, role=role, note=note
        )

    def amend(
        self,
        action_id: int,
        *,
        actor: str,
        role: str,
        new_payload: Mapping[str, Any],
        checks: Sequence[CheckOutcome],
        note: str = "",
    ) -> Action:
        """Nutzlast ändern und freigeben; ``checks`` gelten für die neue Nutzlast."""
        action = self.get(action_id)
        self._authorize(action, actor=actor, role=role)
        if not all(c.passed for c in checks if c.blocking):
            failed = ", ".join(c.name for c in checks if c.blocking and not c.passed)
            raise self._refuse(action, actor, f"Blockierende Vorprüfung nicht bestanden: {failed}")
        return self._store_decision(
            action,
            status=STATUS_AMENDED,
            actor=actor,
            role=role,
            note=note,
            payload=new_payload,
            checks=checks,
        )

    def reject(self, action_id: int, *, actor: str, reason: str) -> Action:
        """Aktion zurückweisen; sie wird nicht ausgeführt. Begründung ist Pflicht."""
        if not reason:
            raise ValueError("Für eine Rückweisung ist eine Begründung nötig")
        if not actor:
            raise ValueError("actor darf nicht leer sein")
        action = self.get(action_id)
        if action.status != STATUS_OPEN:
            raise ActionAlreadyDecidedError(
                f"Aktion {action.id} ist bereits {action.status!r}; Entscheide sind final."
            )
        return self._store_decision(
            action, status=STATUS_REJECTED, actor=actor, role=None, note=reason
        )

    # ---------------------------------------------------------------- read
    def _to_action(self, row: tuple[Any, ...]) -> Action:
        (
            aid,
            tenant,
            use_case,
            title,
            payload,
            status,
            proposed_by,
            approver_must_be,
            checks,
            note,
            created_at,
            decided_at,
            decided_by,
        ) = row
        return Action(
            id=int(aid),
            tenant=tenant,
            use_case=use_case,
            title=title,
            payload=json.loads(payload),
            status=status,
            proposed_by=proposed_by,
            approver_must_be=approver_must_be,
            checks=_checks_from_json(checks),
            note=note,
            created_at=created_at,
            decided_at=decided_at,
            decided_by=decided_by,
        )

    def get(self, action_id: int) -> Action:
        """Aktion laden."""
        with self._lock:
            row = self._conn.execute(
                f"SELECT {_COLUMNS} FROM actions WHERE id = ?",  # noqa: S608 - feste Spalten
                (action_id,),
            ).fetchone()
        if row is None:
            raise ActionNotFoundError(f"Keine Aktion mit ID {action_id}")
        return self._to_action(row)

    def pending(self, *, tenant: str | None = None) -> list[Action]:
        """Offene Aktionen, älteste zuerst."""
        sql = f"SELECT {_COLUMNS} FROM actions WHERE status = ?"  # noqa: S608 - feste Spalten
        params: list[Any] = [STATUS_OPEN]
        if tenant is not None:
            sql += " AND tenant = ?"
            params.append(tenant)
        with self._lock:
            rows = self._conn.execute(sql + " ORDER BY id", params).fetchall()
        return [self._to_action(r) for r in rows]

    def summary(self, *, tenant: str | None = None) -> ApprovalSummary:
        """Anzahl Aktionen je Status."""
        sql = "SELECT status, COUNT(*) FROM actions"
        params: list[Any] = []
        if tenant is not None:
            sql += " WHERE tenant = ?"
            params.append(tenant)
        with self._lock:
            counts = {s: int(n) for s, n in self._conn.execute(sql + " GROUP BY status", params)}
        return ApprovalSummary(
            open=counts.get(STATUS_OPEN, 0),
            approved=counts.get(STATUS_APPROVED, 0),
            amended=counts.get(STATUS_AMENDED, 0),
            rejected=counts.get(STATUS_REJECTED, 0),
        )

    def close(self) -> None:
        """Verbindung schliessen."""
        with self._lock:
            self._conn.close()
