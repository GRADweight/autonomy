"""ExceptionQueue — deterministische Ausnahme-Entlastung (GB-11, Grad >= 4).

Laut Roadmap (docs/roadmap-grad-03-05.md) fehlt für Grad >= 4 der Code für
`exception_queue=true`: das Modell behauptet den Kontrollpunkt, aber es gab
einen, der ihn erzwingt. Das ist dieser Baukasten.

Was er tut
---------
Wenn ein Aktions-Entwurf eine Schwelle überschreitet (Geld-Limit,
sensible Daten, Fehlerhäufung), muss er **deterministisch** einem Menschen
zugewiesen werden — nicht «wenn das Modell es für gut hält», sondern weil
die Policy es sagt. Genau das ist die «deterministischen Policy-Schicht»,
die Grad 5 in GB-11 verlangt.

Design
------
- Null Dependencies (stdlib + gw_core.audit) — läuft offline, thread-sicher.
- Deterministisch: gleiche Eingabe -> gleicher Entscheid. Kein Zufall.
  Das macht die Policy testbar und in der Revision nachvollziehbar.
- Append-only: Einträge können entlastet (entschieden) werden, aber nie
  gelöscht oder zurückgesetzt.
- Jeder Entscheider (menschlich oder systemische Einreihung) landet im
  Audit-Trail, damit die Kette geschlossen ist (GB-11).
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from gw_core.audit import AuditTrail

_STATUS_OFFEN = "offen"
_STATUS_ENTLASTET = "entlastet"
_STATUS_ABGELEHNT = "abgelehnt"
_GULTIGE_ZIEL = {_STATUS_OFFEN, _STATUS_ENTLASTET, _STATUS_ABGELEHNT}


def _jetzt() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


@dataclass(frozen=True)
class ExceptionEntscheid:
    """Ergebnis einer deterministischen Policy-Prüfung.

    `obliegt_mensch` = True, wenn die Aktion einem Menschen entlastet
    werden muss (Schwelle überschritten). `grund` + `regel` erklären
    den Befund — immer für die Kette (Audit) und für die Revision.
    """

    obliegt_mensch: bool
    grund: str
    rule: str = ""


@dataclass(frozen=True)
class Ausnahme:
    """Ein in die Queue eingerührtes, offenes oder entschieden-Element."""

    id: int
    mandant: str
    prototyp: str
    titel: str
    payload: dict
    status: str
    grund: str
    rule: str
    vorgeschlagen_von: str
    angelegt_um: str
    erledigt_um: str | None = None
    erledigt_von: str | None = None


# --------------------------------------------------------------------------- #
# Policy (die deterministische Logik — vom Code-Entwurf unabhängig)           #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ExceptionPolicy:
    """Schwellen, die ein Entlastungs-Befund auslösen. Alle optional.

    Keine der Schwellen gesetzt -> `obliegt_mensch` immer False
    (reiner Durchlass, z. B. für Grad 1/2, wo die Policy nicht greift).
    """

    geld_limit: float | None = None        # Betrag (Brutto); > limit -> Ausnahme
    sensible_erfordert_klarung: bool = False   # sensible Daten -> immer Ausnahme
    fehlerschwelle: int | None = None    # > fehler_zähler -> Ausnahme (Circuit-Breaker)


def _entscheide(
    policy: ExceptionPolicy,
    *,
    betrag: float = 0.0,
    sensible: bool = False,
    fehler_zaehler: int = 0,
) -> ExceptionEntscheid:
    # 1) Geld-Limit (GB-09): Limit gehört in den system, nicht im Prompt.
    if policy.geld_limit is not None and betrag > policy.geld_limit:
        return ExceptionEntscheid(
            True,
            f"Betrag {betrag:.2f} über Limit {policy.geld_limit:.2f}",
            "GB-09",
        )
    # 2) Sensible Daten -> menschliche Klärung (GB-15, Datenklasse).
    if sensible and policy.sensible_erfordert_klarung:
        return ExceptionEntscheid(
            True, "sensible Daten — menschliche Klärung erforderlich",
            "GB-15",
        )
    # 3) Fehlerhäufung (Circuit-Breaker, GB-12/GB-13).
    if policy.fehlerschwelle is not None and fehler_zaehler > policy.fehlerschwelle:
        return ExceptionEntscheid(
            True,
            f"Fehlerhäufung {fehler_zaehler} > Schwellwert {policy.fehlerschwelle}",
            "GB-12",
        )
    return ExceptionEntscheid(False, "keine Schwelle überschritten", "")


# --------------------------------------------------------------------------- #
# ExceptionQueue                                                              #
# --------------------------------------------------------------------------- #
_SCHEMA = """
CREATE TABLE IF NOT EXISTS ausnahmen (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mandant TEXT NOT NULL,
    prototyp TEXT NOT NULL,
    titel TEXT NOT NULL,
    payload TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'offen',
    grund TEXT NOT NULL,
    regel TEXT NOT NULL DEFAULT '',
    vorgeschlagen_von TEXT NOT NULL,
    angelegt_um TEXT NOT NULL,
    erledigt_um TEXT,
    erledigt_von TEXT
);
CREATE INDEX IF NOT EXISTS idx_ausnahmen_mandant ON ausnahmen (mandant);
CREATE INDEX IF NOT EXISTS idx_ausnahmen_status ON ausnahmen (status);
"""


class ExceptionQueue:
    """Deterministische Queue für ausserirdentliche Fälle (Grad >= 4).

    Typischer Lauf:
      audit = AuditTrail()
      q = ExceptionQueue(audit=audit,
                         policy=ExceptionPolicy(geld_limit=2000.0))
      eids = []
      for vorschlag in antritte:
          bescheid = q.pruefe(vorschlag.betrag, vorschlag.sensible)
          if bescheid.obliegt_mensch:
              eids.append(q.einrei(mandant="K1", prototyp="04",
                                   titel=vorschlag.titel, payload=vorschlag.payload,
                                   entscheid=bescheid))
      # Menschen entlasten jede offene Ausnahme:
      q.entscheide(eids[0], actor="ai-lead", status="entlastet")
    """

    def __init__(
        self,
        dbpath: str | Path | None = None,
        audit: AuditTrail | None = None,
        policy: ExceptionPolicy | None = None,
    ):
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(
            str(dbpath) if dbpath is not None else ":memory:",
            check_same_thread=False,
        )
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        self._audit = audit or AuditTrail()
        self._policy = policy or ExceptionPolicy()

    # ------------------------------------------------------------------ #
    # Prüfen (deterministisch)                                           #
    # ------------------------------------------------------------------ #
    def pruefe(
        self,
        *,
        betrag: float = 0.0,
        sensible: bool = False,
        fehler_zaehler: int = 0,
    ) -> ExceptionEntscheid:
        """Deterministisch prüfen, ob eine Aktion entlastet werden muss.

        Gibt einen `ExceptionEntscheid` zurück (kein Seiteneffekt).
        Der Befund ist reproduzierbar: gleiche Schwellen + gleiche Werte
        -> immer dasselbe Ergebnis. Das ist es, was «deterministisch»
        heisst — und woran Revision / Test sich hält.
        """
        return _entscheide(
            self._policy,
            betrag=betrag,
            sensible=sensible,
            fehler_zaehler=fehler_zaehler,
        )

    # ------------------------------------------------------------------ #
    # Einreichen                                                         #
    # ------------------------------------------------------------------ #
    def einrei(
        self,
        *,
        mandant: str,
        prototyp: str,
        titel: str,
        payload: dict,
        entscheid: ExceptionEntscheid,
        vorgeschlagen_von: str = "system",
    ) -> int:
        """Eine Ausnahme in die Queue einrei (Status 'offen').

        Der `entscheid` wird mitgespeichert (grund + regel), damit die Kette
        auch nachträglich erklärt werden kann — «warum lag das hier?»
        """
        payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO ausnahmen (mandant, prototyp, titel, payload, "
                "status, grund, regel, vorgeschlagen_von, angelegt_um) "
                "VALUES (?, ?, ?, ?, 'offen', ?, ?, ?, ?)",
                (
                    mandant,
                    prototyp,
                    titel,
                    payload_json,
                    entscheid.grund,
                    entscheid.rule,
                    vorgeschlagen_von,
                    _jetzt(),
                ),
            )
            self._conn.commit()
            new_id = cur.lastrowid
            if new_id is None:
                raise RuntimeError("INSERT lieferte keine Zeile-ID")
        self._audit.log(
            mandant=mandant,
            prototyp=prototyp,
            actor=vorgeschlagen_von,
            action="ausnahme_einreichte",
            details={
                "ausnahme_id": int(new_id),
                "titel": titel,
                "grund": entscheid.grund,
                "regel": entscheid.rule,
            },
        )
        return int(new_id)

    # ------------------------------------------------------------------ #
    # Entscheiden (menschlich entlastet / abgelehnt)                     #
    # ------------------------------------------------------------------ #
    def entscheide(
        self,
        ausnahme_id: int,
        *,
        status: str,
        actor: str,
        begründung: str = "",
    ) -> Ausnahme:
        """Eine offene Ausnahme entscheiden (-> 'entlastet' | 'abgelehnt').

        `entlastet`   = der Mensch hat den Fall übernommen und sich damit
                        befasst (der eigentliche Zweck der Queue).
        `abgelehnt`   = der Mensch sagt explizit «hier läuft nichts», z. B.
                        falscher Mandant / doppelte Aktion.
        """
        if status not in _GULTIGE_ZIEL - {_STATUS_OFFEN}:
            raise ValueError(
                f"Ungültiger Zielstatus: {status!r} "
                f"(erwartet: 'entlastet' oder 'abgelehnt')"
            )
        with self._lock:
            row = self._conn.execute(
                "SELECT mandant, prototyp, status FROM ausnahmen WHERE id = ?",
                (ausnahme_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Keine Ausnahme mit id={ausnahme_id}")
            mandant, prototyp, aktueller = row
            if aktueller != _STATUS_OFFEN:
                raise RuntimeError(
                    f"Ausnahme {ausnahme_id} ist bereits '{aktueller}' — "
                    "nicht erneut entscheidbar (Append-only)."
                )
            self._conn.execute(
                "UPDATE ausnahmen SET status=?, erledigt_um=?, erledigt_von=? "
                "WHERE id=?",
                (status, _jetzt(), actor, ausnahme_id),
            )
            self._conn.commit()
        self._audit.log(
            mandant=mandant,
            prototyp=prototyp,
            actor=actor,
            action=f"ausnahme_{status}",
            details={"ausnahme_id": ausnahme_id, "begruendung": begründung},
        )
        return self.lade(ausnahme_id)

    # ------------------------------------------------------------------ #
    # Lesen                                                              #
    # ------------------------------------------------------------------ #
    def lade(self, ausnahme_id: int) -> Ausnahme:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, mandant, prototyp, titel, payload, status, "
                "grund, regel, vorgeschlagen_von, angelegt_um, "
                "erledigt_um, erledigt_von FROM ausnahmen WHERE id = ?",
                (ausnahme_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Keine Ausnahme mit id={ausnahme_id}")
        return self._zu_ausnahme(row)

    def offene(self, *, mandant: str | None = None) -> list[Ausnahme]:
        """Offene (noch nicht entschlossene) Ausnahmen, älteste zuerst."""
        with self._lock:
            if mandant is None:
                rows = self._conn.execute(
                    "SELECT * FROM ausnahmen WHERE status='offen' ORDER BY id"
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM ausnahmen WHERE status='offen' AND mandant=? "
                    "ORDER BY id",
                    (mandant,),
                ).fetchall()
        return [self._zu_ausnahme(r) for r in rows]

    @staticmethod
    def _zu_ausnahme(row) -> Ausnahme:
        (
            aid, mandant, prototyp, titel, payload_json, status,
            grund, regel, vorgeschlagen_von, angelegt_um, erledigt_um,
            erledigt_von,
        ) = row
        return Ausnahme(
            id=aid,
            mandant=mandant,
            prototyp=prototyp,
            titel=titel,
            payload=json.loads(payload_json),
            status=status,
            grund=grund,
            rule=regel,
            vorgeschlagen_von=vorgeschlagen_von,
            angelegt_um=angelegt_um,
            erledigt_um=erledigt_um,
            erledigt_von=erledigt_von,
        )

    # ------------------------------------------------------------------ #
    # KPI (was ist die Quote an menschlichen Entlastungen?)              #
    # ------------------------------------------------------------------ #
    def einseiter(self, *, mandant: str | None = None) -> dict:
        """KPI: Wie viele Aktionen entlastet der menschliche Entlaster?

        `offen` / `entlastet` / `abgelehnt` / `total`. Die Quote an
        menschlich entlasteten Fällen ist das KPI: fällt sie dauerhaft
        unter eine Schwelle, ist das kein Qualitäts-Signal mehr, sondern
        ein Politik-Signal (Schwellen zu locker, Rolle nicht besetzt).
        """
        with self._lock:
            where = []
            params: list[object] = []
            if mandant is not None:
                where.append("mandant=?")
                params.append(mandant)
            sql = "SELECT status, COUNT(*) FROM ausnahmen"
            if where:
                sql += " WHERE " + " AND ".join(where)
            sql += " GROUP BY status"
            counts = {s: int(n) for s, n in self._conn.execute(sql, params).fetchall()}
            total = sum(counts.values())
        return {
            "offen": counts.get(_STATUS_OFFEN, 0),
            "entlastet": counts.get(_STATUS_ENTLASTET, 0),
            "abgelehnt": counts.get(_STATUS_ABGELEHNT, 0),
            "total": total,
        }

    def schliesse(self) -> None:
        with self._lock:
            self._conn.close()
