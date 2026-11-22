"""Rollback-Register: Vorher/Nachher-Zustand und deterministischer Umkehrbefehl (GB-12).

Der Baustein führt nichts selbst aus. Er hält fest, was eine Aktion im
Zielsystem verändert hat, leitet daraus den Umkehrbefehl ab (z. B.
``DELETE /4.0/purchase/bills/{id}``) und protokolliert, ob die Ausführung durch
den Host gelungen ist. Nicht umkehrbare Aktionen (z. B. ausgelöste Zahlungen)
werden ausdrücklich als solche registriert; :meth:`RollbackManager.command`
wirft dann einen prüfbaren Fehler statt still nichts zu tun.
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gradweight_autonomy._canonical import canonical_json, to_jsonable
from gradweight_autonomy._resources import Closable
from gradweight_autonomy.audit import AuditTrail

STATUS_OPEN = "open"
STATUS_DONE = "executed"
STATUS_FAILED = "failed"
_PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
_ALLOWED_METHODS = ("DELETE", "PATCH", "POST", "PUT")


class RollbackError(RuntimeError):
    """Basis für Rollback-Fehler."""


class NotReversibleError(RollbackError):
    """Die Aktion ist ausdrücklich als nicht umkehrbar registriert."""


class RollbackNotFoundError(RollbackError, KeyError):
    """Kein Eintrag mit dieser ID."""


class RollbackAlreadyFinalError(RollbackError):
    """Der Eintrag ist bereits abgeschlossen."""


class MissingParameterError(RollbackError):
    """Ein Platzhalter der Vorlage hat keinen Wert im Nachher-Zustand."""


@dataclass(frozen=True)
class RollbackCommand:
    """Umkehrbefehl, den der Host gegen das Zielsystem ausführt."""

    method: str
    endpoint: str
    params: tuple[tuple[str, Any], ...]
    reason: str
    entry_id: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "endpoint": self.endpoint,
            "params": dict(self.params),
            "reason": self.reason,
            "entry_id": self.entry_id,
        }


@dataclass(frozen=True)
class RollbackEntry:
    """Registrierte Aktion mit Zustand und Rollback-Status."""

    id: int
    created_at: str
    tenant: str
    use_case: str
    actor: str
    description: str
    reversible: bool
    before_state: Mapping[str, Any]
    after_state: Mapping[str, Any]
    template: Mapping[str, Any]
    reason: str
    status: str
    result: str | None
    executed_by: str | None
    executed_at: str | None


_SCHEMA = """
CREATE TABLE IF NOT EXISTS rollback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    tenant TEXT NOT NULL,
    use_case TEXT NOT NULL,
    actor TEXT NOT NULL,
    description TEXT NOT NULL,
    reversible INTEGER NOT NULL,
    before_state TEXT NOT NULL,
    after_state TEXT NOT NULL,
    template TEXT NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL,
    result TEXT,
    executed_by TEXT,
    executed_at TEXT
);
"""
_COLUMNS = (
    "id, created_at, tenant, use_case, actor, description, reversible, before_state, "
    "after_state, template, reason, status, result, executed_by, executed_at"
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _fill(value: Any, state: Mapping[str, Any], entry_id: int) -> Any:
    if isinstance(value, str):

        def repl(match: re.Match[str]) -> str:
            key = match.group(1)
            if key not in state:
                raise MissingParameterError(
                    f"Eintrag {entry_id}: Platzhalter {{{key}}} fehlt im Nachher-Zustand "
                    f"(vorhanden: {sorted(state)})"
                )
            return str(state[key])

        return _PLACEHOLDER.sub(repl, value)
    if isinstance(value, Mapping):
        return {k: _fill(v, state, entry_id) for k, v in value.items()}
    if isinstance(value, list):
        return [_fill(v, state, entry_id) for v in value]
    return value


class RollbackManager(Closable):
    """Register für umkehrbare (und ausdrücklich nicht umkehrbare) Aktionen."""

    def __init__(
        self,
        db_path: str | Path = ":memory:",
        *,
        audit: AuditTrail | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._audit = audit
        self._clock = clock
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def _now(self) -> str:
        return self._clock().astimezone(timezone.utc).isoformat(timespec="microseconds")

    def register(
        self,
        *,
        tenant: str,
        use_case: str,
        actor: str,
        description: str,
        reversible: bool,
        before_state: Mapping[str, Any] | None = None,
        after_state: Mapping[str, Any] | None = None,
        template: Mapping[str, Any] | None = None,
        reason: str = "",
    ) -> int:
        """Aktion registrieren.

        ``template`` braucht bei ``reversible=True`` mindestens ``method`` und
        ``endpoint``; Platzhalter ``{name}`` werden aus ``after_state`` ersetzt.
        """
        tpl = dict(template or {})
        if reversible:
            method = str(tpl.get("method", "")).upper()
            if method not in _ALLOWED_METHODS or not tpl.get("endpoint"):
                raise ValueError(
                    f"reversible=True verlangt template.method ({'/'.join(_ALLOWED_METHODS)}) "
                    "und template.endpoint"
                )
        elif not reason:
            raise ValueError("Nicht umkehrbare Aktionen brauchen eine Begründung (reason)")
        with self._lock:
            cur = self._conn.execute(
                f"INSERT INTO rollback ({_COLUMNS.removeprefix('id, ')}) "  # noqa: S608
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL)",
                (
                    self._now(),
                    tenant,
                    use_case,
                    actor,
                    description,
                    int(reversible),
                    canonical_json(to_jsonable(dict(before_state or {}))),
                    canonical_json(to_jsonable(dict(after_state or {}))),
                    canonical_json(to_jsonable(tpl)),
                    reason,
                    STATUS_OPEN,
                ),
            )
            self._conn.commit()
            entry_id = cur.lastrowid
        if entry_id is None:  # pragma: no cover
            raise RollbackError("INSERT lieferte keine ID")
        if self._audit is not None:
            self._audit.append(
                tenant=tenant,
                use_case=use_case,
                actor=actor,
                action="rollback_registered",
                details={"entry_id": entry_id, "reversible": reversible, "reason": reason},
            )
        return int(entry_id)

    def command(self, entry_id: int) -> RollbackCommand:
        """Umkehrbefehl ableiten (deterministisch, ohne Seiteneffekt)."""
        entry = self.get(entry_id)
        if not entry.reversible:
            raise NotReversibleError(f"Eintrag {entry_id} ist nicht umkehrbar: {entry.reason}")
        filled = _fill(dict(entry.template), entry.after_state, entry_id)
        params = filled.get("params") or {}
        if not isinstance(params, Mapping):
            raise RollbackError(f"Eintrag {entry_id}: template.params muss ein Objekt sein")
        return RollbackCommand(
            method=str(filled["method"]).upper(),
            endpoint=str(filled["endpoint"]),
            params=tuple(sorted((str(k), v) for k, v in params.items())),
            reason=entry.reason,
            entry_id=entry_id,
        )

    def record_execution(
        self, entry_id: int, *, success: bool, result: str, actor: str
    ) -> RollbackEntry:
        """Ausführung durch den Host festhalten; danach ist der Eintrag final."""
        entry = self.get(entry_id)
        status = STATUS_DONE if success else STATUS_FAILED
        with self._lock:
            cur = self._conn.execute(
                "UPDATE rollback SET status = ?, result = ?, executed_by = ?, executed_at = ? "
                "WHERE id = ? AND status = ?",
                (status, result[:512], actor, self._now(), entry_id, STATUS_OPEN),
            )
            self._conn.commit()
            changed = cur.rowcount
        if changed != 1:
            raise RollbackAlreadyFinalError(f"Eintrag {entry_id} ist bereits {entry.status!r}")
        if self._audit is not None:
            self._audit.append(
                tenant=entry.tenant,
                use_case=entry.use_case,
                actor=actor,
                action=f"rollback_{status}",
                details={"entry_id": entry_id, "result": result[:512]},
            )
        return self.get(entry_id)

    def _to_entry(self, row: tuple[Any, ...]) -> RollbackEntry:
        (rid, created_at, tenant, use_case, actor, description, reversible, before, after,
         template, reason, status, result, executed_by, executed_at) = row  # fmt: skip
        return RollbackEntry(
            id=int(rid),
            created_at=created_at,
            tenant=tenant,
            use_case=use_case,
            actor=actor,
            description=description,
            reversible=bool(reversible),
            before_state=json.loads(before),
            after_state=json.loads(after),
            template=json.loads(template),
            reason=reason,
            status=status,
            result=result,
            executed_by=executed_by,
            executed_at=executed_at,
        )

    def get(self, entry_id: int) -> RollbackEntry:
        """Eintrag laden."""
        with self._lock:
            row = self._conn.execute(
                f"SELECT {_COLUMNS} FROM rollback WHERE id = ?",  # noqa: S608
                (entry_id,),
            ).fetchone()
        if row is None:
            raise RollbackNotFoundError(f"Kein Rollback-Eintrag mit ID {entry_id}")
        return self._to_entry(row)

    def pending(self, *, tenant: str | None = None) -> list[RollbackEntry]:
        """Offene Einträge, älteste zuerst."""
        sql = f"SELECT {_COLUMNS} FROM rollback WHERE status = ?"  # noqa: S608
        params: list[Any] = [STATUS_OPEN]
        if tenant is not None:
            sql += " AND tenant = ?"
            params.append(tenant)
        with self._lock:
            rows = self._conn.execute(sql + " ORDER BY id", params).fetchall()
        return [self._to_entry(r) for r in rows]

    def summary(self) -> dict[str, int]:
        """Anzahl je Status."""
        with self._lock:
            counts = {
                s: int(n)
                for s, n in self._conn.execute(
                    "SELECT status, COUNT(*) FROM rollback GROUP BY status"
                )
            }
        return {
            STATUS_OPEN: counts.get(STATUS_OPEN, 0),
            STATUS_DONE: counts.get(STATUS_DONE, 0),
            STATUS_FAILED: counts.get(STATUS_FAILED, 0),
            "total": sum(counts.values()),
        }

    def close(self) -> None:
        """Verbindung schliessen."""
        with self._lock:
            self._conn.close()
