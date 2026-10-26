"""Audit-Trail mit Hash-Kette (SQLite, manipulationserkennend).

Jeder Eintrag enthält den Hash seines Vorgängers. Der Eintrags-Hash ist
SHA-256 (oder, mit Schlüssel, HMAC-SHA-256) über das kanonische JSON von
Version, Laufnummer, Zeitstempel, Mandant, Anwendungsfall, Akteur, Aktion,
Details und Vorgänger-Hash (siehe :func:`entry_payload`).

Was das garantiert – und was nicht:

* **Erkennt** nachträgliche Änderungen, Löschungen in der Mitte, Umordnung und
  eingeschobene Einträge (:meth:`AuditTrail.verify`).
* **Erkennt nicht von selbst**, wenn jemand mit Schreibzugriff die *ganze* Kette
  ab einem Punkt neu berechnet oder das Ende abschneidet. Dagegen hilft nur ein
  externer Anker: den Kopf-Hash (:meth:`AuditTrail.head`) regelmässig ausserhalb
  der Datenbank ablegen (z. B. WORM-Speicher, Ticket, signierter Commit) und bei
  der Prüfung als ``expected_head`` übergeben. Mit HMAC-Schlüssel kann ein
  Angreifer ohne Schlüssel die Kette nicht konsistent neu berechnen.
* **Verhindert nichts.** SQLite-Trigger blockieren UPDATE/DELETE über die normale
  Verbindung (Schutz vor Versehen); wer Dateizugriff hat, kann sie entfernen.
  Die Kette macht solche Eingriffe sichtbar, nicht unmöglich.
"""

from __future__ import annotations

import csv
import hashlib
import hmac
import json
import sqlite3
import threading
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gradweight_autonomy._canonical import canonical_bytes, canonical_json
from gradweight_autonomy._resources import Closable

CHAIN_VERSION = "gw-audit-v1"
GENESIS_HASH = "0" * 64
ALGORITHM_SHA256 = "sha256"
ALGORITHM_HMAC = "hmac-sha256"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
    seq INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,
    tenant TEXT NOT NULL,
    use_case TEXT NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    details TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    entry_hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_tenant ON audit_log (tenant);
CREATE INDEX IF NOT EXISTS idx_audit_use_case ON audit_log (use_case);
CREATE TRIGGER IF NOT EXISTS audit_log_no_update BEFORE UPDATE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log ist append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_log_no_delete BEFORE DELETE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log ist append-only'); END;
"""

_COLUMNS = "seq, ts, tenant, use_case, actor, action, details, prev_hash, entry_hash"


class AuditConfigurationError(RuntimeError):
    """Schlüssel oder Algorithmus passen nicht zur bestehenden Kette."""


@dataclass(frozen=True)
class AuditEntry:
    """Ein Eintrag der Kette."""

    seq: int
    ts: str
    tenant: str
    use_case: str
    actor: str
    action: str
    details: Mapping[str, Any]
    prev_hash: str
    entry_hash: str

    def as_dict(self) -> dict[str, Any]:
        """Als JSON-taugliches Dict (für Export und Stichproben)."""
        return {
            "seq": self.seq,
            "ts": self.ts,
            "tenant": self.tenant,
            "use_case": self.use_case,
            "actor": self.actor,
            "action": self.action,
            "details": dict(self.details),
            "prev_hash": self.prev_hash,
            "entry_hash": self.entry_hash,
        }


@dataclass(frozen=True)
class ChainProblem:
    """Ein bei der Prüfung gefundener Bruch der Kette."""

    seq: int
    kind: str  # "gap" | "order" | "link" | "hash" | "anchor"
    detail: str


@dataclass(frozen=True)
class VerificationResult:
    """Ergebnis von :meth:`AuditTrail.verify` bzw. :func:`verify_entries`."""

    ok: bool
    entries_checked: int
    head_seq: int
    head_hash: str
    problems: tuple[ChainProblem, ...] = field(default_factory=tuple)

    def summary(self) -> str:
        """Kurzfassung für Menschen (Deutsch)."""
        if self.ok:
            return (
                f"Kette intakt: {self.entries_checked} Einträge geprüft, "
                f"Kopf {self.head_seq}:{self.head_hash}"
            )
        first = self.problems[0]
        return (
            f"Kette verletzt: {len(self.problems)} Befund(e), erster bei "
            f"Eintrag {first.seq} ({first.kind}): {first.detail}"
        )


def entry_payload(
    *,
    seq: int,
    ts: str,
    tenant: str,
    use_case: str,
    actor: str,
    action: str,
    details: Mapping[str, Any],
    prev_hash: str,
) -> bytes:
    """Die Bytes, über die der Eintrags-Hash gebildet wird (kanonisches JSON)."""
    return canonical_bytes(
        {
            "v": CHAIN_VERSION,
            "seq": seq,
            "ts": ts,
            "tenant": tenant,
            "use_case": use_case,
            "actor": actor,
            "action": action,
            "details": details,
            "prev": prev_hash,
        }
    )


def compute_hash(payload: bytes, key: bytes | None = None) -> str:
    """SHA-256 (ohne Schlüssel) bzw. HMAC-SHA-256 (mit Schlüssel) als Hex."""
    if key is None:
        return hashlib.sha256(payload).hexdigest()
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def key_id(key: bytes) -> str:
    """Kurzer, nicht umkehrbarer Bezeichner eines HMAC-Schlüssels."""
    return hmac.new(key, b"gw-audit-key-id", hashlib.sha256).hexdigest()[:16]


def verify_entries(
    entries: Iterable[AuditEntry],
    *,
    key: bytes | None = None,
    expected_head: tuple[int, str] | None = None,
) -> VerificationResult:
    """Eine Folge von Einträgen (in gespeicherter Reihenfolge) prüfen.

    Geprüft wird: lückenlose Laufnummern ab 1, Verkettung über ``prev_hash``,
    Hash jedes Eintrags und – falls angegeben – der extern verankerte Kopf.
    """
    problems: list[ChainProblem] = []
    expected_seq = 1
    prev_hash = GENESIS_HASH
    count = 0
    anchor_seen = False
    last_seq = 0
    last_hash = GENESIS_HASH
    for entry in entries:
        count += 1
        if entry.seq != expected_seq:
            kind = "gap" if entry.seq > expected_seq else "order"
            problems.append(
                ChainProblem(
                    entry.seq,
                    kind,
                    f"Laufnummer {entry.seq} statt {expected_seq} erwartet "
                    "(Löschung, Umordnung oder Einschub)",
                )
            )
        if entry.prev_hash != prev_hash:
            problems.append(ChainProblem(entry.seq, "link", "prev_hash passt nicht zum Vorgänger"))
        recomputed = compute_hash(
            entry_payload(
                seq=entry.seq,
                ts=entry.ts,
                tenant=entry.tenant,
                use_case=entry.use_case,
                actor=entry.actor,
                action=entry.action,
                details=entry.details,
                prev_hash=entry.prev_hash,
            ),
            key,
        )
        if not hmac.compare_digest(recomputed, entry.entry_hash):
            problems.append(
                ChainProblem(entry.seq, "hash", "Inhalt passt nicht zum gespeicherten Hash")
            )
        if expected_head is not None and entry.seq == expected_head[0]:
            anchor_seen = True
            if not hmac.compare_digest(entry.entry_hash, expected_head[1]):
                problems.append(
                    ChainProblem(entry.seq, "anchor", "Hash weicht vom extern verankerten Kopf ab")
                )
        expected_seq = entry.seq + 1
        prev_hash = entry.entry_hash
        last_seq, last_hash = entry.seq, entry.entry_hash
    if expected_head is not None and expected_head[0] > 0 and not anchor_seen:
        problems.append(
            ChainProblem(
                expected_head[0],
                "anchor",
                "verankerter Eintrag fehlt (Kette gekürzt oder ersetzt)",
            )
        )
    return VerificationResult(
        ok=not problems,
        entries_checked=count,
        head_seq=last_seq,
        head_hash=last_hash,
        problems=tuple(problems),
    )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AuditTrail(Closable):
    """Append-only Audit-Trail mit Hash-Kette.

    >>> trail = AuditTrail()
    >>> trail.append(tenant="K1", use_case="kreditoren", actor="ki", action="vorschlag")
    1
    >>> trail.verify().ok
    True
    """

    def __init__(
        self,
        db_path: str | Path = ":memory:",
        *,
        hmac_key: bytes | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        if hmac_key is not None and len(hmac_key) < 16:
            raise ValueError("HMAC-Schlüssel muss mindestens 16 Bytes lang sein")
        self._key = hmac_key
        self._clock = clock
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False, isolation_level=None)
        self._conn.executescript(_SCHEMA)
        self._init_meta()

    # ------------------------------------------------------------------ setup
    def _init_meta(self) -> None:
        algorithm = ALGORITHM_HMAC if self._key is not None else ALGORITHM_SHA256
        kid = key_id(self._key) if self._key is not None else ""
        meta = [("chain_version", CHAIN_VERSION), ("algorithm", algorithm), ("key_id", kid)]
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                rows = dict(self._conn.execute("SELECT key, value FROM audit_meta").fetchall())
                if not rows:
                    self._conn.executemany(
                        "INSERT INTO audit_meta (key, value) VALUES (?, ?)", meta
                    )
                self._conn.execute("COMMIT")
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
        if rows and (rows.get("algorithm") != algorithm or rows.get("key_id", "") != kid):
            self._conn.close()
            raise AuditConfigurationError(
                "Schlüssel/Algorithmus passen nicht zur bestehenden Kette "
                f"(gespeichert: {rows.get('algorithm')}); Zugriff abgebrochen"
            )

    @property
    def algorithm(self) -> str:
        """``sha256`` oder ``hmac-sha256``."""
        return ALGORITHM_HMAC if self._key is not None else ALGORITHM_SHA256

    # ---------------------------------------------------------------- write
    def append(
        self,
        *,
        tenant: str,
        use_case: str,
        actor: str,
        action: str,
        details: Mapping[str, Any] | None = None,
    ) -> int:
        """Einen Eintrag anhängen und dessen Laufnummer zurückgeben.

        ``details`` muss JSON-serialisierbar sein (Strings, Zahlen, Listen, Dicts).
        Keine Prompts oder ganzen Datensätze ablegen – nur, was für die
        Nachvollziehbarkeit nötig ist (Datenminimierung).
        """
        for name, value in (
            ("tenant", tenant),
            ("use_case", use_case),
            ("actor", actor),
            ("action", action),
        ):
            if not value:
                raise ValueError(f"{name} darf nicht leer sein")
        details_obj: dict[str, Any] = dict(details or {})
        details_text = canonical_json(details_obj)  # validiert Serialisierbarkeit
        ts = self._clock().astimezone(timezone.utc).isoformat(timespec="microseconds")
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute(
                    "SELECT seq, entry_hash FROM audit_log ORDER BY seq DESC LIMIT 1"
                ).fetchone()
                seq = int(row[0]) + 1 if row else 1
                prev_hash = str(row[1]) if row else GENESIS_HASH
                entry_hash = compute_hash(
                    entry_payload(
                        seq=seq,
                        ts=ts,
                        tenant=tenant,
                        use_case=use_case,
                        actor=actor,
                        action=action,
                        details=details_obj,
                        prev_hash=prev_hash,
                    ),
                    self._key,
                )
                self._conn.execute(
                    f"INSERT INTO audit_log ({_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",  # noqa: S608
                    (
                        seq,
                        ts,
                        tenant,
                        use_case,
                        actor,
                        action,
                        details_text,
                        prev_hash,
                        entry_hash,
                    ),
                )
                self._conn.execute("COMMIT")
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
        return seq

    # ----------------------------------------------------------------- read
    @staticmethod
    def _row_to_entry(row: tuple[Any, ...]) -> AuditEntry:
        seq, ts, tenant, use_case, actor, action, details, prev_hash, entry_hash = row
        parsed = json.loads(details)
        if not isinstance(parsed, dict):
            parsed = {"_unlesbar": details}
        return AuditEntry(
            seq=int(seq),
            ts=str(ts),
            tenant=str(tenant),
            use_case=str(use_case),
            actor=str(actor),
            action=str(action),
            details=parsed,
            prev_hash=str(prev_hash),
            entry_hash=str(entry_hash),
        )

    def iter_entries(self) -> Iterator[AuditEntry]:
        """Alle Einträge in Kettenreihenfolge (alt nach neu)."""
        with self._lock:
            rows = self._conn.execute(
                f"SELECT {_COLUMNS} FROM audit_log ORDER BY seq ASC"  # noqa: S608
            ).fetchall()
        for row in rows:
            yield self._row_to_entry(row)

    def query(
        self,
        *,
        tenant: str | None = None,
        use_case: str | None = None,
        actor: str | None = None,
        action: str | None = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        """Neueste Einträge zuerst, optional gefiltert."""
        if limit < 1:
            raise ValueError("limit muss >= 1 sein")
        filters = {"tenant": tenant, "use_case": use_case, "actor": actor, "action": action}
        where = [f"{name} = ?" for name, value in filters.items() if value is not None]
        params: list[Any] = [value for value in filters.values() if value is not None]
        sql = f"SELECT {_COLUMNS} FROM audit_log"  # noqa: S608 - Spaltennamen sind fest
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY seq DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def count(self, *, tenant: str | None = None) -> int:
        """Anzahl Einträge (optional je Mandant)."""
        with self._lock:
            if tenant is None:
                row = self._conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()
            else:
                row = self._conn.execute(
                    "SELECT COUNT(*) FROM audit_log WHERE tenant = ?", (tenant,)
                ).fetchone()
        return int(row[0])

    def head(self) -> tuple[int, str]:
        """Laufnummer und Hash des letzten Eintrags (zum externen Verankern)."""
        with self._lock:
            row = self._conn.execute(
                "SELECT seq, entry_hash FROM audit_log ORDER BY seq DESC LIMIT 1"
            ).fetchone()
        return (int(row[0]), str(row[1])) if row else (0, GENESIS_HASH)

    # --------------------------------------------------------------- verify
    def verify(self, *, expected_head: tuple[int, str] | None = None) -> VerificationResult:
        """Ganze Kette prüfen (siehe :func:`verify_entries`)."""
        return verify_entries(self.iter_entries(), key=self._key, expected_head=expected_head)

    # --------------------------------------------------------------- export
    def export_jsonl(self, target: str | Path) -> Path:
        """Kette als JSON Lines exportieren (mit Hashes, extern prüfbar)."""
        path = Path(target)
        with path.open("w", encoding="utf-8", newline="\n") as fh:
            for entry in self.iter_entries():
                fh.write(canonical_json(entry.as_dict()) + "\n")
        return path

    def export_csv(self, target: str | Path) -> Path:
        """Kette als CSV exportieren (für Revision und Tabellenkalkulation)."""
        path = Path(target)
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(_COLUMNS.split(", "))
            for e in self.iter_entries():
                writer.writerow(
                    [
                        e.seq,
                        e.ts,
                        e.tenant,
                        e.use_case,
                        e.actor,
                        e.action,
                        canonical_json(dict(e.details)),
                        e.prev_hash,
                        e.entry_hash,
                    ]
                )
        return path

    def close(self) -> None:
        """Verbindung schliessen."""
        with self._lock:
            self._conn.close()


def read_jsonl(path: str | Path) -> Iterator[AuditEntry]:
    """Einträge aus einem JSON-Lines-Export lesen (für :func:`verify_entries`)."""
    with Path(path).open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            raw = json.loads(line)
            try:
                yield AuditEntry(
                    seq=int(raw["seq"]),
                    ts=str(raw["ts"]),
                    tenant=str(raw["tenant"]),
                    use_case=str(raw["use_case"]),
                    actor=str(raw["actor"]),
                    action=str(raw["action"]),
                    details=dict(raw["details"]),
                    prev_hash=str(raw["prev_hash"]),
                    entry_hash=str(raw["entry_hash"]),
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"Zeile {lineno}: ungültiger Export-Eintrag ({exc})") from exc


def verify_jsonl(
    path: str | Path,
    *,
    key: bytes | None = None,
    expected_head: tuple[int, str] | None = None,
) -> VerificationResult:
    """Einen JSON-Lines-Export ohne Datenbank prüfen."""
    return verify_entries(read_jsonl(path), key=key, expected_head=expected_head)


def parse_head(text: str) -> tuple[int, str]:
    """``"SEQ:HASH"`` in ein Tupel umwandeln (CLI-Hilfsfunktion)."""
    seq_text, sep, hash_text = text.partition(":")
    if not sep or not seq_text.isdigit() or len(hash_text) != 64:
        raise ValueError("Kopf muss die Form SEQ:HASH haben (HASH = 64 Hex-Zeichen)")
    try:
        int(hash_text, 16)
    except ValueError as exc:
        raise ValueError("HASH muss hexadezimal sein") from exc
    return int(seq_text), hash_text.lower()
