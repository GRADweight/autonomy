"""SamplingAudit — reproduzierbare Stichproben über den Audit-Trail (GB-11, Grad >= 4).

Laut Roadmap (docs/roadmap-grad-03-05.md) fehlt für Grad >= 4 «Stichproben-
Selektoren + Audit-Read-out über den AuditTrail». Das fehlt nicht, weil die
Idee schwer wäre, sondern weil niemand die Selektion **deterministisch**
gemacht hat: eine Stichprobe, die bei zwei Läufen zwei andere Sätze liefert,
ist keine Prüfung, sondern ein Zufall. Das löst diese Datei.

Was «Stichprobenaudit» hier konkret heisst
-------------------------------------------
1. **Beobachten**: jede relevante Aktion landet im Audit-Trail
   (gleicher `AuditTrail`-Baustein wie im Rest des Systems — GB-11).
2. **Stichprobe**: ein fester, reproduzierbarer Teil des Trails wird
   selektiert. Deterministisch durch systematisches Sampling
   (fester Schritt über der id-sorted Liste) — kein Zufallsgenerator,
   deshalb liefert jeder Lauf mit denselben Parametern dieselbe Stichprobe.
3. **Beurteilen**: jede Stichprobe gegen eine oder mehrere Kriterien
   (z. B. «menschlicher Entscheider in der Kette», «Begründung vorhanden»).
4. **Bericht**: Pass-Quote + pro Kriterium die Versager, plus die
   Evidenz (welche Einträge, welche Kriterien) — und der Audit-Akt
   selbst wird wieder in den Trail geschrieben (Audit von Audit).

Design
------
- Null Dependencies (stdlib + gw_core.audit) — offline, thread-sicher.
- Deterministisch: gleiche Eingabe + gleiche Parameter -> gleiche
  Stichprobe. Keine `random`-Abhängigkeit im Selektionspfad.
- Kriterium = `Callable[[dict], tuple[bool, str]]` (bestanden, Befund).
  Das macht Regeln testbar und austauschbar, ohne den Baustein zu ändern.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from gw_core.audit import AuditTrail

# Ein Kriterium: Eintrag -> (bestanden, Befund-Text).
Kriterium = Callable[[dict], tuple[bool, str]]


def _mensch_ist_entscheider(eintrag: dict) -> tuple[bool, str]:
    """GB-11: jede wirkungsvolle Entlastung braucht in der Kette einen Menschen.

    'llm' / 'system' / 'model' sind System-Akteure — einer von ihnen als
    `actor` des letzten Schritts heisst: der Mensch fehlt in der Kette.
    """
    system_aktoren = {"llm", "system", "model", "ki"}
    actor = eintrag.get("actor", "")
    return (
        actor not in system_aktoren,
        f"actor={actor!r}" + ("" if actor not in system_aktoren else " (System, kein Mensch)"),
    )


def _begrundung_vorhanden(eintrag: dict) -> tuple[bool, str]:
    """Eine entscheidbare Entlastung braucht eine Begründung im Trail."""
    details = eintrag.get("details") or {}
    begruendung = str(
        details.get("begruendung") or details.get("annotation") or ""
    ).strip()
    return (
        bool(begruendung),
        f"begruendung={'vorhanden' if begruendung else 'fehlend'}",
    )


#: Standard-Kriterien (Name, Funktion). Kunden können eigene ergänzen.
STANDARD_KRITERIEN: list[tuple[str, Kriterium]] = [
    ("mensch_in_kette", _mensch_ist_entscheider),
    ("begrundung_vorhanden", _begrundung_vorhanden),
]


@dataclass(frozen=True)
class EintragBeurteilung:
    """Ergebnis der Beurteilung eines einzelnen Trails-Eintrags."""

    eintrag_id: int
    ts: str
    actor: str
    action: str
    bestanden: bool
    befunde: tuple[tuple[str, bool, str], ...]  # (kriterium, bestanden, text)


@dataclass(frozen=True)
class AuditBericht:
    """Zusammenfassung einer Stichproben-Audit-Lauf (Evidenz + Quote)."""

    stichprobe_groesse: int
    bestanden: int
    gescheitert: int
    passquote: float  # 0.0–1.0
    eintraege: tuple[EintragBeurteilung, ...]
    pro_kriterium_gescheitert: dict  # kriterium -> Anzahl Versager

    def als_dict(self) -> dict:
        """Maschinenlesbar (Export, KPI-Dashboard, Revision)."""
        return {
            "stichprobe_groesse": self.stichprobe_groesse,
            "bestanden": self.bestanden,
            "gescheitert": self.gescheitert,
            "passquote": round(self.passquote, 4),
            "pro_kriterium_gescheitert": dict(self.pro_kriterium_gescheitert),
            "eintraege": [
                {
                    "id": e.eintrag_id,
                    "ts": e.ts,
                    "actor": e.actor,
                    "action": e.action,
                    "bestanden": e.bestanden,
                    "befunde": [
                        {"kriterium": k, "bestanden": b, "text": t}
                        for k, b, t in e.befunde
                    ],
                }
                for e in self.eintraege
            ],
        }


class SamplingAudit:
    """Stichproben-Audit über einen Audit-Trail (Grad >= 4, GB-11).

    Typischer Lauf:
      audit = AuditTrail()
      ... Aktionen werden in `audit` geloggt (Bestand: `log()` ... ) ...
      sampler = SamplingAudit(audit=audit)
      bericht = sampler.durchfuehre(mandant="K1", n=20,
                                    kriterien=STANDARD_KRITERIEN)
      print(bericht.passquote)                      # 0.95 ...
      print(json.dumps(bericht.als_dict(), indent=2))  # Evidenz
    """

    def __init__(self, audit: AuditTrail | None = None):
        self._audit = audit or AuditTrail()

    # ------------------------------------------------------------------ #
    # 1 · Beobachten (dünner Delegation an den Audit-Trail)              #
    # ------------------------------------------------------------------ #
    def beobachte(
        self,
        *,
        mandant: str,
        prototyp: str,
        actor: str,
        action: str,
        details: dict | None = None,
    ) -> int:
        """Aktion in den Trail schreiben — dieselbe Semantik wie `AuditTrail.log`."""
        return self._audit.log(
            mandant=mandant,
            prototyp=prototyp,
            actor=actor,
            action=action,
            details=details,
        )

    # ------------------------------------------------------------------ #
    # 2 · Stichprobe (deterministisch)                                   #
    # ------------------------------------------------------------------ #
    def stichprobe(
        self,
        *,
        mandant: str | None = None,
        prototyp: str | None = None,
        n: int = 20,
    ) -> list[dict]:
        """Reproduzierbare systematische Stichprobe über dem Trail.

        Selektion = fester Schritt über der id-sorted Liste (alt->neu).
        Keine Zufallszahl, kein Seed — dieselbe Datenmenge + dasselbe `n`
        liefert immer dieselben Einträge. Das ist die Eigenschaft, die
        aus einer «Stichprobe» eine **wiederholbare Prüfung** macht.

        `n < 1` wirft ValueError. `n` >= Gesamtzahl liefert den ganzen
        Trail (deterministisch und vollständig — keine «fast ganz»).
        """
        if n < 1:
            raise ValueError("n muss >= 1 sein")
        # Vollmenge, alt->neu (query liefert newest first).
        traetig = self._audit.query(mandant=mandant, prototyp=prototyp, limit=10**9)
        traetig.reverse()
        total = len(traetig)
        if total == 0:
            return []
        if n >= total:
            return traetig
        step = total / n
        return [traetig[min(i, total - 1)] for i in (int(i * step) for i in range(n))]

    # ------------------------------------------------------------------ #
    # 3 · Beurteilen                                                     #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _beurteile_eintrag(
        eintrag: dict, kriterien: list[tuple[str, Kriterium]]
    ) -> EintragBeurteilung:
        befunde = []
        bestanden = True
        for name, fkt in kriterien:
            try:
                ok, text = fkt(eintrag)
            except Exception as e:  # Criterion-Fehler -> Eintrag scheitert, Lauf läuft weiter
                ok, text = False, f"Kriterium {name} warf: {e}"
            befunde.append((name, bool(ok), str(text)))
            bestanden = bestanden and bool(ok)
        return EintragBeurteilung(
            eintrag_id=int(eintrag["id"]),
            ts=eintrag["ts"],
            actor=eintrag["actor"],
            action=eintrag["action"],
            bestanden=bestanden,
            befunde=tuple(befunde),
        )

    # ------------------------------------------------------------------ #
    # 4 · Durchführen (2+3+5: Sampling, Prüfung, Bericht, Log-Zeile)     #
    # ------------------------------------------------------------------ #
    def durchfuehre(
        self,
        *,
        mandant: str | None = None,
        prototyp: str | None = None,
        n: int = 20,
        kriterien: list[tuple[str, Kriterium]] | None = None,
        actor: str = "system",
    ) -> AuditBericht:
        """Stichproben-Audit laufen lassen und als Evidenz in den Trail legen.

        Der Bericht selbst wird als `details` in der Log-Zeile
        `stichproben_audit` gespeichert (GB-11: Beobachtbarkeit der
        Beobachtung). Die Log-Zeile enthält `quote`, `bestanden`,
        `gescheitert` und die Stichprobe-Größe — das volle Evidenz-JSON
        (`als_dict()`-Struktur) bleibt in der Detail-Beilage.
        """
        kriterien = kriterien or STANDARD_KRITERIEN
        stichprobe = self.stichprobe(mandant=mandant, prototyp=prototyp, n=n)
        beurteilungen = [self._beurteile_eintrag(e, kriterien) for e in stichprobe]
        bestanden = sum(1 for b in beurteilungen if b.bestanden)
        gescheitert = len(beurteilungen) - bestanden
        quote = (bestanden / len(beurteilungen)) if beurteilungen else 0.0
        pro_krit = {
            name: sum(1 for b in beurteilungen for k, ok, _t in b.befunde if k == name and not ok)
            for name, _ in kriterien
        }
        bericht = AuditBericht(
            stichprobe_groesse=len(stichprobe),
            bestanden=bestanden,
            gescheitert=gescheitert,
            passquote=quote,
            eintraege=tuple(beurteilungen),
            pro_kriterium_gescheitert=pro_krit,
        )
        # Beobachtbarkeit der Beobachtung (GB-11) — in dieselbe Trail-Instanz.
        self._audit.log(
            mandant=mandant or "*",
            prototyp=prototyp or "*",
            actor=actor,
            action="stichproben_audit",
            details={
                "n": len(stichprobe),
                "bestanden": bestanden,
                "gescheitert": gescheitert,
                "passquote": round(quote, 4),
                "kriterien": [name for name, _ in kriterien],
                "evidenz": bericht.als_dict(),
            },
        )
        return bericht

    # ------------------------------------------------------------------ #
    # 5 · Lesen                                                          #
    # ------------------------------------------------------------------ #
    def letzte_berichte(self, *, mandant: str | None = None) -> AuditBericht | None:
        """Letzten Audit-Bericht aus dem Trail als `AuditBericht` zurückbauen.

        Nutzt die `details.evidenz`-Beilage der letzten
        `stichproben_audit`-Zeile. Gilt «keine vorhanden» -> None.
        """
        zeilen = self._audit.query(
            mandant=mandant, limit=10**9
        )
        for z in zeilen:  # neueste zuerst
            if z["action"] != "stichproben_audit":
                continue
            ev = (z["details"] or {}).get("evidenz") or {}
            return AuditBericht(
                stichprobe_groesse=ev.get("stichprobe_groesse", 0),
                bestanden=ev.get("bestanden", 0),
                gescheitert=ev.get("gescheitert", 0),
                passquote=ev.get("passquote", 0.0),
                eintraege=tuple(
                    EintragBeurteilung(
                        eintrag_id=int(e["id"]),
                        ts=e["ts"],
                        actor=e["actor"],
                        action=e["action"],
                        bestanden=bool(e["bestanden"]),
                        befunde=tuple(
                            (b["kriterium"], bool(b["bestanden"]), b["text"])
                            for b in e.get("befunde") or []
                        ),
                    )
                    for e in ev.get("eintraege") or []
                ),
                pro_kriterium_gescheitert=dict(ev.get("pro_kriterium_gescheitert") or {}),
            )
        return None
