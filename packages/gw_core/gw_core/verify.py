"""Zahlen- und Quellenabgleich — Zahlen einer Antwort gegen Fundstellen prüfen.

Kein Modell: deterministischer Abgleich von Zahlen-Entitäten.

Mechanik (deterministisch, LLM-frei):
  1) Zahlen-Entitäten in der Antwort extrahieren (Betrag, Prozentsatz,
     Datum, Zählung) — die dominanten Fehlerklassen bei Halluzinationen.
  2) Dieselbe Extraktion auf den zitierten Fundstellen.
  3) Zahlen in der Antwort, die in KEINER Fundstelle stehen, werden als
     fehlend markiert -> Befund.ok=False (VETO: Antwort nicht belegbar).

Das Modul ist bewusst die *billige Kernversion*: es deckt Zahlen und
Zahl-tokens. Qualitative Umformulierungen prüft ein Zweitmodell in der
vollen Version; diese Kernversion ist deterministisch und damit testbar.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Zahlenformen (CH/EU), längste zuerst:
#   CH-Datum 31.07.2026 · ISO-Datum 2026-07-01 ·
#   gruppiert 1'234'567(.89) / 1'234,56 · dekadisch 1234.56 / 1234,56 ·
#   einfache 1234
_NUM = re.compile(
    r"""
    (?<![\w])                                   # kein Wort-Kern davor
    (
        \d{1,2}\.\d{1,2}\.\d{2,4}                # 31.07.2026
      | \d{4}-\d{2}-\d{2}                        # 2026-07-01
      | \d{1,3}(?:'\d{3})+(?:[.,]\d+)?           # 1'234'567 / 1'234.56
      | \d+(?:[.,]\d+)+                          # 1234.56 / 1234,56
      | \d+                                      # 1234
    )
    (?![\w])                                     # kein Wort-Kern dahinter
    """,
    re.VERBOSE,
)

_PROZENT_FOLGT = re.compile(r"^\s*(?:%|％)")

ISO_DATUM = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CH_DATUM = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$")


def _kanonischer_schluessel(token: str) -> tuple[str, bool]:
    """Einen Token in seinen Vergleichsschlüssel übersetzen.

    Returns (schluessel, ist_datum). Daten werden kanonisch in ISO
    (JJJJ-MM-TT) gebracht, damit `31.07.2026` und `2026-07-31` dieselbe
    Entität sind. Andere Zahlen: `'`-Tausender + Dezimal-Komma normalisiert.
    """
    t = token.replace(" ", "")
    m_iso = ISO_DATUM.match(t)
    if m_iso:
        return t, True
    m_ch = CH_DATUM.match(t)
    if m_ch:
        tt, mm, jjjj = m_ch.groups()
        return f"{jjjj}-{int(mm):02d}-{int(tt):02d}", True
    norm = t.replace("'", "")
    if "," in norm and "." not in norm:
        norm = norm.replace(",", ".")
    return norm, False


@dataclass(frozen=True)
class Zitat:
    """Eine Fundstelle: der Text, den der RAG-Retrieval geholt hat."""

    text: str
    quelle: str = ""


@dataclass(frozen=True)
class Befund:
    """Ergebnis der Zweitmodell-Prüfung — maschinenlesbar, belegsicher."""

    ok: bool
    gepueft: int
    gedeckt: int
    fehlende: tuple[str, ...] = field(default_factory=tuple)
    veto_grund: str = ""

    def zusammenfassung(self) -> str:
        if self.ok:
            return (
                f"Prüfung OK: {self.gepueft}/{self.gepueft} "
                f"Zahlen-Entitäten in Fundstellen belegt."
            )
        return (
            f"Prüfung VETO: {len(self.fehlende)} von {self.gepueft} "
            f"Zahlen-Entitäten in den Fundstellen nicht belegt. "
            f"Fehlend: {', '.join(self.fehlende[:5])}"
        )


def _normalisiere(token: str) -> str:
    """Zahl in vergleichbare Normalform: 1'234.56 / 1'234,56 -> 1234.56."""
    t = token.replace("'", "").replace(" ", "")
    # Dezimal-Komma -> Punkt (nur wenn kein Gruppen-Punkt schon da ist)
    if "," in t and "." not in t:
        t = t.replace(",", ".")
    return t


def _zifferntokens(text: str) -> list[tuple[str, str]]:
    """Liste von (Anzeige, Vergleichsschlüssel) für jede Zahlen-Entität."""
    out: list[tuple[str, str]] = []
    for m in _NUM.finditer(text):
        roh = m.group(1)
        # Prozent-Marke anhängen, falls der Token einen % begleitet
        rest = text[m.end():]
        anzeige = roh + " %" if _PROZENT_FOLGT.match(rest) else roh
        schlüssel, _ist_datum = _kanonischer_schluessel(roh)
        out.append((anzeige, schlüssel))
    return out


def _vokabular(quellen_texte: list[str]) -> set[str]:
    vok: set[str] = set()
    for t in quellen_texte:
        for _anzeige, schlüssel in _zifferntokens(t):
            vok.add(schlüssel)
    return vok


def pruefe_antwort(antwort: str, fundstellen: list[Zitat]) -> Befund:
    """Antwort-Text gegen die Fundstellen prüfen.

    `fundstellen` sind die RAG-Chunks, aus denen die Antwort stammen SOLL.
    Jede Zahlen-Entität in der Antwort muss in mind. einer Fundstelle
    belegt sein, sonst VETO.
    """
    quellen = [f.text for f in fundstellen]
    quellen_vok = _vokabular(quellen)

    seen: set[str] = set()
    fehlend: list[str] = []
    for anzeige, schlüssel in _zifferntokens(antwort):
        if schlüssel in seen:
            continue
        seen.add(schlüssel)
        if schlüssel not in quellen_vok:
            fehlend.append(anzeige)

    return Befund(
        ok=not fehlend,
        gepueft=len(seen),
        gedeckt=len(seen) - len(fehlend),
        fehlende=tuple(fehlend),
        veto_grund=(
            "" if not fehlend
            else "Diese Zahlen/Zitate stehen in keiner der Fundstellen."
        ),
    )
