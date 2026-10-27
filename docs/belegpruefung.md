# Schweizer Belegprüfung

`gradweight_autonomy.invoice_checks` prüft eine Lieferantenrechnung, bevor sie
zur Freigabe vorgelegt und gebucht wird. Die Prüfung ist deterministisch und
läuft ohne Netzwerk.

## Prüfungen und Grundlagen

| Prüfung | Regel | Grundlage |
|---|---|---|
| IBAN | Länder CH und LI, 21 Stellen, BBAN = 5 Ziffern + 12 Zeichen, Prüfziffer MOD 97-10 | ISO 13616, ISO 7064; SIX Swiss Implementation Guidelines QR-bill (Version 2.3) |
| QR-IBAN | Institut-Identifikation (QR-IID) 30000–31999 | SIX IG QR-bill |
| QR-Referenz | 26 Ziffern + Prüfziffer «Modulo 10, rekursiv», nicht nur Nullen, nur mit QR-IBAN | SIX IG QR-bill |
| Creditor Reference (SCOR) | `RF` + 2 Prüfziffern + 1–21 Zeichen (5–25 total), MOD 97-10, nur mit normaler IBAN | ISO 11649; SIX IG QR-bill |
| Währung und Betrag | CHF oder EUR, 0.01 bis 999'999'999.99, höchstens zwei Nachkommastellen | SIX IG QR-bill |
| MWST-Satz | gültig am **Leistungsdatum**: ab 1.1.2024 8.1 %, 2.6 %, 3.8 %; 2018–2023 7.7 %, 2.5 %, 3.7 % | ESTV (Mehrwertsteuererhöhung per 1.1.2024) |
| MWST-Betrag und Total | MWST = Netto x Satz (kaufmännisch gerundet) innerhalb Toleranz; Netto + MWST = Total innerhalb Toleranz | – |
| UID | `CHE-123.456.789`, Prüfziffer mit Gewichten 5, 4, 3, 2, 7, 6, 5, 4 und Modulo 11; Zusatz `MWST`/`TVA`/`IVA` | Bundesamt für Statistik (UID-Register) |

Blockierend sind alle Befunde ausser zwei Hinweisen: ausgewiesene MWST ohne
erfasste MWST-Nummer des Lieferanten bzw. UID ohne MWST-Zusatz. Ob der
Vorsteuerabzug möglich ist, bleibt eine Prüfung der Buchhaltung.

**Annahme:** Toleranz von CHF 0.05 je MWST-Betrag und für das Total
(Rappenrundung, Rundung je Position). Anpassbar über `vat_tolerance` und
`total_tolerance`.

## Einsatz im Freigabe-Ablauf

```python
from gradweight_autonomy.invoice_checks import InvoiceFacts, VatLine, check_invoice

beleg = check_invoice(
    InvoiceFacts(
        iban="CH44 3199 9123 0008 8901 2",
        reference="21 00000 00003 13947 14300 09017",
        supplier_uid="CHE-100.155.212 MWST",
        supply_date=date(2026, 9, 30),
        currency="CHF",
        gross=Decimal("1081.00"),
        vat_lines=(VatLine(Decimal("8.1"), Decimal("1000.00"), Decimal("81.00")),),
    )
)
# Blockierende Vorprüfung an die Aktion hängen:
aktion = queue.propose(..., checks=[beleg.to_check_outcome()])
# Scheitert mit ApprovalDeniedError, wenn beleg.passed False ist:
queue.approve(aktion, actor="a.beispiel", role="buchhaltung")
# Der Adapter verlangt dieselbe, bestandene Prüfung:
bexio.create_supplier_bill(rechnung, check=beleg)
```

Der bexio-Adapter bucht nur, wenn eine bestandene Belegprüfung mit gleichem
Betrag und gleicher Währung übergeben wird. Den ganzen Ablauf zeigt
`gw-autonomy demo`.

## Prüfung der Algorithmen

Die Tests (`tests/test_invoice_checks.py`) erzeugen mit Hypothesis zufällige
gültige IBAN, QR-Referenzen, SCOR und UID und vergleichen das Ergebnis mit
der unabhängigen Bibliothek python-stdnum (nur Testabhängigkeit). Belegt ist
dabei auch eine Eigenschaft des Verfahrens: MOD 97-10 erkennt jede Ersetzung
einer Ziffer durch eine andere Ziffer und jede Vertauschung benachbarter
Ziffern, aber **nicht jede** Ersetzung durch einen Buchstaben.

## Grenzen

- Plausibilität, nicht Echtheit: Eine betrügerische Rechnung mit gültiger
  IBAN des Betrügers besteht die Prüfung. Abgleich mit Lieferantenstamm und
  bekannter IBAN bleibt nötig.
- Nur IBAN aus der Schweiz und Liechtenstein; MWST-Sätze ab 2018; keine
  Sonderfälle wie Bezugsteuer, Margenbesteuerung oder Saldosteuersätze.
- Die Angaben müssen aus dem Beleg extrahiert sein; ob die Extraktion stimmt,
  prüft der [Zahlen- und Quellenabgleich](zahlenabgleich.md).
