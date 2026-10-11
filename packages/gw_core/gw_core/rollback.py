"""Automatic-Rollback — technischer Rollback-Pfad über den Zielsystem-Adapter (Grad >= 4, GB-12).

Laut Roadmap (docs/roadmap-grad-03-05.md) war `automatic_rollback=true`
im JSON behauptet, aber **kein Code**: Die Lücke war der konkrete
Technik-Pfad, nicht die Idee. Diese Datei schliesst sie als **dritten,
jetzt im Repo liegenden Code-Baustein** für Grad >= 4:

1. **Vorher / Nachher** registrieren — der Zustand im Zielsystem VOR
   der Aktion, und was das Zielsystem NACH der Aktion zurückgegeben hat.
2. **Rollback-Befehl generieren** — die konkrete Reversal-Operation
   (z. B. `DELETE /kb_bill/12903`), deterministisch aus den Snapshots
   + dem deklarierten Template berechenbar.
3. **Ausführung protokollieren** — `durchgefuert` / `gescheitert`,
   Append-only: einmal abgeschlossen ist der Eintrag **final**.

Warum SQLite (und keine Redis / Postgres / JSON-Datei / In-Memory)
------------------------------------------------------------------
- Gleiche Storage-Schicht wie `audit.py` → null neue Dependencies.
- ACID + `threading.Lock` = atomar. In-Memory-DB wäre bei Neustart
  weg — genau der Moment, in dem man rollen müsste.
- Eine `.db`-Datei ist, was ein deployender Betreiber erwarten kann.

Warum «Spekulation» (Befehl generieren) und keine HTTP-Ausführung
-----------------------------------------------------------------
- `gw_core` bleibt transport-frei (kein `httpx`); der **Host** führt
  den Befehl gegen das Zielsystem aus.
- Gleiche Layer-Architektur wie die Freigabe-Queue: Core = Logik,
  Adapter = Transport.
- Machen den Baustein **portabel** über Zielsysteme (Bexio / Sage50 /
  DATEV / lokal) austauschbar.

Reversibilität ist eine **Eingabe**, nicht eine Annahme
---------------------------------------------------------
Nicht jede Aktion ist reversibel (z. B. eine gesendete E-Mail, eine
Banküberweisung). `registrieren` verlangt `reversibel` als Parameter;
`befehl()` wirft bei `reversibel=False` eine `RollbackUnmoeglichFehler`
mit klarer Begründung — ein **expliziter, prüfbarer Befund**, kein
stiller Noop.
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _jetzt() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


def _dj(v: dict | None) -> str:
    return json.dumps(v or {}, ensure_ascii=False, sort_keys=True)


def _ldj(s: str | None) -> dict:
    if not s:
        return {}
    try:
        out = json.loads(s)
        return out if isinstance(out, dict) else {}
    except (ValueError, TypeError):
        return {}


# --------------------------------------------------------------------------- #
# Fehler                                                                       #
# --------------------------------------------------------------------------- #
class RollbackFehler(RuntimeError):
    """Basis für alle Rollback-Fehlermeldungen."""


class RollbackUnmoeglichFehler(RollbackFehler):
    """Die Aktion ist explizit als nicht-reversibel registriert."""

    def __init__(self, grund: str, eintrag_id: int) -> None:
        super().__init__(f"Eintrag #{eintrag_id} nicht reversibel: {grund}")
        self.grund = grund
        self.eintrag_id = eintrag_id


class RollbackEintragNichtGefundenFehler(RollbackFehler):
    def __init__(self, eintrag_id: int) -> None:
        super().__init__(f"Rollback-Eintrag #{eintrag_id} existiert nicht.")
        self.eintrag_id = eintrag_id


class RollbackBereitsAbgeschlossenFehler(RollbackFehler):
    def __init__(self, eintrag_id: int, status: str) -> None:
        super().__init__(
            f"Eintrag #{eintrag_id} ist bereits '{status}' — "
            f"Append-only: kein Ändern."
        )
        self.eintrag_id = eintrag_id
        self.status = status


class MissingRollbackParameterFehler(RollbackFehler):
    """Ein Template-Platzhalter findet keinen Wert in nachher_state."""

    def __init__(self, parameter: str, eintrag_id: int, nachricht: str) -> None:
        super().__init__(nachricht)
        self.parameter = parameter
        self.eintrag_id = eintrag_id


# --------------------------------------------------------------------------- #
# Datenobjekte                                                                 #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class RollbackEintrag:
    """Eine registrierte, reversibele (oder explizit nicht) Aktion."""

    id: int
    ts: str
    mandant: str
    prototyp: str
    actor: str
    beschreibung: str
    reversibel: bool
    vorher_state: dict
    vorher_quelle: str
    nachher_state: dict
    nachher_quelle: str
    einkehren_template: dict
    grund: str
    status: str               # offen | durchgefuert | gescheitert
    status_begruendung: str | None
    aufgabe_von: str | None


@dataclass(frozen=True)
class RollbackBefehl:
    """Der konkrete Reversal-Befehl, deterministisch aus dem Eintrag.

    `parameter` ist ein sortiertes Tuple von `(key, value)`-Paaren.
    Der Host (Kunden-Deployment) führt den Befehl gegen das Zielsystem
    aus — dieser Baustein tut es nicht selbst (Layer-Architektur).
    """

    methode: str
    endpunkt: str
    parameter: tuple[tuple[str, Any], ...]
    begruendung: str
    zugehoerig: int

    def als_dict(self) -> dict:
        return {
            "methode": self.methode,
            "endpunkt": self.endpunkt,
            "parameter": dict(self.parameter),
            "begruendung": self.begruendung,
            "eintrag_id": self.zugehoerig,
        }


# --------------------------------------------------------------------------- #
# Schema                                                                       #
# --------------------------------------------------------------------------- #
_SCHEMA = """
CREATE TABLE IF NOT EXISTS rollback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    mandant TEXT NOT NULL,
    prototyp TEXT NOT NULL,
    actor TEXT NOT NULL,
    beschreibung TEXT NOT NULL,
    reversibel INTEGER NOT NULL,
    vorher_state TEXT NOT NULL,
    vorher_quelle TEXT NOT NULL,
    nachher_state TEXT NOT NULL,
    nachher_quelle TEXT NOT NULL,
    einkehren_template TEXT NOT NULL,
    grund TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'offen',
    status_begruendung TEXT,
    status_ums TEXT,
    aufgabe_von TEXT
);
CREATE INDEX IF NOT EXISTS idx_rb_mandant ON rollback (mandant);
CREATE INDEX IF NOT EXISTS idx_rb_prototyp ON rollback (prototyp);
"""

_COLUMNEN = (
    "id", "ts", "mandant", "prototyp", "actor", "beschreibung",
    "reversibel", "vorher_state", "vorher_quelle", "nachher_state",
    "nachher_quelle", "einkehren_template", "grund", "status",
    "status_begruendung", "status_ums", "aufgabe_von",
)


def _row_to_dict(row: tuple) -> dict:
    return dict(zip(_COLUMNEN, row))


def _entry_from_dict(d: dict) -> RollbackEintrag:
    return RollbackEintrag(
        id=int(d["id"]),
        ts=d["ts"],
        mandant=d["mandant"],
        prototyp=d["prototyp"],
        actor=d["actor"],
        beschreibung=d["beschreibung"],
        reversibel=bool(d["reversibel"]),
        vorher_state=_ldj(d.get("vorher_state")),
        vorher_quelle=d.get("vorher_quelle", ""),
        nachher_state=_ldj(d.get("nachher_state")),
        nachher_quelle=d.get("nachher_quelle", ""),
        einkehren_template=_ldj(d.get("einkehren_template")),
        grund=d.get("grund", ""),
        status=d["status"],
        status_begruendung=d.get("status_begruendung"),
        aufgabe_von=d.get("aufgabe_von"),
    )


# --------------------------------------------------------------------------- #
# Core                                                                         #
# --------------------------------------------------------------------------- #
class RollbackManager:
    """Technisch durchsetzbarer Rollback-Pfad (Grad >= 4, GB-12).

    Typischer Lauf (Bexio-Beispiel):

        rb = RollbackManager()
        rid = rb.registrieren(
            mandant="K1", prototyp="04", actor="agent-01",
            beschreibung="Rechnung RE-2026-0042 gebucht (1281.00 CHF)",
            reversibel=True,
            vorher_state={},
            nachher_state={"bexio_id": 12903},
            einkehren_template={
                "methode": "DELETE",
                "endpoint": "/kb_bill/{bexio_id}",
            },
            grund="GB-12: jede wirkungsvolle Aktion braucht einen Rollback-Pfad",
        )
        befehl = rb.befehl(rid)
        # → DELETE /kb_bill/12903
        # Host führt den Befehl aus, z. B.:
        #   resp = httpx.delete(f"{base}/kb_bill/12903", headers=auth)
        rb.ausfuehren(rid, success=True, resultat="Buchung #12903 gelöscht",
                      on_behalf_of="Edin")
        # Append-only: ein zweiter Aufruf wirft
        # RollbackBereitsAbgeschlossenFehler.
    """

    def __init__(self, dbpath: str | Path = ":memory:") -> None:
        # RLock: `ausfuehren()` hält das Lock und ruft `_lesse()` auf,
        # das es ebenfalls braucht — ein normales Lock würde hier
        # self-deadlock. RLock ist der minimale, korrekte Fix.
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(dbpath), check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # ------------------------------------------------------------------ #
    # 1 · Registrieren                                                    #
    # ------------------------------------------------------------------ #
    def registrieren(
        self,
        *,
        mandant: str,
        prototyp: str,
        actor: str,
        beschreibung: str,
        reversibel: bool,
        vorher_state: dict | None = None,
        vorher_quelle: str = "system",
        nachher_state: dict | None = None,
        nachher_quelle: str = "zielsystem",
        einkehren_template: dict | None = None,
        grund: str = "",
        ts: str | None = None,
    ) -> int:
        """Aktion mit Vorher/Nachher-Snapshots registrieren.

        `reversibel=False` ist ein **bewusster** Befund (z. B. Banküber-
        weisung): `befehl()` wirft `RollbackUnmoeglichFehler` mit der
        Begründung. Das ist ein prüfbares Ergebnis, kein stiller Noop.

        `einkehren_template` erwartet mindestens `methode`.
        Platzhalter `{name}` im Template werden von `befehl()` durch die
        `nachher_state`-Werte ersetzt.

        Wirft:
            ValueError — reversibel=True aber kein Template mit Methode.
        """
        if reversibel and not (einkehren_template or {}).get("methode"):
            raise ValueError(
                "reversibel=True verlangt ein einkehren_template "
                "mit mindestens dem Feld 'methode'."
            )
        now = ts or _jetzt()
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO rollback (ts, mandant, prototyp, actor, beschreibung,"
                " reversibel, vorher_state, vorher_quelle, nachher_state,"
                " nachher_quelle, einkehren_template, grund) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    now, mandant, prototyp, actor, beschreibung,
                    int(reversibel), _dj(vorher_state), vorher_quelle,
                    _dj(nachher_state), nachher_quelle,
                    _dj(einkehren_template or {}), grund,
                ),
            )
            self._conn.commit()
            if cur.lastrowid is None:
                raise RuntimeError("registrieren: INSERT lieferte keine Zeile-ID")
            return int(cur.lastrowid)

    # ------------------------------------------------------------------ #
    # 2 · Befehl generieren (deterministisch)                             #
    # ------------------------------------------------------------------ #
    def befehl(self, eintrag_id: int) -> RollbackBefehl:
        """Konkreten Reversal-Befehl aus Template + nachher_state bauen.

        Deterministisch: gleicher Eintrag → gleicher Befehl.

        Platzhalter-Substitution:
            Template:  {"methode": "DELETE", "endpoint": "/kb_bill/{bexio_id}"}
            nachher:   {"bexio_id": 12903}
            Befehl:    DELETE /kb_bill/12903

        `parameter` im Template ist optional und folgt demselben Substitu-
        ierungsweg; das Ergebnis wird als sortiertes Tuple gespeichert.

        Wirft:
            RollbackUnmoeglichFehler      — reversibel=False
            MissingRollbackParameterFehler — Platzhalter ohne Wert in nachher
            RollbackEintragNichtGefundenFehler
        """
        d = self._lesse(eintrag_id)
        if not d["reversibel"]:
            raise RollbackUnmoeglichFehler(d["grund"] or "keine Angabe", eintrag_id)

        nachher = _ldj(d["nachher_state"])
        template = _ldj(d["einkehren_template"])

        def _sub(m: re.Match[str]) -> str:
            key = m.group(1)
            if key not in nachher:
                raise MissingRollbackParameterFehler(
                    key, eintrag_id,
                    f"Template-Platzhalter '{{{key}}}' findet keinen Wert "
                    f"in nachher_state (gibt: {list(nachher)})",
                )
            return str(nachher[key])

        def _fill(val: Any) -> Any:
            if isinstance(val, str):
                return re.sub(r"{(\w+)}", _sub, val)
            if isinstance(val, dict):
                return {k: _fill(v) for k, v in val.items()}
            if isinstance(val, list):
                return [_fill(v) for v in val]
            return val

        filled = _fill(template)
        methode = str(filled.get("methode", ""))
        if not methode:
            raise RollbackFehler(
                f"Eintrag #{eintrag_id}: reversibel=true, aber Template "
                f"hat kein 'methode'-Feld."
            )
        endpunkt = str(filled.get("endpoint", ""))
        parameter_raw = filled.get("parameter") or {}
        if not isinstance(parameter_raw, dict):
            raise RollbackFehler(
                f"Eintrag #{eintrag_id}: 'parameter' im Template muss "
                f"ein dict sein, ist {type(parameter_raw).__name__}."
            )
        paare = tuple(sorted((str(k), v) for k, v in parameter_raw.items()))
        return RollbackBefehl(
            methode=methode,
            endpunkt=endpunkt,
            parameter=paare,
            begruendung=d["grund"],
            zugehoerig=eintrag_id,
        )

    # ------------------------------------------------------------------ #
    # 3 · Ausführung protokollieren (Append-only)                         #
    # ------------------------------------------------------------------ #
    def ausfuehren(
        self,
        eintrag_id: int,
        *,
        success: bool,
        resultat: str,
        on_behalf_of: str,
        ts: str | None = None,
    ) -> RollbackEintrag:
        """Rollback als `durchgefuert` oder `gescheitert` abschliessen.

        Append-only: einmal abgeschlossen ist der Eintrag final.
        Ein zweiter Aufruf für denselben Eintrag wirft
        `RollbackBereitsAbgeschlossenFehler` — das ist die technische
        Antwort auf «wer hat wann was getäuscht» (GB-11).

        Parameter:
            success      — True = Zielsystem hat den Befehl ausgeführt.
            resultat     — Ergebnis-Text vom Zielsystem (z. B. HTTP-Status).
            on_behalf_of — wer hat es veranlasst (für Audit-Trail).

        Wirft:
            RollbackEintragNichtGefundenFehler
            RollbackBereitsAbgeschlossenFehler
        """
        with self._lock:
            d = self._lesse(eintrag_id)
            if d["status"] != "offen":
                raise RollbackBereitsAbgeschlossenFehler(
                    eintrag_id, d["status"]
                )
            self._conn.execute(
                "UPDATE rollback SET status=?, status_begruendung=?,"
                " status_ums=?, aufgabe_von=? WHERE id=?",
                (
                    "durchgefuert" if success else "gescheitert",
                    resultat[:512],
                    ts or _jetzt(),
                    on_behalf_of,
                    eintrag_id,
                ),
            )
            self._conn.commit()
        return self._read(eintrag_id)

    # ------------------------------------------------------------------ #
    # 4 · Lesen                                                           #
    # ------------------------------------------------------------------ #
    def read(self, eintrag_id: int) -> RollbackEintrag:
        """Vollständigen Eintrag lesen (inkl. Status nach Execution)."""
        return self._read(eintrag_id)

    def _read(self, eintrag_id: int) -> RollbackEintrag:
        d = self._lesse(eintrag_id)
        return _entry_from_dict(d)

    def offene(
        self, *, mandant: str | None = None, limit: int = 100
    ) -> list[RollbackEintrag]:
        """Offene (noch nicht abgearbeitete) Rollback-Einträge."""
        with self._lock:
            where: list[str] = ["status='offen'"]
            params: list[object] = []
            if mandant is not None:
                where.append("mandant=?")
                params.append(mandant)
            sql = (
                f"SELECT {', '.join(_COLUMNEN)} FROM rollback "
                f"WHERE {' AND '.join(where)} ORDER BY id ASC LIMIT ?"
            )
            params.append(limit)
            rows = self._conn.execute(sql, params).fetchall()
        return [_entry_from_dict(_row_to_dict(r)) for r in rows]

    def zähler(self, *, mandant: str | None = None) -> dict:
        """KPI: Anzahl je Status (für Monitoring)."""
        with self._lock:
            where: list[str] = []
            params: list[object] = []
            if mandant is not None:
                where.append("mandant=?")
                params.append(mandant)
            sql = "SELECT status, COUNT(*) FROM rollback"
            if where:
                sql += f" WHERE {' AND '.join(where)}"
            sql += " GROUP BY status"
            rows = self._conn.execute(sql, params).fetchall()
        return {
            "offen": sum(c for s, c in rows if s == "offen"),
            "durchgefuert": sum(c for s, c in rows if s == "durchgefuert"),
            "gescheitert": sum(c for s, c in rows if s == "gescheitert"),
            "total": sum(c for _, c in rows),
        }

    def schliesse(self) -> None:
        with self._lock:
            self._conn.close()

    # ------------------------------------------------------------------ #
    # Intern                                                              #
    # ------------------------------------------------------------------ #
    def _lesse(self, eintrag_id: int) -> dict:
        """Interne Lese (verwaltet das Lock, gibt dict oder Raise)."""
        with self._lock:
            row = self._conn.execute(
                f"SELECT {', '.join(_COLUMNEN)} FROM rollback WHERE id=?",
                (eintrag_id,),
            ).fetchone()
        if row is None:
            raise RollbackEintragNichtGefundenFehler(eintrag_id)
        return _row_to_dict(row)
