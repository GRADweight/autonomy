"""Zahlen- und Quellenabgleich: Stehen die Zahlen einer Antwort in den Quellen?

Deterministisch und ohne Modell. Geprüft werden Beträge, Prozentsätze, Zahlen,
Daten, Uhrzeiten sowie Kennungen (IBAN, QR-Referenz, UID). Was nicht geprüft
wird: Aussagen ohne Zahlen, Umformulierungen, falsche Zuordnung einer korrekten
Zahl zum falschen Sachverhalt. Dafür gibt es optional
:class:`gradweight_autonomy.llm.SecondModelReview`.

Unterstützte Schreibweisen (Auswahl): ``1'234.50``, ``1’234.50``, ``1234,50``,
``1.234,50``, ``1,234.50``, ``CHF 1'234.–``, ``8.1 %``, ``31.07.2026``,
``2026-07-31``, ``31. Juli 2026``, ``14:30``. Quellenverweise wie ``[2]``,
``[1, 3]`` oder ``[^4]`` und Aufzählungsnummern am Zeilenanfang zählen nicht als
Zahlen.

>>> sources = [Source("AGB"), Source("Frist: 30 Tage")]
>>> check_numbers("Die Frist beträgt 30 Tage [2].", sources).passed
True
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

KIND_NUMBER = "number"
KIND_DATE = "date"
KIND_TIME = "time"
KIND_IDENTIFIER = "identifier"

_MONTHS = {
    "januar": 1,
    "jan": 1,
    "februar": 2,
    "feb": 2,
    "märz": 3,
    "maerz": 3,
    "mär": 3,
    "mrz": 3,
    "april": 4,
    "apr": 4,
    "mai": 5,
    "juni": 6,
    "jun": 6,
    "juli": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sept": 9,
    "sep": 9,
    "oktober": 10,
    "okt": 10,
    "november": 11,
    "nov": 11,
    "dezember": 12,
    "dez": 12,
}
_MONTH_ALT = "|".join(sorted(_MONTHS, key=len, reverse=True))
_THIN = "\u00a0\u202f\u2009"
_APOS = "'\u2019"

_TOKEN = re.compile(
    rf"""
    (?<![0-9A-Za-zÄÖÜäöüß_])(?<![A-Za-z]-)(?<![0-9][.,'\u2019])
    (?:
        (?P<iban>(?:CH|LI)[0-9]{{2}}(?:\ ?[0-9A-Z]{{4}}){{4}}\ ?[0-9A-Z])
      | (?P<uid>CHE-?[0-9]{{3}}\.?[0-9]{{3}}\.?[0-9]{{3}})
      | (?P<qrr>[0-9]{{2}}(?:\ [0-9]{{5}}){{5}}|[0-9]{{27}})
      | (?P<iso>[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}})
      | (?P<named>[0-9]{{1,2}}\.\ ?(?:{_MONTH_ALT})\.?\ [0-9]{{4}})
      | (?P<chdate>[0-9]{{1,2}}\.[0-9]{{1,2}}\.(?:[0-9]{{4}}|[0-9]{{2}})(?![0-9]))
      | (?P<time>[0-9]{{1,2}}:[0-9]{{2}}(?::[0-9]{{2}})?)
      | (?P<num>
            [0-9]{{1,3}}(?:[{_APOS}][0-9]{{3}})+(?:[.,][0-9]+)?
          | [0-9]{{1,3}}(?:[{_THIN}][0-9]{{3}})+(?:[.,][0-9]+)?
          | [0-9]{{1,3}}(?:,[0-9]{{3}})+\.[0-9]+
          | [0-9]{{1,3}}(?:\.[0-9]{{3}})+,[0-9]+
          | [0-9]{{1,3}}(?:\.[0-9]{{3}}){{2,}}
          | [0-9]+(?:[.,][0-9]+)?
        )
        (?P<strich>\.[–-](?![0-9]))?
    )
    (?![0-9])
    """,
    re.VERBOSE | re.IGNORECASE,
)
_CITATION = re.compile(r"\[\^?[0-9]+(?:\s*[,–-]\s*[0-9]+)*\]")
_LIST_MARKER = re.compile(
    rf"(?mi)^[ \t]*([0-9]{{1,3}})[.)][ \t](?![ \t]*(?:{_MONTH_ALT})\.?[ \t][0-9]{{4}})"
)
_PERCENT_AFTER = re.compile(r"\s?(?:%|Prozent\b)", re.IGNORECASE)
_CURRENCY_BEFORE = re.compile(r"(CHF|SFr\.|Fr\.|EUR|€|USD|\$)\s?$")
_CURRENCY_AFTER = re.compile(r"\s?(CHF|Franken|EUR|Euro|€|USD)(?![A-Za-z])", re.IGNORECASE)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-ZÄÖÜ0-9«\"„(])|\n+")
_CURRENCY_CODES = {
    "chf": "CHF",
    "sfr.": "CHF",
    "fr.": "CHF",
    "franken": "CHF",
    "eur": "EUR",
    "euro": "EUR",
    "€": "EUR",
    "usd": "USD",
    "$": "USD",
}


@dataclass(frozen=True)
class NumberToken:
    """Eine erkannte Zahl, ein Datum oder eine Kennung mit Position im Text."""

    text: str
    kind: str
    key: str
    unit: str | None
    start: int
    end: int


@dataclass(frozen=True)
class Source:
    """Eine Fundstelle (z. B. ein RAG-Abschnitt)."""

    text: str
    ref: str = ""


@dataclass(frozen=True)
class Unsupported:
    """Eine nicht belegte Angabe mit Grund."""

    token: NumberToken
    reason: str


@dataclass(frozen=True)
class SourceCheckResult:
    """Ergebnis des Abgleichs."""

    passed: bool
    checked: int
    unsupported: tuple[Unsupported, ...]
    citations_required: bool

    def summary(self) -> str:
        """Kurzfassung (Deutsch)."""
        if self.passed:
            return f"Abgleich bestanden: {self.checked} Angaben in den Quellen belegt."
        shown = ", ".join(dict.fromkeys(f"{u.token.text} ({u.reason})" for u in self.unsupported))
        return (
            f"Abgleich nicht bestanden: {len(self.unsupported)} von {self.checked} Angaben "
            f"nicht belegt: {shown}"
        )


def _decimal_key(raw: str) -> str | None:
    text = raw
    for sep in (*_APOS, *_THIN):
        text = text.replace(sep, "")
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif text.count(".") > 1:
        text = text.replace(".", "")
    else:
        text = text.replace(",", ".")
    try:
        value = Decimal(text)
    except InvalidOperation:  # pragma: no cover - Regex lässt nur Ziffern zu
        return None
    return format(value.normalize(), "f")


def _date_key(year: int, month: int, day: int) -> str | None:
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def _full_year(raw: str) -> int:
    year = int(raw)
    return 2000 + year if len(raw) == 2 else year


def _unit(text: str, start: int, end: int) -> str | None:
    if _PERCENT_AFTER.match(text, end):
        return "%"
    before = _CURRENCY_BEFORE.search(text, max(0, start - 6), start)
    if before:
        return _CURRENCY_CODES[before.group(1).lower()]
    after = _CURRENCY_AFTER.match(text, end)
    if after:
        return _CURRENCY_CODES[after.group(1).lower()]
    return None


def _mask(text: str, pattern: re.Pattern[str], group: int = 0) -> str:
    def blank(m: re.Match[str]) -> str:
        if group == 0:
            return " " * len(m.group(0))
        s, e = m.span(group)
        return m.group(0)[: s - m.start()] + " " * (e - s) + m.group(0)[e - m.start() :]

    return pattern.sub(blank, text)


def _negative(text: str, start: int) -> bool:
    if start == 0 or text[start - 1] not in "-\u2212":
        return False
    return start == 1 or text[start - 2] in " \t\n(:="


def extract_tokens(text: str) -> list[NumberToken]:
    """Alle Zahlen, Daten und Kennungen eines Textes (ohne Quellenverweise)."""
    cleaned = _mask(_mask(text, _CITATION), _LIST_MARKER, group=1)
    tokens: list[NumberToken] = []
    for m in _TOKEN.finditer(cleaned):
        raw = m.group(0)
        start, end = m.span()
        kind = KIND_NUMBER
        unit: str | None = None
        key: str | None
        if m.group("iban"):
            kind, key = KIND_IDENTIFIER, "IBAN:" + raw.replace(" ", "").upper()
        elif m.group("uid"):
            kind, key = KIND_IDENTIFIER, "UID:" + re.sub(r"[^0-9]", "", raw)
        elif m.group("qrr"):
            kind, key = KIND_IDENTIFIER, "QRR:" + raw.replace(" ", "")
        elif m.group("iso"):
            y, mo, d = (int(x) for x in raw.split("-"))
            kind, key = KIND_DATE, _date_key(y, mo, d)
        elif m.group("named"):
            day_part, rest = raw.split(".", 1)
            month_word, year = rest.replace(".", " ").split()
            kind, key = KIND_DATE, _date_key(int(year), _MONTHS[month_word.lower()], int(day_part))
        elif m.group("chdate"):
            day_text, month_text, year_text = raw.split(".")
            kind, key = KIND_DATE, _date_key(_full_year(year_text), int(month_text), int(day_text))
        elif m.group("time"):
            parts = [int(p) for p in raw.split(":")]
            kind, key = KIND_TIME, ":".join(f"{p:02d}" for p in parts)
        else:
            num = m.group("num")
            key = _decimal_key(num)
            unit = "CHF" if m.group("strich") else _unit(cleaned, start, end)
            if key is not None and key != "0" and _negative(cleaned, start):
                key = "-" + key
        if key is None:  # ungültiges Datum wie 31.02.2026: als Zeichenkette vergleichen
            kind, key = KIND_IDENTIFIER, "RAW:" + raw
        tokens.append(NumberToken(text[start:end], kind, key, unit, start, end))
    return tokens


def _vocabulary(texts: Iterable[str]) -> list[NumberToken]:
    vocab: list[NumberToken] = []
    for text in texts:
        for token in extract_tokens(text):
            vocab.append(token)
            if token.kind == KIND_DATE:  # «im Jahr 2026» ist durch ein Datum 2026 belegt
                vocab.append(NumberToken(token.text, KIND_NUMBER, token.key[:4], None, 0, 0))
    return vocab


def _supported(token: NumberToken, vocab: Sequence[NumberToken]) -> bool:
    for candidate in vocab:
        if candidate.kind != token.kind or candidate.key != token.key:
            continue
        if token.unit is None or candidate.unit is None or token.unit == candidate.unit:
            return True
    return False


def _segments(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    start = 0
    for m in _SENTENCE_END.finditer(text):
        spans.append((start, m.start()))
        start = m.end()
    spans.append((start, len(text)))
    return [(s, e) for s, e in spans if text[s:e].strip()]


def _citations(segment: str) -> list[int]:
    numbers: list[int] = []
    for m in _CITATION.finditer(segment):
        inner = m.group(0).strip("[]^")
        for part in re.split(r"\s*,\s*", inner):
            if re.fullmatch(r"[0-9]+\s*[–-]\s*[0-9]+", part):
                lo, hi = (int(x) for x in re.split(r"\s*[–-]\s*", part))
                numbers.extend(range(lo, hi + 1))
            else:
                numbers.append(int(part))
    return numbers


def check_numbers(
    answer: str, sources: Sequence[Source], *, require_citations: bool = False
) -> SourceCheckResult:
    """Jede Zahl der Antwort muss in den Quellen stehen.

    ``require_citations=False``: Abgleich gegen alle Quellen.
    ``require_citations=True``: Jeder Satz mit Zahlen braucht einen Verweis
    ``[n]`` (1-basiert auf ``sources``), und die Zahl muss in einer der dort
    zitierten Quellen stehen. Sätze werden an ``. ! ?`` mit folgendem
    Grossbuchstaben bzw. an Zeilenumbrüchen getrennt; Abkürzungen können zu
    zusätzlichen Trennungen und damit zu (sicheren) Fehlalarmen führen.
    """
    tokens = extract_tokens(answer)
    unsupported: list[Unsupported] = []
    if not require_citations:
        vocab = _vocabulary(s.text for s in sources)
        unsupported = [
            Unsupported(t, "in keiner Quelle") for t in tokens if not _supported(t, vocab)
        ]
    else:
        per_source = [_vocabulary([s.text]) for s in sources]
        for seg_start, seg_end in _segments(answer):
            seg_tokens = [t for t in tokens if seg_start <= t.start < seg_end]
            if not seg_tokens:
                continue
            cited = _citations(answer[seg_start:seg_end])
            invalid = [n for n in cited if not 1 <= n <= len(sources)]
            if not cited or invalid:
                reason = (
                    "Satz ohne Quellenverweis"
                    if not cited
                    else f"Verweis auf unbekannte Quelle [{invalid[0]}]"
                )
                unsupported.extend(Unsupported(t, reason) for t in seg_tokens)
                continue
            vocab = [tok for n in cited for tok in per_source[n - 1]]
            label = ", ".join(f"[{n}]" for n in dict.fromkeys(cited))
            unsupported.extend(
                Unsupported(t, f"nicht in {label}") for t in seg_tokens if not _supported(t, vocab)
            )
    return SourceCheckResult(
        passed=not unsupported,
        checked=len(tokens),
        unsupported=tuple(unsupported),
        citations_required=require_citations,
    )
