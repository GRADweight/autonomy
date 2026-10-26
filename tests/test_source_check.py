"""Zahlen- und Quellenabgleich."""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from gradweight_autonomy.source_check import (
    KIND_DATE,
    KIND_IDENTIFIER,
    KIND_NUMBER,
    KIND_TIME,
    Source,
    check_numbers,
    extract_tokens,
)

QUELLEN = [
    Source("Der Rechnungsbetrag beträgt CHF 1'081.00.", "rechnung.pdf"),
    Source("MWST-Satz 8.1 % (Normalsatz). Fällig am 31.07.2026.", "rechnung.pdf"),
    Source("Rückgabe innert 30 Tagen. Versand ab 14:30 Uhr.", "agb.pdf"),
]


def keys(text: str) -> list[tuple[str, str, str | None]]:
    return [(t.kind, t.key, t.unit) for t in extract_tokens(text)]


# ------------------------------------------------------------- Befund aus dem Review
def test_citation_marker_is_not_a_number() -> None:
    """Früher: «30 Tage [2]» -> Veto «Fehlend: 2». Richtige Antworten wurden blockiert."""
    result = check_numbers("Die Frist beträgt 30 Tage [3].", QUELLEN)
    assert result.passed, result.summary()
    assert result.checked == 1


@pytest.mark.parametrize("marker", ["[2]", "[1, 3]", "[1-3]", "[1–3]", "[^2]"])
def test_citation_variants_are_ignored(marker: str) -> None:
    assert extract_tokens(f"Text {marker} Ende") == []


def test_list_markers_are_ignored() -> None:
    assert keys("1. Schritt\n2) Schritt\n  3. Schritt") == []
    assert keys("Seite 3. Danach") == [(KIND_NUMBER, "3", None)]


# ------------------------------------------------------------- Formate
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("CHF 1'234.50", (KIND_NUMBER, "1234.5", "CHF")),
        ("1’234.50 Franken", (KIND_NUMBER, "1234.5", "CHF")),
        ("1234,50 EUR", (KIND_NUMBER, "1234.5", "EUR")),
        ("1.234,50 €", (KIND_NUMBER, "1234.5", "EUR")),
        ("USD 1,234.50", (KIND_NUMBER, "1234.5", "USD")),
        ("Fr. 1'234.–", (KIND_NUMBER, "1234", "CHF")),
        ("1'234.-", (KIND_NUMBER, "1234", "CHF")),
        ("1.234.567", (KIND_NUMBER, "1234567", None)),
        ("1\u202f234.50", (KIND_NUMBER, "1234.5", None)),
        ("8.1 %", (KIND_NUMBER, "8.1", "%")),
        ("8,1%", (KIND_NUMBER, "8.1", "%")),
        ("2.6 Prozent", (KIND_NUMBER, "2.6", "%")),
        ("Rabatt -5 %", (KIND_NUMBER, "-5", "%")),
        ("31.07.2026", (KIND_DATE, "2026-07-31", None)),
        ("1.7.26", (KIND_DATE, "2026-07-01", None)),
        ("2026-07-31", (KIND_DATE, "2026-07-31", None)),
        ("31. Juli 2026", (KIND_DATE, "2026-07-31", None)),
        ("1. März 2026", (KIND_DATE, "2026-03-01", None)),
        ("3. Okt. 2026", (KIND_DATE, "2026-10-03", None)),
        ("14:30", (KIND_TIME, "14:30", None)),
        ("9:05:00", (KIND_TIME, "09:05:00", None)),
        ("CH93 0076 2011 6238 5295 7", (KIND_IDENTIFIER, "IBAN:CH9300762011623852957", None)),
        ("CHE-116.281.710 MWST", (KIND_IDENTIFIER, "UID:116281710", None)),
        (
            "21 00000 00003 13947 14300 09017",
            (KIND_IDENTIFIER, "QRR:210000000003139471430009017", None),
        ),
        ("31.02.2026", (KIND_IDENTIFIER, "RAW:31.02.2026", None)),
    ],
)
def test_formats(text: str, expected: tuple[str, str, str | None]) -> None:
    assert keys(text) == [expected]


@pytest.mark.parametrize("text", ["COVID-19", "GB-03", "A4", "Q3", "v1.2.3", "gw4"])
def test_identifiers_inside_words_are_not_numbers(text: str) -> None:
    assert extract_tokens(text) == []


def test_ranges_and_positions() -> None:
    tokens = extract_tokens("Lieferung in 3-5 Tagen")
    assert [(t.key, t.start, t.end) for t in tokens] == [("3", 13, 14), ("5", 15, 16)]


# ------------------------------------------------------------- Abgleich
def test_supported_answer_passes() -> None:
    answer = (
        "Der Betrag ist 1081 Franken, die MWST beträgt 8,1 % und die Rechnung ist am "
        "31. Juli 2026 fällig. Versand ab 14:30 im Jahr 2026."
    )
    result = check_numbers(answer, QUELLEN)
    assert result.passed, result.summary()
    assert "belegt" in result.summary()


def test_hallucinated_numbers_are_reported() -> None:
    result = check_numbers("Der Betrag ist CHF 5'432.00, der Satz 19 %.", QUELLEN)
    assert not result.passed
    assert [u.token.text for u in result.unsupported] == ["5'432.00", "19"]
    assert "nicht belegt" in result.summary()


def test_units_must_be_compatible() -> None:
    assert not check_numbers("Der Satz ist 1081 %.", QUELLEN).passed
    assert not check_numbers("Der Betrag ist EUR 1'081.00.", QUELLEN).passed
    assert check_numbers("Der Betrag ist 1'081.00.", QUELLEN).passed


def test_sign_matters() -> None:
    assert not check_numbers("Abweichung -30 Tage", QUELLEN).passed


def test_no_sources_means_nothing_is_supported() -> None:
    assert not check_numbers("Betrag 1081.00", []).passed
    assert check_numbers("Keine Zahlen hier.", []).passed


# ------------------------------------------------------------- Zitierpflicht
def test_require_citations() -> None:
    ok = check_numbers(
        "Der Betrag ist CHF 1'081.00 [1]. Rückgabe innert 30 Tagen [3].",
        QUELLEN,
        require_citations=True,
    )
    assert ok.passed, ok.summary()
    wrong_source = check_numbers("Rückgabe innert 30 Tagen [1].", QUELLEN, require_citations=True)
    assert [u.reason for u in wrong_source.unsupported] == ["nicht in [1]"]
    missing = check_numbers("Rückgabe innert 30 Tagen.", QUELLEN, require_citations=True)
    assert [u.reason for u in missing.unsupported] == ["Satz ohne Quellenverweis"]
    unknown = check_numbers("Rückgabe innert 30 Tagen [7].", QUELLEN, require_citations=True)
    assert [u.reason for u in unknown.unsupported] == ["Verweis auf unbekannte Quelle [7]"]
    ranged = check_numbers("Betrag 1'081.00 und 30 Tage [1-3].", QUELLEN, require_citations=True)
    assert ranged.passed
    no_numbers = check_numbers("Siehe Anhang [2].\nDanke.", QUELLEN, require_citations=True)
    assert no_numbers.passed
    assert no_numbers.citations_required


# ------------------------------------------------------------- Eigenschaften
_AMOUNTS = st.decimals(min_value=Decimal("0.01"), max_value=Decimal("9999999.99"), places=2)


def _swiss(value: Decimal, sep: str, decimal_sep: str) -> str:
    whole, frac = f"{value:.2f}".split(".")
    groups = []
    while whole:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    return sep.join(groups) + decimal_sep + frac


@settings(max_examples=200)
@given(value=_AMOUNTS, style=st.sampled_from([("'", "."), ("’", "."), ("", "."), ("", ",")]))
def test_swiss_amount_formats_roundtrip(value: Decimal, style: tuple[str, str]) -> None:
    text = f"Betrag CHF {_swiss(value, *style)} total"
    tokens = extract_tokens(text)
    assert len(tokens) == 1
    assert Decimal(tokens[0].key) == value
    assert tokens[0].unit == "CHF"


@settings(max_examples=150)
@given(
    present=st.lists(st.integers(min_value=10, max_value=10**6), min_size=1, max_size=5),
    extra=st.integers(min_value=10, max_value=10**6),
)
def test_answer_passes_iff_all_numbers_are_in_sources(present: list[int], extra: int) -> None:
    source = Source("Werte: " + "; ".join(f"{n:,}".replace(",", "'") for n in present))
    answer = "Es sind " + " und ".join(str(n) for n in present) + "."
    assert check_numbers(answer, [source]).passed
    with_extra = check_numbers(answer + f" Zusätzlich {extra}.", [source])
    assert with_extra.passed == (extra in present)


@settings(max_examples=100)
@given(n=st.integers(min_value=1, max_value=999), text=st.text(alphabet="abc ", max_size=10))
def test_citation_markers_never_become_tokens(n: int, text: str) -> None:
    assert extract_tokens(f"{text}[{n}]{text}") == []
