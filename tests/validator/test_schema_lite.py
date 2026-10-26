"""Schlanker Schema-Validator: Einzelfälle und Differenztest gegen jsonschema."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from gradweight_autonomy.validator.jsonschema_lite import (
    SchemaDefinitionError,
    SchemaValidator,
    load_usecase_schema,
    usecase_validator,
)
from gradweight_autonomy.validator.model import (
    CONTROL_STATUSES,
    CONTROLS,
    DATA_CLASSES,
    HUMAN_ROLES,
    MEASUREMENT_METHODS,
    MONEY_PERIODS,
    RESIDENCIES,
    SCHEMA_VERSION,
    STEP_HUMAN_ROLES,
    WHO_PLANS,
    EvidenceType,
)

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = sorted((ROOT / "examples").rglob("*.json"))
SCHEMA = load_usecase_schema()
REFERENCE = jsonschema.Draft202012Validator(SCHEMA)


def _example(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((ROOT / "examples" / name).read_text(encoding="utf-8"))
    return data


def test_schema_is_valid_draft_2020_12() -> None:
    jsonschema.Draft202012Validator.check_schema(SCHEMA)
    assert SCHEMA["$id"] == f"urn:gradweight:autonomy:usecase:{SCHEMA_VERSION}"


def test_schema_enums_match_model() -> None:
    props = SCHEMA["properties"]
    defs = SCHEMA["$defs"]
    assert tuple(props["who_plans"]["enum"]) == WHO_PLANS
    assert tuple(props["human_role"]["enum"]) == HUMAN_ROLES
    assert tuple(defs["data"]["properties"]["classification"]["enum"]) == DATA_CLASSES
    assert tuple(defs["data"]["properties"]["residency"]["enum"]) == RESIDENCIES
    assert tuple(defs["measurement"]["properties"]["method"]["enum"]) == MEASUREMENT_METHODS
    assert tuple(defs["money_limit"]["properties"]["per"]["enum"]) == MONEY_PERIODS
    assert tuple(defs["step"]["properties"]["human_role"]["enum"]) == STEP_HUMAN_ROLES
    assert tuple(defs["control"]["properties"]["status"]["enum"]) == CONTROL_STATUSES
    assert set(defs["controls"]["properties"]) == set(CONTROLS)
    assert set(defs["evidence"]["properties"]["type"]["enum"]) == {t.value for t in EvidenceType}


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_all_examples_are_schema_valid_in_both_validators(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert REFERENCE.is_valid(data)
    assert usecase_validator().errors(data) == []


def test_error_messages_and_pointers() -> None:
    case = _example("gw4-c-teile-nachbestellen.json")
    case["level"] = "4"
    case["risk"]["money_effect"] = "ja"
    del case["owner"]
    case["unbekannt"] = 1
    case["evidence"][0]["type"] = "foto"
    errors = {(e.pointer, e.message) for e in usecase_validator().errors(case)}
    assert ("/level", "muss eine ganze Zahl sein") in errors
    assert ("/risk/money_effect", "muss true oder false sein") in errors
    assert ("", "Pflichtfeld 'owner' fehlt") in errors
    assert ("/unbekannt", "unbekanntes Feld 'unbekannt'") in errors
    assert any(
        p == "/evidence/0/type" and m.startswith("muss einer dieser Werte") for p, m in errors
    )


@pytest.mark.parametrize(
    ("schema", "value", "valid"),
    [
        ({"type": "integer"}, 4.0, True),
        ({"type": "integer"}, 4.5, False),
        ({"type": "integer"}, True, False),
        ({"type": "number"}, False, False),
        ({"type": ["string", "null"]}, None, True),
        ({"const": 1}, 1.0, True),
        ({"const": 1}, True, False),
        ({"enum": [[1, 2]]}, [1, 2], True),
        ({"enum": [{"a": 1}]}, {"a": 1}, True),
        ({"enum": [{"a": 1}]}, {"a": 2}, False),
        ({"enum": ["a"]}, ["a"], False),
        ({"uniqueItems": True}, [1, 1.0], False),
        ({"uniqueItems": True}, [1, True], True),
        ({"minItems": 2, "maxItems": 3}, [1], False),
        ({"maxItems": 1}, [1, 2], False),
        ({"minLength": 2, "maxLength": 3}, "abcd", False),
        ({"minimum": 1, "maximum": 3}, 0, False),
        ({"maximum": 3}, 4, False),
        ({"exclusiveMinimum": 0}, 0, False),
        ({"exclusiveMaximum": 1}, 1, False),
        ({"pattern": "^a$"}, "a\n", False),
        ({"pattern": "b"}, "abc", True),
        ({"pattern": r"x\$"}, "x$", True),
        ({"additionalProperties": {"type": "string"}}, {"x": 1}, False),
        ({"additionalProperties": {"type": "string"}}, {"x": "y"}, True),
        ({"items": False}, [1], False),
        ({"items": True}, [1], True),
        ({"properties": {"a/b~c": {"type": "string"}}}, {"a/b~c": 1}, False),
        ({"type": "object", "properties": {"c": {"$ref": "#"}}}, {"c": {"c": {}}}, True),
        ({"type": "object", "properties": {"c": {"$ref": "#"}}}, {"c": {"c": 1}}, False),
    ],
)
def test_keyword_semantics(schema: dict[str, Any], value: Any, valid: bool) -> None:
    assert SchemaValidator(schema).is_valid(value) is valid


def test_pointer_escaping() -> None:
    errors = SchemaValidator({"properties": {"a/b~c": {"type": "string"}}}).errors({"a/b~c": 1})
    assert errors[0].pointer == "/a~1b~0c"


def test_trailing_newline_is_rejected_unlike_python_re() -> None:
    """Bewusste Abweichung: ECMA-262-Semantik für '$'."""
    case = _example("gw0-marktforschung.json")
    case["id"] = "gw0-marktforschung\n"
    assert REFERENCE.is_valid(case)  # Python-re lässt den Zeilenumbruch zu
    assert not usecase_validator().is_valid(case)


@pytest.mark.parametrize(
    ("schema", "message"),
    [
        ({"if": {}}, "nicht unterstützte"),
        ({"pattern": "("}, "ungültiges pattern"),
        ({"$ref": "https://example.org/x"}, "nur lokale"),
        ({"$ref": "#/$defs/fehlt"}, "nicht auflösbar"),
        ({"properties": {"a": 3}}, "Objekt oder boolean"),
        ({"type": "zahl"}, "unbekannter Typ"),
    ],
)
def test_schema_definition_errors(schema: dict[str, Any], message: str) -> None:
    with pytest.raises(SchemaDefinitionError, match=message):
        SchemaValidator(schema).errors({"a": 1} if "type" not in schema else 1)


# --------------------------------------------------------------------- Differenztest
_SCALARS = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-3, max_value=10),
    st.floats(allow_nan=False, allow_infinity=False, width=32),
    st.text(alphabet="abcxyz0123456789-_./:^ ", max_size=12),
    st.sampled_from(
        [
            "model",
            "mandate",
            "geheim",
            "on_prem",
            "pass^k",
            "implemented",
            "test_report",
            "2026-10-01",
            "2.0",
            "../x",
            "/etc/passwd",
            "https://example.org/a",
        ]
    ),
)
_VALUES = st.recursive(
    _SCALARS,
    lambda inner: st.one_of(
        st.lists(inner, max_size=3),
        st.dictionaries(st.sampled_from(["status", "id", "x", "amount"]), inner, max_size=3),
    ),
    max_leaves=6,
)


def _paths(value: Any, prefix: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
    found = [prefix]
    if isinstance(value, dict):
        for k, v in value.items():
            found += _paths(v, (*prefix, k))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            found += _paths(v, (*prefix, i))
    return found


@settings(max_examples=400, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    base=st.sampled_from(EXAMPLES),
    data=st.data(),
)
def test_differential_against_reference_implementation(base: Path, data: st.DataObject) -> None:
    case = json.loads(base.read_text(encoding="utf-8"))
    mutated = copy.deepcopy(case)
    for _ in range(data.draw(st.integers(min_value=1, max_value=3))):
        paths = [p for p in _paths(mutated) if p]
        path = data.draw(st.sampled_from(paths))
        parent: Any = mutated
        for key in path[:-1]:
            parent = parent[key]
        action = data.draw(st.sampled_from(["replace", "delete", "add"]))
        if action == "delete":
            del parent[path[-1]]
        elif action == "add" and isinstance(parent, dict):
            parent[data.draw(st.sampled_from(["extra", "status", "level", "ref"]))] = data.draw(
                _VALUES
            )
        else:
            parent[path[-1]] = data.draw(_VALUES)
    assert usecase_validator().is_valid(mutated) == REFERENCE.is_valid(mutated)
