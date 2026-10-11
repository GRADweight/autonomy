"""Tracing — lückenloses LLM-Request-Protokoll (GB-11).

Der Audit-Trail deckt *Aktionen* (Freigabe, Zurückstellen); dieser
Baustein deckt die *LLM-Anfragen selbst*: Modell, Provider, Dauer,
Anfrage-/Antwortlänge, Status (ok/Refusal/_TIMEOUT), zugehörige
Aktion-ID, Mandant, Prototyp.

Bewusster Vorteil gegenüber einer Langfuse-Cloud: Die Daten bleiben in
derselben SQLite-Datei wie Audit/Queue (ein Zugriffspunkt für die
Revisions-Auswertung, DSG Art. 9 Rechenschaft) und es geht kein
Prompt-Inhalt auf einen Drittserver (DSG-relevant für #11
Personalfragen).
"""

from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _jetzt() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


@dataclass(frozen=True)
class TraceEvent:
    mandant: str
    prototyp: str
    provider: str
    model: str
    dauer_ms: int
    anfrage_länge: int
    antwort_länge: int
    status: str  # 'ok' | 'refusal' | 'timeout' | 'error'
    aktions_id: int | None = None
    fehler: str = ""
    timestamp: str = _jetzt()


class Tracer:
    """Append-only LLM-Trace-Log im selben DB-File wie Audit-Trail/Queue."""

    def __init__(self, db_file: str | Path) -> None:
        self.db_file = str(db_file)
        Path(self.db_file).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_file, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS traces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                t TEXT NOT NULL,
                mandant TEXT NOT NULL,
                prototyp TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                dauer_ms INTEGER NOT NULL,
                anfrage_laenge INTEGER NOT NULL,
                antwort_laenge INTEGER NOT NULL,
                status TEXT NOT NULL,
                aktions_id INTEGER,
                fehler TEXT NOT NULL DEFAULT ''
            )
            """
        )
        self._conn.commit()

    def record(self, ev: TraceEvent) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO traces (t, mandant, prototyp, provider, model, "
                "dauer_ms, anfrage_laenge, antwort_laenge, status, aktions_id, "
                "fehler) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    ev.timestamp, ev.mandant, ev.prototyp, ev.provider,
                    ev.model, ev.dauer_ms, ev.anfrage_länge, ev.antwort_länge,
                    ev.status, ev.aktions_id, ev.fehler,
                ),
            )
            self._conn.commit()
            if cur.lastrowid is None:
                raise RuntimeError("INSERT lieferte keine Zeilen-ID")
            return int(cur.lastrowid)

    def query(self, *, mandant: str | None = None, status: str | None = None,
              limit: int = 100) -> list[dict[str, Any]]:
        where: list[str] = []
        args: list[object] = []
        if mandant:
            where.append("mandant=?")
            args.append(mandant)
        if status:
            where.append("status=?")
            args.append(status)
        sql = "SELECT * FROM traces"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(max(1, min(limit, 1000)))
        with self._lock:
            rows = self._conn.execute(sql, args).fetchall()
        cols = ("id", "t", "mandant", "prototyp", "provider", "model",
                "dauer_ms", "anfrage_laenge", "antwort_laenge", "status",
                "aktions_id", "fehler")
        return [dict(zip(cols, r, strict=True)) for r in rows]

    def zusammenfassung(self, mandant: str | None = None) -> dict[str, Any]:
        """KPI für den 1-Seiter: Aufwand, Fehlerquote, Ø-Dauer."""
        where = "WHERE mandant=?" if mandant else ""
        args: list[object] = [mandant] if mandant else []
        with self._lock:
            f = self._conn.execute(
                f"SELECT COUNT(*), COALESCE(SUM(dauer_ms),0), "
                "COALESCE(AVG(dauer_ms),0), "
                "COALESCE(SUM(CASE WHEN status!='ok' THEN 1 ELSE 0 END),0) "
                f"FROM traces {where}", args).fetchone()
        n, sum_ms, avg_ms, fehler = (int(f[0]), float(f[1]), float(f[2]), int(f[3]))
        return {
            "anfragen": n,
            "fehler": fehler,
            "fehlerquote_prozent": round(fehler / n * 100, 1) if n else 0.0,
            "oek_dauer_ms": round(avg_ms),
            "summe_s": round(sum_ms / 1000, 1),
        }

    def schliesse(self) -> None:
        self._conn.close()


class TracingKontext:
    """Zeiten eine LLM-Aufruf sauber (start → record ok/error/refusal)."""

    def __init__(self, tracer: Tracer, *, mandant: str, prototyp: str,
                 provider: str, model: str,
                 aktions_id: int | None = None, anfrage: str = "") -> None:
        self._t = tracer
        self._mandant = mandant
        self._prototyp = prototyp
        self._provider = provider
        self._model = model
        self._aktions_id = aktions_id
        self._anfrage = anfrage
        self._start = time.monotonic()

    def abschliessen(self, *, antwort: str = "", status: str = "ok",
                     fehler: str = "") -> int:
        return self._t.record(TraceEvent(
            mandant=self._mandant,
            prototyp=self._prototyp,
            provider=self._provider,
            model=self._model,
            dauer_ms=int((time.monotonic() - self._start) * 1000),
            anfrage_länge=len(self._anfrage),
            antwort_länge=len(antwort),
            status=status,
            aktions_id=self._aktions_id,
            fehler=fehler,
        ))
