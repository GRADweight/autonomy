"""Audit-Trail: Hash-Kette, Manipulationserkennung, Export."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from gradweight_autonomy.audit import (
    GENESIS_HASH,
    AuditConfigurationError,
    AuditEntry,
    AuditTrail,
    compute_hash,
    entry_payload,
    parse_head,
    read_jsonl,
    verify_entries,
    verify_jsonl,
)

KEY = b"0123456789abcdef0123456789abcdef"


class FixedClock:
    def __init__(self) -> None:
        self.t = datetime(2026, 10, 1, 8, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        self.t += timedelta(seconds=1)
        return self.t


def _filled(path: Path | str = ":memory:", n: int = 5, key: bytes | None = None) -> AuditTrail:
    trail = AuditTrail(path, hmac_key=key, clock=FixedClock())
    for i in range(n):
        trail.append(
            tenant="K1",
            use_case="kreditoren",
            actor="ki" if i % 2 == 0 else "buchhaltung",
            action=f"schritt_{i}",
            details={"i": i, "betrag": f"{100 + i}.00"},
        )
    return trail


def _raw(path: Path) -> sqlite3.Connection:
    """Direkter Zugriff wie ein Angreifer mit Dateizugriff: Trigger entfernen."""
    conn = sqlite3.connect(path)
    conn.execute("DROP TRIGGER audit_log_no_update")
    conn.execute("DROP TRIGGER audit_log_no_delete")
    return conn


def test_append_returns_sequential_numbers_and_chain_links() -> None:
    trail = _filled(n=3)
    entries = list(trail.iter_entries())
    assert [e.seq for e in entries] == [1, 2, 3]
    assert entries[0].prev_hash == GENESIS_HASH
    assert entries[1].prev_hash == entries[0].entry_hash
    assert trail.head() == (3, entries[2].entry_hash)
    result = trail.verify()
    assert result.ok
    assert result.entries_checked == 3
    assert "intakt" in result.summary()


def test_empty_trail_verifies_and_has_genesis_head() -> None:
    trail = AuditTrail()
    assert trail.head() == (0, GENESIS_HASH)
    assert trail.verify().ok
    assert trail.count() == 0


def test_hash_matches_documented_payload() -> None:
    trail = _filled(n=1)
    e = next(trail.iter_entries())
    payload = entry_payload(
        seq=e.seq,
        ts=e.ts,
        tenant=e.tenant,
        use_case=e.use_case,
        actor=e.actor,
        action=e.action,
        details=e.details,
        prev_hash=e.prev_hash,
    )
    assert payload.startswith(b'{"action":"schritt_0"')
    assert compute_hash(payload) == e.entry_hash


def test_update_and_delete_are_blocked_by_triggers(tmp_path: Path) -> None:
    db = tmp_path / "audit.db"
    _filled(db).close()
    conn = sqlite3.connect(db)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE audit_log SET actor = 'x' WHERE seq = 1")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM audit_log WHERE seq = 1")
    conn.close()


def test_modified_details_are_detected(tmp_path: Path) -> None:
    db = tmp_path / "audit.db"
    _filled(db).close()
    conn = _raw(db)
    conn.execute("""UPDATE audit_log SET details = '{"betrag":"999.00","i":2}' WHERE seq = 3""")
    conn.commit()
    conn.close()
    result = AuditTrail(db).verify()
    assert not result.ok
    assert [(p.seq, p.kind) for p in result.problems] == [(3, "hash")]
    assert "verletzt" in result.summary()


def test_modified_actor_is_detected(tmp_path: Path) -> None:
    db = tmp_path / "audit.db"
    _filled(db).close()
    conn = _raw(db)
    conn.execute("UPDATE audit_log SET actor = 'cfo' WHERE seq = 2")
    conn.commit()
    conn.close()
    assert {p.kind for p in AuditTrail(db).verify().problems} == {"hash"}


def test_deleted_entry_in_the_middle_is_detected(tmp_path: Path) -> None:
    db = tmp_path / "audit.db"
    _filled(db).close()
    conn = _raw(db)
    conn.execute("DELETE FROM audit_log WHERE seq = 3")
    conn.commit()
    conn.close()
    result = AuditTrail(db).verify()
    kinds = {(p.seq, p.kind) for p in result.problems}
    assert (4, "gap") in kinds
    assert (4, "link") in kinds


def test_deleted_first_entry_is_detected(tmp_path: Path) -> None:
    db = tmp_path / "audit.db"
    _filled(db).close()
    conn = _raw(db)
    conn.execute("DELETE FROM audit_log WHERE seq = 1")
    conn.commit()
    conn.close()
    assert not AuditTrail(db).verify().ok


def test_reordering_is_detected(tmp_path: Path) -> None:
    db = tmp_path / "audit.db"
    _filled(db).close()
    conn = _raw(db)
    # Inhalte von 2 und 4 tauschen, Laufnummern bleiben (klassische Umordnung).
    rows = {
        r[0]: r[1:]
        for r in conn.execute(
            "SELECT seq, ts, actor, action, details, prev_hash, entry_hash FROM audit_log"
        )
    }
    for target, source in ((2, 4), (4, 2)):
        conn.execute(
            "UPDATE audit_log SET ts=?, actor=?, action=?, details=?, prev_hash=?, entry_hash=? "
            "WHERE seq=?",
            (*rows[source], target),
        )
    conn.commit()
    conn.close()
    result = AuditTrail(db).verify()
    assert not result.ok
    assert {p.seq for p in result.problems} >= {2, 4}


def test_recomputed_chain_without_key_needs_external_anchor(tmp_path: Path) -> None:
    """Ohne Schlüssel kann ein Angreifer die Kette neu rechnen – nur der Anker hilft."""
    db = tmp_path / "audit.db"
    trail = _filled(db)
    anchor = trail.head()
    trail.close()
    conn = _raw(db)
    rows = conn.execute(
        "SELECT seq, ts, tenant, use_case, actor, action, details FROM audit_log ORDER BY seq"
    ).fetchall()
    prev = GENESIS_HASH
    for seq, ts, tenant, use_case, actor, action, details in rows:
        new_details = json.loads(details)
        if seq == 2:
            new_details["betrag"] = "1.00"
        h = compute_hash(
            entry_payload(
                seq=seq,
                ts=ts,
                tenant=tenant,
                use_case=use_case,
                actor=actor,
                action=action,
                details=new_details,
                prev_hash=prev,
            )
        )
        conn.execute(
            "UPDATE audit_log SET details=?, prev_hash=?, entry_hash=? WHERE seq=?",
            (json.dumps(new_details, sort_keys=True, separators=(",", ":")), prev, h, seq),
        )
        prev = h
    conn.commit()
    conn.close()
    reopened = AuditTrail(db)
    assert reopened.verify().ok, "ohne Anker ist eine vollständige Neuberechnung unsichtbar"
    anchored = reopened.verify(expected_head=anchor)
    assert not anchored.ok
    assert anchored.problems[0].kind == "anchor"


def test_truncation_is_detected_with_anchor(tmp_path: Path) -> None:
    db = tmp_path / "audit.db"
    trail = _filled(db)
    anchor = trail.head()
    trail.close()
    conn = _raw(db)
    conn.execute("DELETE FROM audit_log WHERE seq >= 4")
    conn.commit()
    conn.close()
    reopened = AuditTrail(db)
    assert reopened.verify().ok
    result = reopened.verify(expected_head=anchor)
    assert not result.ok
    assert "fehlt" in result.problems[0].detail


def test_hmac_chain_cannot_be_recomputed_without_key(tmp_path: Path) -> None:
    db = tmp_path / "audit.db"
    _filled(db, key=KEY).close()
    conn = _raw(db)
    rows = conn.execute("SELECT seq, ts, tenant, use_case, actor, action FROM audit_log").fetchall()
    prev = GENESIS_HASH
    for seq, ts, tenant, use_case, actor, action in rows:
        h = compute_hash(
            entry_payload(
                seq=seq,
                ts=ts,
                tenant=tenant,
                use_case=use_case,
                actor=actor,
                action=action,
                details={"gefälscht": True},
                prev_hash=prev,
            )
        )  # ohne Schlüssel
        conn.execute(
            "UPDATE audit_log SET details=?, prev_hash=?, entry_hash=? WHERE seq=?",
            ('{"gefälscht":true}', prev, h, seq),
        )
        prev = h
    conn.commit()
    conn.close()
    result = AuditTrail(db, hmac_key=KEY).verify()
    assert not result.ok
    assert all(p.kind == "hash" for p in result.problems)


def test_wrong_or_missing_key_is_rejected(tmp_path: Path) -> None:
    db = tmp_path / "audit.db"
    _filled(db, key=KEY).close()
    with pytest.raises(AuditConfigurationError):
        AuditTrail(db)
    with pytest.raises(AuditConfigurationError):
        AuditTrail(db, hmac_key=b"another-key-with-16+bytes")
    assert AuditTrail(db, hmac_key=KEY).verify().ok


def test_short_key_rejected() -> None:
    with pytest.raises(ValueError, match="16 Bytes"):
        AuditTrail(hmac_key=b"short")


def test_append_validates_input() -> None:
    trail = AuditTrail()
    with pytest.raises(ValueError, match="actor"):
        trail.append(tenant="K", use_case="u", actor="", action="a")
    with pytest.raises(ValueError, match="kanonisches JSON"):
        trail.append(tenant="K", use_case="u", actor="x", action="a", details={"x": object()})
    with pytest.raises(ValueError, match="kanonisches JSON"):
        trail.append(tenant="K", use_case="u", actor="x", action="a", details={"x": float("nan")})
    assert trail.count() == 0


def test_query_filters_and_limit() -> None:
    trail = _filled(n=6)
    trail.append(tenant="K2", use_case="x", actor="hr", action="other")
    assert trail.count() == 7
    assert trail.count(tenant="K2") == 1
    newest = trail.query(limit=2)
    assert [e.seq for e in newest] == [7, 6]
    assert [e.actor for e in trail.query(actor="buchhaltung")] == ["buchhaltung"] * 3
    assert trail.query(tenant="K1", action="schritt_0")[0].details["i"] == 0
    with pytest.raises(ValueError, match="limit"):
        trail.query(limit=0)


def test_export_jsonl_roundtrip_and_tamper_detection(tmp_path: Path) -> None:
    trail = _filled(n=4)
    path = trail.export_jsonl(tmp_path / "audit.jsonl")
    assert verify_jsonl(path).ok
    assert [e.seq for e in read_jsonl(path)] == [1, 2, 3, 4]
    lines = path.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(lines[1])
    tampered["action"] = "geaendert"
    lines[1] = json.dumps(tampered)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = verify_jsonl(path, expected_head=trail.head())
    assert not result.ok
    assert result.problems[0].seq == 2


def test_export_jsonl_detects_dropped_line(tmp_path: Path) -> None:
    trail = _filled(n=4)
    path = trail.export_jsonl(tmp_path / "audit.jsonl")
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join([lines[0], lines[2], lines[3]]) + "\n", encoding="utf-8")
    assert not verify_jsonl(path).ok


def test_export_jsonl_reordered_lines_detected(tmp_path: Path) -> None:
    trail = _filled(n=3)
    path = trail.export_jsonl(tmp_path / "audit.jsonl")
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join([lines[1], lines[0], lines[2]]) + "\n", encoding="utf-8")
    kinds = {p.kind for p in verify_jsonl(path).problems}
    assert "order" in kinds or "gap" in kinds


def test_read_jsonl_rejects_malformed_line(tmp_path: Path) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text('{"seq": 1}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="Zeile 1"):
        list(read_jsonl(path))


def test_export_csv_contains_hashes(tmp_path: Path) -> None:
    trail = _filled(n=2)
    text = trail.export_csv(tmp_path / "audit.csv").read_text(encoding="utf-8")
    assert text.splitlines()[0].endswith("prev_hash,entry_hash")
    assert trail.head()[1] in text


def test_parse_head() -> None:
    h = "a" * 64
    assert parse_head(f"12:{h}") == (12, h)
    for bad in ("12", f"x:{h}", "1:abc", "1:" + "z" * 64):
        with pytest.raises(ValueError, match=r"SEQ:HASH|hexadezimal"):
            parse_head(bad)


def test_concurrent_writers_keep_chain_intact(tmp_path: Path) -> None:
    """Zwei Verbindungen auf dieselbe Datei, mehrere Threads: Kette bleibt lückenlos."""
    db = tmp_path / "audit.db"
    a = AuditTrail(db)
    b = AuditTrail(db)

    def worker(trail: AuditTrail, name: str) -> None:
        for i in range(25):
            trail.append(tenant="K", use_case="u", actor=name, action="a", details={"i": i})

    threads = [
        threading.Thread(target=worker, args=(t, f"w{i}")) for i, t in enumerate((a, b, a, b))
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    result = AuditTrail(db).verify()
    assert result.ok
    assert result.entries_checked == 100


@settings(max_examples=40, deadline=None)
@given(
    details=st.lists(
        st.dictionaries(
            st.text(min_size=1, max_size=8),
            st.one_of(st.integers(), st.text(max_size=12), st.booleans(), st.none()),
            max_size=4,
        ),
        min_size=1,
        max_size=6,
    ),
    victim=st.integers(min_value=0, max_value=5),
)
def test_any_single_field_change_is_detected(details: list[dict[str, object]], victim: int) -> None:
    trail = AuditTrail(clock=FixedClock())
    for d in details:
        trail.append(tenant="K", use_case="u", actor="a", action="x", details=d)
    entries = [e.as_dict() for e in trail.iter_entries()]
    idx = victim % len(entries)
    entries[idx]["actor"] = entries[idx]["actor"] + "!"
    result = verify_entries(AuditEntry(**e) for e in entries)
    assert not result.ok
    assert result.problems[0].seq == idx + 1
