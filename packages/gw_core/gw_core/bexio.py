"""Bexio-Adapter (Zielsystem, GB-09: Money-Limite IM Zielsystem).

Warum dieser Baustein die Freigabe real macht:
Heute endet "freigegeben" im Log. Wenn freigegeben = Rechnung in Bexio
angelegt ist, wird aus dem Prototyp #2 ein Produkt. (GB-09: Grad-4+-
Geld-Operationen dürfen limiten NUR im Zielsystem tragen — nicht im
Prompt. Bexio kennt den Kunden, kennt die Buchungsregeln, kennt
QR-Referenz-Gültigkeit — der LLM kennt nichts davon. Bexio ist die
Grenzstelle.)

Authentifizierung (verifiziert 2026-10-01 gemäss docs.bexio.com):
- OAuth 2.0 Autorisierungs-Code (OpenID Connect, Issuer
  https://auth.bexio.com/realms/bexio) oder
- Personal Access Token (PAT) von developer.bexio.com.
Beides wird als `Authorization: Bearer <token>` gesendet.

Scopes (benötigt für Rechnungs-Anlage): `kb_bill_show kb_bill_edit`
(bei Kaufrechnungen) — für eigene Ausstellungen: `kb_invoice_show
kb_invoice_edit`. Die Scope-Anforderung erfolgt NICHT in diesem
Adapter, sondern in der OAuth-Fluss des Hosts. Der Adapter nimmt
einen gültigen Bearer-Token und sendet ihn.

Einschränkungen, die in der Doku vermerkt sind:
- API-Sandbox für Entwicklung ist bei bexio erforderlich
  (docs.bexio.com nennt das explizit).
- Bexio gibt keine Implementierungsunterstützung — "JOSHMARTIN"
  wird als Partener genannt. Dieser Adapter ist daher bewusst klein:
  nur das, was freigegebene Buchungen benötigen.

Verbindungs-Limits: `max_buchungen_pro_tage` (GB-09: systemseitig!)
ist hier implementiert, nicht im LLM. Das ist der Punkt, an dem
"Freigabe" und "Grenze" zusammenkommen: Die Freigabe entscheidet
ÜBERHAUPT, ob das System angefragt wird; das Limit entscheidet
WIEVIEL, das System anfrägt.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from typing import Any

import httpx

log = logging.getLogger("gw.bexio")


@dataclass(frozen=True)
class BexioFehler:
    code: str
    message: str
    http_status: int | None = None


class BexioZielsystemAdapter:
    """Schlanker Adapter für freigegebene Buchungen → Bexio.

    Bewusst klein: nur das, was aus einer freigegebenen Aktion
    benötigt wird. Kein "alles-umfassendes ERP-SDK".
    """

    API_BASE = "https://api.bexio.com/2.0"

    def __init__(
        self,
        token: str,
        *,
        sandbox: bool = False,
        max_buchungen_pro_tag: int = 50,
        max_betrag_chf: float | None = 10_000.0,
        timeout_s: float = 30.0,
    ) -> None:
        """
        Parameters:
            token: Bearer-Token (OAuth Access oder PAT).
            sandbox: True → API-Sandbox-Base-URL verwenden
                     (https://sandbox.bexio.com).
            max_buchungen_pro_tag: GB-09 systemseitiges Geld-Limit.
            max_betrag_chf: Keine Buchung über diesen Brutto-Betrag.
            timeout_s: HTTP-Timeout.
        """
        self._token = token
        self._max_pro_tag = max_buchungen_pro_tag
        self._max_betrag = max_betrag_chf
        base = "https://sandbox.bexio.com/2.0" if sandbox else self.API_BASE
        self._http = httpx.Client(timeout=timeout_s, headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        })
        self._base = base
        # Tägliche Zählung (systemseitiges GB-09-Limit):
        self._tag = dt.date.today().isoformat()
        self._zehler_tag = 0

    # ------------------------------------------------------------------- #
    # GB-09: Systemlimite — prüfen VOR jeder API-Aufrufe                   #
    # ------------------------------------------------------------------- #
    def pre_ckeck(self, *, betrag_brutto: float, währung: str = "CHF") -> BexioFehler | None:
        """Systemseitige Limiten (GB-09).

        Diese Prüfung erfolgt in diesem Modul — NICHT im LLM-Prompt.
        Ein LLM hat keine Ahnung, wieviel CHF ein Kunde in dieser
        Woche bereits gebucht hat; das Ziehl-System (oder dieser
        Adapter, der es vertritt) hat es.
        """
        self._tag_rollover()
        if self._zehler_tag >= self._max_pro_tag:
            return BexioFehler(
                "limit_tagesvolumen",
                f"Tagesvolumen {self._max_pro_tag} Buchungen erreicht.")
        if self._max_betrag is not None and betrag_brutto > self._max_betrag:
            return BexioFehler(
                "limit_betrag",
                f"Betrag {betrag_brutto:.2f} {währung} über Limit {self._max_betrag:.2f} CHF.")
        return None

    def _tag_rollover(self) -> None:
        heute = dt.date.today().isoformat()
        if heute != self._tag:
            self._tag = heute
            self._zehler_tag = 0

    # ------------------------------------------------------------------- #
    # Rechnungs-Abgabe (Kauf-Rechnung von einem Lieferant)                 #
    # ------------------------------------------------------------------- #
    def lieferrechnung_buchen(
        self,
        *,
        lieferant_kontaktnr: str,
        rechnungsdatum: str,            # JJJJ-MM-TT
        faelligkeitsdatum: str,         # JJJJ-MM-TT
        positions: list[dict[str, Any]],
        betrag_netto: float,
        mwst_satz: float,
        mwst_betrag: float,
        betrag_brutto: float,
        rechnungsnummer: str | None = None,
        qr_referenz: str | None = None,
        iban: str | None = None,
        zahlungsziel: str | None = None,
        zusaatext: str = "",
    ) -> dict[str, Any]:
        """Eine freigegebene Lieferant-Rechnung in Bexio anlegen.

        `positions` ist eine Liste von Diktaten:
          {"bezeichnung": str, "menge": float, "preis_pro_stueck": float,
           "einheit": str|None, "artikel_kontaktnr": str|None}

        GB-09-Prüfung + Zähler-Aufruf passiert intern.
        """
        fehler = self.pre_ckeck(betrag_brutto=betrag_brutto)
        if fehler is not None:
            raise BexioZielFehler(fehler)

        payload: dict[str, Any] = {
            "contact": str(lieferant_kontaktnr),
            "document_date": rechnungsdatum,
            "due_date": faelligkeitsdatum,
            "currency": "CHF",
            "total_net": round(betrag_netto, 2),
            "tax": [
                {"tax_rate": mwst_satz, "tax_amount": round(mwst_betrag, 2)}
            ],
            "total_gross": round(betrag_brutto, 2),
            "positions": positions,
        }
        if rechnungsnummer:
            payload["document_number"] = rechnungsnummer
        if qr_referenz:
            payload["payment_reference"] = qr_referenz
        if iban:
            # Bexio nutzt `payee` (Empfänger-Konto) für die Auszahlung;
            # wir mappen IBAN hier als Hinweis für die manuelle
            # Zahlungserfassung — Bexio liest IBAN aus dem Kontakt.
            payload.setdefault("notes", "")
            if zusaatext:
                payload["notes"] = f"{zusaatext} | IBAN: {iban}".strip(" |")
            else:
                payload["notes"] = f"IBAN: {iban}"
        elif zusaatext:
            payload["notes"] = zusaatext

        resp = self._http.post(f"{self._base}/kb_bill", json=payload)
        if resp.status_code == 429:
            raise BexioZielFehler(BexioFehler(
                "rate_limit",
                "Bexio API Rate-Limit erreicht (HTTP 429).",
                http_status=429))
        if resp.status_code >= 400:
            # Bexio-Format: {"error": "..."} oder {"code":..., "message":...}
            try:
                body = resp.json()
                code = str(body.get("code", body.get("error", "unknown")))
                message = str(body.get("message", body.get("error", resp.text[:300])))
            except (ValueError, KeyError):
                code, message = "unknown", resp.text[:300]
            log.warning("Bexio API Fehler: %s %s", code, message)
            raise BexioZielFehler(BexioFehler(
                code, message, http_status=resp.status_code))
        self._zehler_tag += 1
        return resp.json()

    # ------------------------------------------------------------------- #
    def close(self) -> None:
        self._http.close()


class BexioZielFehler(RuntimeError):
    """Bexio-Adapter-Fehler (Limit, Rate-Limit, API-Fehler)."""

    def __init__(self, fehler: BexioFehler) -> None:
        super().__init__(f"[{fehler.code}] {fehler.message}")
        self.fehler = fehler


def _beispiel_payload(**kw) -> dict[str, Any]:
    """Nur für Doku/Tests: das JSON, das an Bexio verschickt würde."""
    base: dict[str, Any] = {
        "contact": "1001",
        "document_date": "2026-07-01",
        "due_date": "2026-07-31",
        "currency": "CHF",
        "total_net": 1000.0,
        "tax": [{"tax_rate": 8.1, "tax_amount": 81.0}],
        "total_gross": 1081.0,
        "positions": [
            {
                "description": "Dienstleistung Q3",
                "quantity": 1,
                "unit_price": 1000.0,
                "unit": "St",
            }
        ],
        "document_number": "RE-2026-0042",
        "payment_reference": "312345678901234567890123457",
    }
    base.update(kw)
    return base
