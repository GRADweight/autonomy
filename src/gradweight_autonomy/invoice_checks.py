"""Schweizer Belegprüfung: IBAN, QR-Referenz, SCOR, MWST, UID.

Deterministische Vorprüfung einer Lieferantenrechnung, bevor ein Mensch sie
freigibt und bevor sie gebucht wird. Grundlagen:

* IBAN nach ISO 13616 (Prüfziffer ISO 7064 MOD 97-10); Schweiz und
  Liechtenstein: 21 Stellen, BBAN = 5 Ziffern (IID) + 12 alphanumerische Zeichen.
* QR-Rechnung (SIX, Swiss Implementation Guidelines QR-bill): IBAN nur CH/LI;
  QR-IBAN erkennbar an der QR-IID 30000–31999 und nur mit QR-Referenz;
  QR-Referenz = 26 Ziffern + Prüfziffer «Modulo 10, rekursiv», nicht nur Nullen;
  Creditor Reference (SCOR, ISO 11649) nur mit normaler IBAN, 5–25 Zeichen,
  beginnt mit «RF» und zwei Prüfziffern.
* MWST-Sätze (ESTV): ab 1.1.2024 8.1 % / 2.6 % / 3.8 % (Beherbergung),
  2018–2023 7.7 % / 2.5 % / 3.7 %. Massgebend ist das Datum der Leistung, nicht
  das Rechnungsdatum.
* UID (CHE-123.456.789): Prüfziffer mit Gewichten 5, 4, 3, 2, 7, 6, 5, 4 und
  Modulo 11; Rest 10 ergibt keine gültige Nummer.

Annahme: Rundungstoleranz von CHF 0.05 je MWST-Betrag und für das Total
(Rappenrundung, Rundung je Position). Anpassbar über Parameter.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from gradweight_autonomy.approval import CheckOutcome

IBAN_LENGTHS = {"CH": 21, "LI": 21}
QR_IID_RANGE = (30000, 31999)
QR_BILL_CURRENCIES = ("CHF", "EUR")
QR_BILL_MAX_AMOUNT = Decimal("999999999.99")
_MOD10_TABLE = (0, 9, 4, 6, 8, 2, 7, 1, 3, 5)
_UID_WEIGHTS = (5, 4, 3, 2, 7, 6, 5, 4)
_UID_SUFFIXES = ("MWST", "TVA", "IVA", "VAT")
CENT = Decimal("0.01")


@dataclass(frozen=True)
class Issue:
    """Ein Befund der Belegprüfung."""

    code: str
    field: str
    message: str
    blocking: bool = True


# --------------------------------------------------------------------------- IBAN
def _alnum_to_digits(text: str) -> str:
    return "".join(str(int(ch, 36)) for ch in text)


def _mod97(text: str) -> int:
    return int(_alnum_to_digits(text)) % 97


def normalize(text: str) -> str:
    """Leerzeichen entfernen, Grossbuchstaben."""
    return re.sub(r"\s+", "", text).upper()


def iban_check_digits(country: str, bban: str) -> str:
    """Zwei IBAN-Prüfziffern für Land und BBAN berechnen."""
    return f"{98 - _mod97(bban + country + '00'):02d}"


@dataclass(frozen=True)
class IbanCheck:
    valid: bool
    normalized: str
    is_qr_iban: bool = False
    error: str = ""


def validate_iban(text: str) -> IbanCheck:
    """IBAN für CH/LI prüfen (Länge, Format, Prüfziffer, QR-IBAN)."""
    iban = normalize(text)
    country = iban[:2]
    if country not in IBAN_LENGTHS:
        return IbanCheck(False, iban, error="nur IBAN mit Ländercode CH oder LI zulässig")
    if len(iban) != IBAN_LENGTHS[country]:
        return IbanCheck(False, iban, error=f"IBAN muss {IBAN_LENGTHS[country]} Stellen haben")
    if not re.fullmatch(r"[A-Z]{2}[0-9]{2}[0-9]{5}[0-9A-Z]{12}", iban):
        return IbanCheck(
            False, iban, error="ungültiges Format (erwartet 2 Buchstaben, 7 Ziffern, 12 Zeichen)"
        )
    if _mod97(iban[4:] + iban[:4]) != 1:
        return IbanCheck(False, iban, error="Prüfziffer falsch")
    iid = int(iban[4:9])
    return IbanCheck(True, iban, is_qr_iban=QR_IID_RANGE[0] <= iid <= QR_IID_RANGE[1])


# ------------------------------------------------------------------ Referenzen
def qr_reference_check_digit(digits: str) -> int:
    """Prüfziffer «Modulo 10, rekursiv» für 26 Ziffern."""
    if not digits.isdigit():
        raise ValueError("nur Ziffern erlaubt")
    carry = 0
    for ch in digits:
        carry = _MOD10_TABLE[(carry + int(ch)) % 10]
    return (10 - carry) % 10


@dataclass(frozen=True)
class ReferenceCheck:
    valid: bool
    normalized: str
    kind: str  # "QRR" | "SCOR"
    error: str = ""


def validate_qr_reference(text: str) -> ReferenceCheck:
    """QR-Referenz: 27 Ziffern, nicht nur Nullen, Prüfziffer Modulo 10 rekursiv."""
    ref = normalize(text)
    if not re.fullmatch(r"[0-9]{27}", ref):
        return ReferenceCheck(False, ref, "QRR", "QR-Referenz muss aus 27 Ziffern bestehen")
    if set(ref) == {"0"}:
        return ReferenceCheck(False, ref, "QRR", "QR-Referenz darf nicht nur aus Nullen bestehen")
    if qr_reference_check_digit(ref[:26]) != int(ref[26]):
        return ReferenceCheck(False, ref, "QRR", "Prüfziffer der QR-Referenz falsch")
    return ReferenceCheck(True, ref, "QRR")


def scor_check_digits(body: str) -> str:
    """Prüfziffern einer Creditor Reference (ISO 11649) für ``body``."""
    return f"{98 - _mod97(body + 'RF00'):02d}"


def validate_scor(text: str) -> ReferenceCheck:
    """Creditor Reference (ISO 11649): RF + 2 Prüfziffern + 1–21 Zeichen."""
    ref = normalize(text)
    if not re.fullmatch(r"RF[0-9]{2}[0-9A-Z]{1,21}", ref):
        return ReferenceCheck(
            False, ref, "SCOR", "SCOR muss mit RF und 2 Ziffern beginnen, 5–25 Zeichen"
        )
    if _mod97(ref[4:] + ref[:4]) != 1:
        return ReferenceCheck(False, ref, "SCOR", "Prüfziffer der Creditor Reference falsch")
    return ReferenceCheck(True, ref, "SCOR")


def check_payment_reference(iban: IbanCheck, reference: str | None) -> list[Issue]:
    """Kombination IBAN/Referenz nach den Regeln der QR-Rechnung."""
    if not iban.valid:
        return []  # IBAN-Fehler wird separat gemeldet
    ref = normalize(reference) if reference else ""
    if iban.is_qr_iban:
        if not ref:
            return [Issue("qr_iban_without_qrr", "reference", "QR-IBAN verlangt eine QR-Referenz")]
        result = validate_qr_reference(ref)
        return [] if result.valid else [Issue("invalid_qr_reference", "reference", result.error)]
    if not ref:
        return []
    if ref.startswith("RF"):
        result = validate_scor(ref)
        return [] if result.valid else [Issue("invalid_scor", "reference", result.error)]
    if ref.isdigit():
        return [
            Issue(
                "qrr_without_qr_iban",
                "reference",
                "QR-Referenz ist nur mit einer QR-IBAN zulässig (normale IBAN: SCOR oder keine)",
            )
        ]
    return [Issue("unknown_reference", "reference", "Referenz ist weder QR-Referenz noch SCOR")]


# --------------------------------------------------------------------------- UID
def uid_check_digit(first8: str) -> int | None:
    """Prüfziffer aus den ersten 8 Ziffern; ``None``, wenn keine gültige UID möglich ist."""
    if not re.fullmatch(r"[0-9]{8}", first8):
        raise ValueError("genau 8 Ziffern erwartet")
    check = (11 - sum(w * int(d) for w, d in zip(_UID_WEIGHTS, first8, strict=True)) % 11) % 11
    return None if check == 10 else check


@dataclass(frozen=True)
class UidCheck:
    valid: bool
    normalized: str
    vat_suffix: str | None = None
    error: str = ""


def validate_uid(text: str) -> UidCheck:
    """UID im Format CHE-123.456.789 (optional mit Zusatz MWST/TVA/IVA) prüfen."""
    m = re.fullmatch(
        r"\s*CHE[-\s]?([0-9]{3})\.?([0-9]{3})\.?([0-9]{3})(?:\s+(MWST|TVA|IVA|VAT))?\s*",
        text.upper(),
    )
    if not m:
        return UidCheck(False, text.strip(), error="Format CHE-123.456.789 erwartet")
    digits = "".join(m.group(i) for i in (1, 2, 3))
    formatted = f"CHE-{digits[:3]}.{digits[3:6]}.{digits[6:]}"
    expected = uid_check_digit(digits[:8])
    if expected is None or expected != int(digits[8]):
        return UidCheck(False, formatted, m.group(4), "Prüfziffer der UID falsch")
    return UidCheck(True, formatted, m.group(4))


# --------------------------------------------------------------------------- MWST
@dataclass(frozen=True)
class VatRates:
    normal: Decimal
    reduced: Decimal
    accommodation: Decimal

    def all(self) -> tuple[Decimal, ...]:
        return (self.normal, self.reduced, self.accommodation)


_VAT_PERIODS: tuple[tuple[date, VatRates], ...] = (
    (date(2024, 1, 1), VatRates(Decimal("8.1"), Decimal("2.6"), Decimal("3.8"))),
    (date(2018, 1, 1), VatRates(Decimal("7.7"), Decimal("2.5"), Decimal("3.7"))),
)


def vat_rates(supply_date: date) -> VatRates:
    """Gültige MWST-Sätze für das Datum der Leistung (ab 2018)."""
    for start, rates in _VAT_PERIODS:
        if supply_date >= start:
            return rates
    raise ValueError("MWST-Sätze vor 2018 werden nicht unterstützt")


@dataclass(frozen=True)
class VatLine:
    """Eine MWST-Zeile: Satz in Prozent, Nettobetrag, Steuerbetrag."""

    rate: Decimal
    net: Decimal
    vat: Decimal


def check_vat(
    lines: Sequence[VatLine],
    *,
    gross: Decimal,
    supply_date: date,
    vat_tolerance: Decimal = Decimal("0.05"),
    total_tolerance: Decimal = Decimal("0.05"),
) -> list[Issue]:
    """Sätze, Steuerbeträge und Total auf Plausibilität prüfen."""
    issues: list[Issue] = []
    try:
        rates = vat_rates(supply_date)
    except ValueError as exc:
        return [Issue("vat_period_unsupported", "supply_date", str(exc))]
    previous = {r for _, p in _VAT_PERIODS for r in p.all()} - set(rates.all())
    if not lines:
        issues.append(Issue("vat_lines_missing", "vat_lines", "keine MWST-Zeile angegeben"))
    for i, line in enumerate(lines):
        where = f"vat_lines[{i}]"
        if line.net < 0 or line.vat < 0:
            issues.append(
                Issue("negative_amount", where, "negative Beträge sind hier nicht vorgesehen")
            )
            continue
        if line.rate == 0:
            if line.vat != 0:
                issues.append(Issue("vat_on_exempt", where, "Satz 0 %, aber Steuerbetrag > 0"))
            continue
        if line.rate not in rates.all():
            hint = (
                " (Satz aus einer früheren Periode; massgebend ist das Leistungsdatum)"
                if line.rate in previous
                else ""
            )
            issues.append(
                Issue(
                    "vat_rate_invalid",
                    where,
                    f"MWST-Satz {line.rate} % gilt am {supply_date.isoformat()} nicht; gültig: "
                    f"{', '.join(str(r) for r in rates.all())} %{hint}",
                )
            )
            continue
        expected = (line.net * line.rate / 100).quantize(CENT, rounding=ROUND_HALF_UP)
        if abs(expected - line.vat) > vat_tolerance:
            issues.append(
                Issue(
                    "vat_amount_mismatch",
                    where,
                    f"MWST {line.vat} passt nicht zu {line.rate} % von {line.net} "
                    f"(erwartet {expected})",
                )
            )
    total = sum((line.net + line.vat for line in lines), Decimal(0))
    if lines and abs(total - gross) > total_tolerance:
        issues.append(
            Issue(
                "total_mismatch",
                "gross",
                f"Total {gross} stimmt nicht mit Netto + MWST {total.quantize(CENT)} überein",
            )
        )
    return issues


# ---------------------------------------------------------------------- Rechnung
@dataclass(frozen=True)
class InvoiceFacts:
    """Die für die Prüfung nötigen Angaben einer Lieferantenrechnung."""

    iban: str
    supply_date: date
    currency: str
    gross: Decimal
    vat_lines: tuple[VatLine, ...]
    reference: str | None = None
    supplier_uid: str | None = None


@dataclass(frozen=True)
class InvoiceCheckResult:
    """Ergebnis der Belegprüfung."""

    passed: bool
    facts: InvoiceFacts
    issues: tuple[Issue, ...] = field(default_factory=tuple)

    def summary(self) -> str:
        if not self.issues:
            return "Belegprüfung bestanden."
        parts = "; ".join(f"{i.field}: {i.message}" for i in self.issues)
        verdict = "bestanden mit Hinweisen" if self.passed else "nicht bestanden"
        return f"Belegprüfung {verdict}: {parts}"

    def to_check_outcome(self) -> CheckOutcome:
        """Als blockierende Vorprüfung für die Freigabe-Queue."""
        return CheckOutcome("belegpruefung", self.passed, blocking=True, detail=self.summary())


def check_invoice(
    facts: InvoiceFacts,
    *,
    vat_tolerance: Decimal = Decimal("0.05"),
    total_tolerance: Decimal = Decimal("0.05"),
) -> InvoiceCheckResult:
    """Alle Prüfungen ausführen; nur nicht-blockierende Hinweise lassen ``passed`` zu."""
    issues: list[Issue] = []
    if facts.currency not in QR_BILL_CURRENCIES:
        issues.append(Issue("currency", "currency", "Währung muss CHF oder EUR sein (QR-Rechnung)"))
    if not Decimal(0) < facts.gross <= QR_BILL_MAX_AMOUNT:
        issues.append(
            Issue("amount_range", "gross", "Betrag muss zwischen 0.01 und 999'999'999.99 liegen")
        )
    if facts.gross.quantize(CENT) != facts.gross:
        issues.append(
            Issue("amount_precision", "gross", "Betrag hat mehr als zwei Nachkommastellen")
        )
    iban = validate_iban(facts.iban)
    if not iban.valid:
        issues.append(Issue("invalid_iban", "iban", iban.error))
    issues += check_payment_reference(iban, facts.reference)
    issues += check_vat(
        facts.vat_lines,
        gross=facts.gross,
        supply_date=facts.supply_date,
        vat_tolerance=vat_tolerance,
        total_tolerance=total_tolerance,
    )
    charges_vat = any(line.vat > 0 for line in facts.vat_lines)
    if facts.supplier_uid:
        uid = validate_uid(facts.supplier_uid)
        if not uid.valid:
            issues.append(Issue("invalid_uid", "supplier_uid", uid.error))
        elif charges_vat and uid.vat_suffix is None:
            issues.append(
                Issue(
                    "uid_without_vat_suffix",
                    "supplier_uid",
                    "MWST ausgewiesen, aber UID ohne Zusatz MWST/TVA/IVA",
                    blocking=False,
                )
            )
    elif charges_vat:
        issues.append(
            Issue(
                "vat_without_registration",
                "supplier_uid",
                "MWST ausgewiesen, aber keine MWST-Nummer des Lieferanten erfasst "
                "(Vorsteuerabzug prüfen)",
                blocking=False,
            )
        )
    return InvoiceCheckResult(
        passed=not any(i.blocking for i in issues), facts=facts, issues=tuple(issues)
    )
