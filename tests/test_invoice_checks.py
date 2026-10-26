"""Schweizer Belegprüfung: Algorithmen, Eigenschaften, Differenztest gegen python-stdnum."""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from stdnum import iban as stdnum_iban
from stdnum import iso11649
from stdnum.ch import esr, uid

from gradweight_autonomy.invoice_checks import (
    InvoiceFacts,
    VatLine,
    check_invoice,
    check_payment_reference,
    check_vat,
    iban_check_digits,
    qr_reference_check_digit,
    scor_check_digits,
    uid_check_digit,
    validate_iban,
    validate_qr_reference,
    validate_scor,
    validate_uid,
    vat_rates,
)

IBAN = "CH93 0076 2011 6238 5295 7"
QR_IBAN = "CH44 3199 9123 0008 8901 2"
QRR = "21 00000 00003 13947 14300 09017"
SCOR = "RF18 5390 0754 7034"
UID = "CHE-100.155.212 MWST"
D2026 = date(2026, 10, 1)

DIGITS = st.text(alphabet="0123456789", min_size=1, max_size=1)
ALNUM = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


# --------------------------------------------------------------------- IBAN
def test_known_ibans() -> None:
    assert validate_iban(IBAN).valid
    assert not validate_iban(IBAN).is_qr_iban
    qr = validate_iban(QR_IBAN)
    assert qr.valid
    assert qr.is_qr_iban
    assert validate_iban("li21 0881 0000 2324 013a a").valid


@pytest.mark.parametrize(
    ("value", "error"),
    [
        ("DE89370400440532013000", "CH oder LI"),
        ("CH930076201162385295", "21 Stellen"),
        ("CH93007620116238529570", "21 Stellen"),
        ("CH93A0762011623852957", "Format"),
        ("CH9400762011623852957", "Prüfziffer"),
    ],
)
def test_invalid_ibans(value: str, error: str) -> None:
    result = validate_iban(value)
    assert not result.valid
    assert error in result.error


@st.composite
def ch_ibans(draw: st.DrawFn) -> str:
    country = draw(st.sampled_from(["CH", "LI"]))
    iid = draw(st.text(alphabet="0123456789", min_size=5, max_size=5))
    account = draw(st.text(alphabet=ALNUM, min_size=12, max_size=12))
    bban = iid + account
    return country + iban_check_digits(country, bban) + bban


@settings(max_examples=300)
@given(value=ch_ibans())
def test_generated_ibans_are_valid_and_agree_with_stdnum(value: str) -> None:
    result = validate_iban(value)
    assert result.valid
    assert stdnum_iban.is_valid(value)
    assert result.is_qr_iban == (30000 <= int(value[4:9]) <= 31999)


@settings(max_examples=300)
@given(value=ch_ibans(), pos=st.integers(min_value=2, max_value=20), digit=DIGITS)
def test_single_digit_substitution_is_detected(value: str, pos: int, digit: str) -> None:
    """ISO 7064 MOD 97-10 erkennt jede Ziffer-zu-Ziffer-Ersetzung."""
    assume(value[pos].isdigit() and digit != value[pos])
    mutated = value[:pos] + digit + value[pos + 1 :]
    assert not validate_iban(mutated).valid


def test_letter_substitution_is_not_always_detected() -> None:
    """Grenze des Verfahrens: Buchstaben werden zu zwei Ziffern, das ist nicht lückenlos."""
    assert validate_iban("CH2363788000000000000").valid
    assert validate_iban("CH236378800000J000000").valid


@settings(max_examples=300)
@given(value=ch_ibans(), pos=st.integers(min_value=4, max_value=19))
def test_adjacent_digit_transposition_is_detected(value: str, pos: int) -> None:
    assume(value[pos].isdigit() and value[pos + 1].isdigit() and value[pos] != value[pos + 1])
    mutated = value[:pos] + value[pos + 1] + value[pos] + value[pos + 2 :]
    assert not validate_iban(mutated).valid


@settings(max_examples=400)
@given(value=st.text(alphabet="CHLI0123456789AB ", min_size=15, max_size=26))
def test_iban_differential_against_stdnum(value: str) -> None:
    compact = value.replace(" ", "").upper()
    if compact[:2] in ("CH", "LI"):
        assert validate_iban(value).valid == stdnum_iban.is_valid(compact)


# --------------------------------------------------------------- QR-Referenz
def test_known_qr_reference() -> None:
    assert validate_qr_reference(QRR).valid
    assert qr_reference_check_digit("21000000000313947143000901") == 7


@pytest.mark.parametrize(
    ("value", "error"),
    [
        ("21000000000313947143000901", "27 Ziffern"),
        ("2100000000031394714300090A7", "27 Ziffern"),
        ("0" * 27, "Nullen"),
        ("210000000003139471430009016", "Prüfziffer"),
    ],
)
def test_invalid_qr_references(value: str, error: str) -> None:
    result = validate_qr_reference(value)
    assert not result.valid
    assert error in result.error


def test_check_digit_requires_digits() -> None:
    with pytest.raises(ValueError, match="Ziffern"):
        qr_reference_check_digit("12a")


@settings(max_examples=300)
@given(body=st.text(alphabet="0123456789", min_size=26, max_size=26))
def test_qr_reference_roundtrip_and_stdnum(body: str) -> None:
    assume(set(body) != {"0"})
    ref = body + str(qr_reference_check_digit(body))
    assert validate_qr_reference(ref).valid
    assert esr.is_valid(ref)


@settings(max_examples=300)
@given(
    body=st.text(alphabet="0123456789", min_size=26, max_size=26),
    pos=st.integers(min_value=0, max_value=26),
    digit=DIGITS,
)
def test_qr_reference_detects_single_digit_errors(body: str, pos: int, digit: str) -> None:
    ref = body + str(qr_reference_check_digit(body))
    assume(ref[pos] != digit)
    mutated = ref[:pos] + digit + ref[pos + 1 :]
    assume(set(mutated) != {"0"})
    assert not validate_qr_reference(mutated).valid


# --------------------------------------------------------------------- SCOR
def test_known_scor() -> None:
    assert validate_scor(SCOR).valid
    assert scor_check_digits("539007547034") == "18"


@pytest.mark.parametrize(
    ("value", "error"),
    [("RF17 5390 0754 7034", "Prüfziffer"), ("RX18 5390", "beginnen"), ("RF18", "beginnen")],
)
def test_invalid_scor(value: str, error: str) -> None:
    result = validate_scor(value)
    assert not result.valid
    assert error in result.error


@settings(max_examples=300)
@given(body=st.text(alphabet=ALNUM, min_size=1, max_size=21))
def test_scor_roundtrip_and_stdnum(body: str) -> None:
    ref = "RF" + scor_check_digits(body) + body
    assert validate_scor(ref).valid
    assert iso11649.is_valid(ref)


# --------------------------------------------------------- IBAN x Referenz
def test_payment_reference_rules() -> None:
    qr = validate_iban(QR_IBAN)
    normal = validate_iban(IBAN)
    assert check_payment_reference(qr, QRR) == []
    assert [i.code for i in check_payment_reference(qr, None)] == ["qr_iban_without_qrr"]
    assert [i.code for i in check_payment_reference(qr, SCOR)] == ["invalid_qr_reference"]
    assert [i.code for i in check_payment_reference(qr, "210000000003139471430009016")] == [
        "invalid_qr_reference"
    ]
    assert check_payment_reference(normal, None) == []
    assert check_payment_reference(normal, SCOR) == []
    assert [i.code for i in check_payment_reference(normal, "RF00 1234")] == ["invalid_scor"]
    assert [i.code for i in check_payment_reference(normal, QRR)] == ["qrr_without_qr_iban"]
    assert [i.code for i in check_payment_reference(normal, "Rechnung 42")] == ["unknown_reference"]
    assert check_payment_reference(validate_iban("DE00"), QRR) == []


# ---------------------------------------------------------------------- UID
def test_known_uid() -> None:
    result = validate_uid(UID)
    assert (result.valid, result.normalized, result.vat_suffix) == (True, "CHE-100.155.212", "MWST")
    assert validate_uid("che100155212").valid
    assert not validate_uid("CHE-100.155.213").valid
    assert "Format" in validate_uid("100.155.212").error


def test_uid_check_digit_ten_is_never_valid() -> None:
    # Gewichtete Summe mit Rest 1 -> Prüfziffer 10 -> keine gültige UID
    first8 = next(f"{n:08d}" for n in range(10**8) if uid_check_digit(f"{n:08d}") is None)
    assert all(not validate_uid(f"CHE{first8}{d}").valid for d in range(10))
    with pytest.raises(ValueError, match="8 Ziffern"):
        uid_check_digit("1234567")


@settings(max_examples=400)
@given(digits=st.text(alphabet="0123456789", min_size=9, max_size=9))
def test_uid_differential_against_stdnum(digits: str) -> None:
    assert validate_uid(f"CHE{digits}").valid == uid.is_valid(f"CHE{digits}")


# ---------------------------------------------------------------------- MWST
def test_vat_rates_by_supply_date() -> None:
    assert vat_rates(date(2024, 1, 1)).all() == (Decimal("8.1"), Decimal("2.6"), Decimal("3.8"))
    assert vat_rates(date(2023, 12, 31)).all() == (Decimal("7.7"), Decimal("2.5"), Decimal("3.7"))
    with pytest.raises(ValueError, match="vor 2018"):
        vat_rates(date(2017, 12, 31))


def _line(net: str, rate: str) -> VatLine:
    n, r = Decimal(net), Decimal(rate)
    return VatLine(r, n, (n * r / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def test_vat_happy_path_and_mixed_rates() -> None:
    lines = [
        _line("1000.00", "8.1"),
        _line("200.00", "2.6"),
        VatLine(Decimal(0), Decimal("50"), Decimal(0)),
    ]
    gross = sum((ln.net + ln.vat for ln in lines), Decimal(0))
    assert check_vat(lines, gross=gross, supply_date=D2026) == []


def test_vat_old_rate_after_2024_is_flagged_with_hint() -> None:
    issues = check_vat([_line("1000.00", "7.7")], gross=Decimal("1077.00"), supply_date=D2026)
    assert [i.code for i in issues] == ["vat_rate_invalid"]
    assert "früheren Periode" in issues[0].message
    assert (
        check_vat([_line("1000.00", "7.7")], gross=Decimal("1077.00"), supply_date=date(2023, 6, 1))
        == []
    )


@pytest.mark.parametrize(
    ("lines", "gross", "code"),
    [
        (
            [VatLine(Decimal("8.1"), Decimal("1000"), Decimal("90"))],
            Decimal("1090"),
            "vat_amount_mismatch",
        ),
        ([_line("1000.00", "8.1")], Decimal("1090.00"), "total_mismatch"),
        (
            [VatLine(Decimal("19"), Decimal("100"), Decimal("19"))],
            Decimal("119"),
            "vat_rate_invalid",
        ),
        ([VatLine(Decimal(0), Decimal("100"), Decimal("5"))], Decimal("105"), "vat_on_exempt"),
        (
            [VatLine(Decimal("8.1"), Decimal("-100"), Decimal("-8.1"))],
            Decimal("-108.1"),
            "negative_amount",
        ),
        ([], Decimal("100"), "vat_lines_missing"),
    ],
)
def test_vat_issues(lines: list[VatLine], gross: Decimal, code: str) -> None:
    assert code in [i.code for i in check_vat(lines, gross=gross, supply_date=D2026)]


def test_vat_before_2018_is_reported() -> None:
    issues = check_vat([_line("100", "8.0")], gross=Decimal("108"), supply_date=date(2017, 1, 1))
    assert [i.code for i in issues] == ["vat_period_unsupported"]


@settings(max_examples=300)
@given(
    net=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("1000000"), places=2),
    rate=st.sampled_from(["8.1", "2.6", "3.8"]),
    delta=st.decimals(min_value=Decimal("0.06"), max_value=Decimal("100"), places=2),
)
def test_vat_property(net: Decimal, rate: str, delta: Decimal) -> None:
    line = _line(str(net), rate)
    gross = line.net + line.vat
    assert check_vat([line], gross=gross, supply_date=D2026) == []
    assert check_vat([line], gross=gross + delta, supply_date=D2026)
    wrong = VatLine(line.rate, line.net, line.vat + delta)
    assert "vat_amount_mismatch" in [
        i.code for i in check_vat([wrong], gross=line.net + wrong.vat, supply_date=D2026)
    ]


# ------------------------------------------------------------------ Rechnung
def _facts(**over: object) -> InvoiceFacts:
    base: dict[str, object] = {
        "iban": QR_IBAN,
        "reference": QRR,
        "supplier_uid": UID,
        "supply_date": D2026,
        "currency": "CHF",
        "gross": Decimal("1081.00"),
        "vat_lines": (_line("1000.00", "8.1"),),
    }
    base.update(over)
    return InvoiceFacts(**base)  # type: ignore[arg-type]


def test_invoice_passes_and_converts_to_check_outcome() -> None:
    result = check_invoice(_facts())
    assert result.passed
    assert result.summary() == "Belegprüfung bestanden."
    outcome = result.to_check_outcome()
    assert (outcome.name, outcome.passed, outcome.blocking) == ("belegpruefung", True, True)


@pytest.mark.parametrize(
    ("over", "code"),
    [
        ({"currency": "USD"}, "currency"),
        ({"gross": Decimal("0")}, "amount_range"),
        ({"gross": Decimal("1081.001")}, "amount_precision"),
        ({"iban": "CH9400762011623852957", "reference": None}, "invalid_iban"),
        ({"reference": None}, "qr_iban_without_qrr"),
        ({"supplier_uid": "CHE-100.155.213 MWST"}, "invalid_uid"),
    ],
)
def test_invoice_blocking_issues(over: dict[str, object], code: str) -> None:
    result = check_invoice(_facts(**over))
    assert not result.passed
    assert code in [i.code for i in result.issues]
    assert "nicht bestanden" in result.summary()


def test_invoice_non_blocking_hints() -> None:
    no_uid = check_invoice(_facts(supplier_uid=None))
    assert no_uid.passed
    assert [i.code for i in no_uid.issues] == ["vat_without_registration"]
    assert "Hinweisen" in no_uid.summary()
    no_suffix = check_invoice(_facts(supplier_uid="CHE-100.155.212"))
    assert [i.code for i in no_suffix.issues] == ["uid_without_vat_suffix"]
    exempt = check_invoice(
        _facts(
            supplier_uid=None,
            gross=Decimal("50"),
            vat_lines=(VatLine(Decimal(0), Decimal("50"), Decimal(0)),),
        )
    )
    assert exempt.issues == ()
