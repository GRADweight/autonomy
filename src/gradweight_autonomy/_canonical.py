"""Kanonisches JSON für Hashes und Signaturen.

Regeln (für externe Prüfer reproduzierbar):

* UTF-8, Schlüssel lexikografisch sortiert, keine Leerzeichen zwischen Tokens
  (``separators=(",", ":")``), Nicht-ASCII-Zeichen unverändert (``ensure_ascii=False``).
* ``NaN`` und ``Infinity`` sind verboten.
* Für Ganzzahlen, Strings, Booleans und ``null`` entspricht das Ergebnis RFC 8785
  (JSON Canonicalization Scheme). Fliesskommazahlen werden in Pythons
  ``repr``-Form serialisiert, die in Randfällen von RFC 8785 abweicht. Beträge
  deshalb als String oder als Ganzzahl in Rappen ablegen.
* Strings werden nicht Unicode-normalisiert.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any, TypeAlias

JSONScalar: TypeAlias = str | int | float | bool | None
JSONValue: TypeAlias = JSONScalar | Sequence["JSONValue"] | Mapping[str, "JSONValue"]


def canonical_json(value: Any) -> str:
    """Wert als kanonischen JSON-Text serialisieren.

    >>> canonical_json({"b": 1, "a": [True, None, "ä"]})
    '{"a":[true,null,"ä"],"b":1}'
    """
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Wert ist nicht als kanonisches JSON darstellbar: {exc}") from exc


def canonical_bytes(value: Any) -> bytes:
    """Kanonisches JSON als UTF-8-Bytes."""
    return canonical_json(value).encode("utf-8")


def to_jsonable(value: Any) -> Any:
    """Decimal-Werte rekursiv in Strings umwandeln (verlustfrei, kanonisierbar)."""
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, Mapping):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    return value
