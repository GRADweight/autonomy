"""Zeilen-/Spaltenzuordnung für JSON Pointer."""

from __future__ import annotations

import json
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from gradweight_autonomy.validator.jsonpos import PointerLocator, Position
from gradweight_autonomy.validator.jsonschema_lite import escape_pointer_token

_JSON = st.recursive(
    st.one_of(
        st.none(),
        st.booleans(),
        st.integers(),
        st.floats(allow_nan=False, allow_infinity=False),
        st.text(max_size=8),
    ),
    lambda inner: st.one_of(
        st.lists(inner, max_size=4),
        st.dictionaries(st.text(max_size=6), inner, max_size=4),
    ),
    max_leaves=15,
)


def _pointers(value: Any, ptr: str = "") -> list[tuple[str, Any]]:
    found = [(ptr, value)]
    if isinstance(value, dict):
        for k, v in value.items():
            found += _pointers(v, f"{ptr}/{escape_pointer_token(k)}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            found += _pointers(v, f"{ptr}/{i}")
    return found


@settings(max_examples=200, deadline=None)
@given(value=_JSON, indent=st.sampled_from([None, 0, 2, 4]), ascii_only=st.booleans())
def test_every_pointer_maps_to_its_value(value: Any, indent: int | None, ascii_only: bool) -> None:
    text = json.dumps(value, indent=indent, ensure_ascii=ascii_only)
    locator = PointerLocator(text)
    decoder = json.JSONDecoder()
    for ptr, expected in _pointers(value):
        offset = locator.offset(ptr)
        assert offset is not None
        parsed, _ = decoder.raw_decode(text, offset)
        assert parsed == expected
        pos = locator.locate(ptr)
        line_start = text.rfind("\n", 0, offset) + 1
        assert pos == Position(text.count("\n", 0, offset) + 1, offset - line_start + 1)


def test_missing_pointer_falls_back_to_parent() -> None:
    text = '{\n  "a": {\n    "b": 1\n  }\n}'
    locator = PointerLocator(text)
    assert locator.locate("/a/fehlt") == Position(2, 8)
    assert locator.locate("/x/y") == Position(1, 1)
    assert locator.locate("") == Position(1, 1)


def test_invalid_text_yields_first_line() -> None:
    locator = PointerLocator("{ kaputt")
    assert locator.offset("") is None
    assert locator.locate("/a") == Position(1, 1)


def test_bom_and_empty_containers() -> None:
    locator = PointerLocator('\ufeff{"a": [], "b": {}, "c": [1, 2]}')
    assert locator.locate("/c/1") == Position(1, 29)
    assert locator.locate("/b") == Position(1, 16)
