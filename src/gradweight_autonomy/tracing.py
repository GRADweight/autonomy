"""Tracing von Modellaufrufen (Metadaten, keine Inhalte).

Der Audit-Trail hält *Entscheide* fest; dieses Modul die *Modellaufrufe*:
Anbieter, Modell, Dauer, Längen von Anfrage und Antwort, Status. Prompt- und
Antworttexte werden bewusst nicht gespeichert (Datenminimierung).
"""

from __future__ import annotations

import sqlite3
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gradweight_autonomy._resources import Closable

STATUSES = ("ok", "refusal", "timeout", "error")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


@dataclass(frozen=True)
class TraceEvent:
    """Ein Modellaufruf."""

    tenant: str
    use_case: str
    provider: str
    model: str
    duration_ms: int
    request_chars: int
    response_chars: int
    status: str
    action_id: int | None = None
    error: str = ""
    timestamp: str = field(default_factory=_utc_now_iso)

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(f"status muss einer von {STATUSES} sein")
        if self.duration_ms < 0 or self.request_chars < 0 or self.response_chars < 0:
            raise ValueError("Dauer und Längen dürfen nicht negativ sein")


@dataclass
class Span:
    """Laufender Aufruf innerhalb von :meth:`Tracer.span`."""

    response_chars: int = 0
    status: str = "ok"
    error: str = ""

    def finish(self, *, response: str = "", status: str = "ok", error: str = "") -> None:
        """Ergebnis setzen (sonst gilt ``ok`` bzw. bei Ausnahme ``error``)."""
        self.response_chars = len(response)
        self.status = status
        self.error = error


class Tracer(Closable):
    """Append-only Protokoll von Modellaufrufen in SQLite."""

    def __init__(
        self, db_path: str | Path = ":memory:", *, monotonic: Callable[[], float] = time.monotonic
    ) -> None:
        self._monotonic = monotonic
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS traces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                tenant TEXT NOT NULL,
                use_case TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                duration_ms INTEGER NOT NULL,
                request_chars INTEGER NOT NULL,
                response_chars INTEGER NOT NULL,
                status TEXT NOT NULL,
                action_id INTEGER,
                error TEXT NOT NULL DEFAULT ''
            )
            """
        )
        self._conn.commit()

    def record(self, event: TraceEvent) -> int:
        """Ereignis speichern; gibt die ID zurück."""
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO traces (ts, tenant, use_case, provider, model, duration_ms, "
                "request_chars, response_chars, status, action_id, error) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event.timestamp,
                    event.tenant,
                    event.use_case,
                    event.provider,
                    event.model,
                    event.duration_ms,
                    event.request_chars,
                    event.response_chars,
                    event.status,
                    event.action_id,
                    event.error,
                ),
            )
            self._conn.commit()
            row_id = cur.lastrowid
        if row_id is None:  # pragma: no cover
            raise RuntimeError("INSERT lieferte keine ID")
        return int(row_id)

    @contextmanager
    def span(
        self,
        *,
        tenant: str,
        use_case: str,
        provider: str,
        model: str,
        request: str = "",
        action_id: int | None = None,
    ) -> Iterator[Span]:
        """Aufruf messen; eine Ausnahme wird als ``error`` protokolliert und weitergereicht."""
        start = self._monotonic()
        span = Span()
        try:
            yield span
        except BaseException as exc:
            span.status = "error"
            span.error = type(exc).__name__
            raise
        finally:
            self.record(
                TraceEvent(
                    tenant=tenant,
                    use_case=use_case,
                    provider=provider,
                    model=model,
                    duration_ms=max(0, int((self._monotonic() - start) * 1000)),
                    request_chars=len(request),
                    response_chars=span.response_chars,
                    status=span.status,
                    action_id=action_id,
                    error=span.error,
                )
            )

    def query(
        self, *, tenant: str | None = None, status: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Neueste Ereignisse zuerst."""
        sql = (
            "SELECT id, ts, tenant, use_case, provider, model, duration_ms, request_chars, "
            "response_chars, status, action_id, error FROM traces"
        )
        where: list[str] = []
        params: list[Any] = []
        if tenant is not None:
            where.append("tenant = ?")
            params.append(tenant)
        if status is not None:
            where.append("status = ?")
            params.append(status)
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(max(1, min(limit, 1000)))
        cols = (
            "id",
            "ts",
            "tenant",
            "use_case",
            "provider",
            "model",
            "duration_ms",
            "request_chars",
            "response_chars",
            "status",
            "action_id",
            "error",
        )
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [dict(zip(cols, r, strict=True)) for r in rows]

    def summary(self, *, tenant: str | None = None) -> dict[str, float | int]:
        """Anzahl, Fehlerquote und mittlere Dauer."""
        sql = (
            "SELECT COUNT(*), COALESCE(AVG(duration_ms), 0), "
            "COALESCE(SUM(CASE WHEN status != 'ok' THEN 1 ELSE 0 END), 0) FROM traces"
        )
        params: list[Any] = []
        if tenant is not None:
            sql += " WHERE tenant = ?"
            params.append(tenant)
        with self._lock:
            n, avg_ms, failures = self._conn.execute(sql, params).fetchone()
        n = int(n)
        return {
            "calls": n,
            "failures": int(failures),
            "failure_rate": round(int(failures) / n, 4) if n else 0.0,
            "avg_duration_ms": round(float(avg_ms)),
        }

    def close(self) -> None:
        """Verbindung schliessen."""
        with self._lock:
            self._conn.close()
