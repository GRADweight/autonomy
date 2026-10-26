"""Schlanker JSON-Schema-Validator (Teilmenge von Draft 2020-12, nur Standardbibliothek).

Unterstützt genau die Schlüsselwörter, die das Use-Case-Schema verwendet. Ein
unbekanntes Schlüsselwort führt beim Laden zu einem Fehler, damit das Schema
nicht stillschweigend Regeln enthält, die hier nicht geprüft werden.

Die Übereinstimmung mit der Referenzimplementierung ``jsonschema`` wird in den
Tests differenziell (Hypothesis) geprüft. Eine bewusste Abweichung: ``$`` am
Ende eines ``pattern`` gilt wie in ECMA-262 nur am Textende; Python-``re`` liesse
zusätzlich einen abschliessenden Zeilenumbruch zu.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Any

SUPPORTED_KEYWORDS = frozenset(
    {
        # Struktur und Annotationen
        "$schema",
        "$id",
        "$defs",
        "$ref",
        "$comment",
        "title",
        "description",
        "examples",
        "default",
        "deprecated",
        "format",
        # Validierung
        "type",
        "enum",
        "const",
        "required",
        "properties",
        "additionalProperties",
        "items",
        "minItems",
        "maxItems",
        "uniqueItems",
        "minLength",
        "maxLength",
        "pattern",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
    }
)

_TYPE_LABELS = {
    "object": "ein Objekt",
    "array": "eine Liste",
    "string": "ein String",
    "integer": "eine ganze Zahl",
    "number": "eine Zahl",
    "boolean": "true oder false",
    "null": "null",
}


class SchemaDefinitionError(ValueError):
    """Das Schema selbst ist für diesen Validator ungültig."""


@dataclass(frozen=True)
class SchemaError:
    """Eine Verletzung des Schemas an einer Stelle (JSON Pointer)."""

    pointer: str
    message: str


def escape_pointer_token(token: str) -> str:
    """Token für einen JSON Pointer (RFC 6901) maskieren."""
    return token.replace("~", "~0").replace("/", "~1")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _matches_type(value: Any, type_name: str) -> bool:
    if type_name == "object":
        return isinstance(value, Mapping)
    if type_name == "array":
        return isinstance(value, list)
    if type_name == "string":
        return isinstance(value, str)
    if type_name == "boolean":
        return isinstance(value, bool)
    if type_name == "null":
        return value is None
    if type_name == "number":
        return _is_number(value)
    if type_name == "integer":
        if isinstance(value, bool):
            return False
        if isinstance(value, int):
            return True
        return isinstance(value, float) and math.isfinite(value) and value.is_integer()
    raise SchemaDefinitionError(f"unbekannter Typ {type_name!r}")


def _json_equal(a: Any, b: Any) -> bool:
    """Gleichheit nach JSON-Schema-Semantik (1 == 1.0, aber true != 1)."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if _is_number(a) and _is_number(b):
        return bool(a == b)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_json_equal(x, y) for x, y in zip(a, b, strict=True))
    if isinstance(a, Mapping) and isinstance(b, Mapping):
        return a.keys() == b.keys() and all(_json_equal(a[k], b[k]) for k in a)
    if type(a) is not type(b):
        return False
    return bool(a == b)


@lru_cache(maxsize=64)
def _compile(pattern: str) -> re.Pattern[str]:
    ecma_end = (
        pattern[:-1] + r"\Z" if pattern.endswith("$") and not pattern.endswith(r"\$") else pattern
    )
    try:
        return re.compile(ecma_end)
    except re.error as exc:
        raise SchemaDefinitionError(f"ungültiges pattern {pattern!r}: {exc}") from exc


class SchemaValidator:
    """Validiert JSON-Werte gegen ein (Teilmengen-)Schema."""

    def __init__(self, schema: Mapping[str, Any]) -> None:
        self._root = schema
        self._check_definition(schema, "#")

    # --------------------------------------------------------- definition
    def _check_definition(self, node: Any, where: str) -> None:
        if isinstance(node, bool):
            return
        if not isinstance(node, Mapping):
            raise SchemaDefinitionError(f"{where}: Schema muss Objekt oder boolean sein")
        unknown = set(node) - SUPPORTED_KEYWORDS
        if unknown:
            raise SchemaDefinitionError(
                f"{where}: nicht unterstützte Schlüsselwörter {sorted(unknown)}"
            )
        if "pattern" in node:
            _compile(node["pattern"])
        if "$ref" in node:
            self._resolve(node["$ref"])
        for key in ("properties", "$defs"):
            for name, sub in node.get(key, {}).items():
                self._check_definition(sub, f"{where}/{key}/{name}")
        for key in ("items", "additionalProperties"):
            if key in node:
                self._check_definition(node[key], f"{where}/{key}")

    def _resolve(self, ref: str) -> Any:
        if ref == "#":
            return self._root
        if not ref.startswith("#/"):
            raise SchemaDefinitionError(f"nur lokale $ref werden unterstützt: {ref!r}")
        node: Any = self._root
        for raw in ref[2:].split("/"):
            token = raw.replace("~1", "/").replace("~0", "~")
            if not isinstance(node, Mapping) or token not in node:
                raise SchemaDefinitionError(f"$ref nicht auflösbar: {ref!r}")
            node = node[token]
        return node

    # --------------------------------------------------------- validation
    def errors(self, instance: Any) -> list[SchemaError]:
        """Alle Verletzungen, sortiert nach Fundstelle."""
        found = list(self._validate(instance, self._root, ""))
        return sorted(found, key=lambda e: (e.pointer, e.message))

    def is_valid(self, instance: Any) -> bool:
        return not any(True for _ in self._validate(instance, self._root, ""))

    def _validate(self, value: Any, schema: Any, ptr: str) -> Iterator[SchemaError]:
        if schema is True:
            return
        if schema is False:
            yield SchemaError(ptr, "hier ist kein Wert erlaubt")
            return
        if "$ref" in schema:
            yield from self._validate(value, self._resolve(schema["$ref"]), ptr)
        if "type" in schema:
            types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
            if not any(_matches_type(value, t) for t in types):
                expected = " oder ".join(_TYPE_LABELS.get(str(t), str(t)) for t in types)
                yield SchemaError(ptr, f"muss {expected} sein")
                return
        if "const" in schema and not _json_equal(value, schema["const"]):
            yield SchemaError(ptr, f"muss {json.dumps(schema['const'], ensure_ascii=False)} sein")
        if "enum" in schema and not any(_json_equal(value, e) for e in schema["enum"]):
            allowed = ", ".join(json.dumps(e, ensure_ascii=False) for e in schema["enum"])
            yield SchemaError(ptr, f"muss einer dieser Werte sein: {allowed}")
        if isinstance(value, str):
            yield from self._validate_string(value, schema, ptr)
        elif _is_number(value):
            yield from self._validate_number(value, schema, ptr)
        elif isinstance(value, list):
            yield from self._validate_array(value, schema, ptr)
        elif isinstance(value, Mapping):
            yield from self._validate_object(value, schema, ptr)

    @staticmethod
    def _validate_string(value: str, schema: Mapping[str, Any], ptr: str) -> Iterator[SchemaError]:
        if "minLength" in schema and len(value) < schema["minLength"]:
            yield SchemaError(ptr, f"muss mindestens {schema['minLength']} Zeichen lang sein")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            yield SchemaError(ptr, f"darf höchstens {schema['maxLength']} Zeichen lang sein")
        if "pattern" in schema and not _compile(schema["pattern"]).search(value):
            yield SchemaError(ptr, f"entspricht nicht dem Muster {schema['pattern']}")

    @staticmethod
    def _validate_number(
        value: float, schema: Mapping[str, Any], ptr: str
    ) -> Iterator[SchemaError]:
        if "minimum" in schema and value < schema["minimum"]:
            yield SchemaError(ptr, f"muss >= {schema['minimum']} sein")
        if "maximum" in schema and value > schema["maximum"]:
            yield SchemaError(ptr, f"muss <= {schema['maximum']} sein")
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            yield SchemaError(ptr, f"muss > {schema['exclusiveMinimum']} sein")
        if "exclusiveMaximum" in schema and value >= schema["exclusiveMaximum"]:
            yield SchemaError(ptr, f"muss < {schema['exclusiveMaximum']} sein")

    def _validate_array(
        self, value: Sequence[Any], schema: Mapping[str, Any], ptr: str
    ) -> Iterator[SchemaError]:
        if "minItems" in schema and len(value) < schema["minItems"]:
            yield SchemaError(ptr, f"braucht mindestens {schema['minItems']} Einträge")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            yield SchemaError(ptr, f"darf höchstens {schema['maxItems']} Einträge haben")
        if schema.get("uniqueItems"):
            for i, item in enumerate(value):
                if any(_json_equal(item, other) for other in value[:i]):
                    yield SchemaError(f"{ptr}/{i}", "Eintrag ist doppelt")
        if "items" in schema:
            for i, item in enumerate(value):
                yield from self._validate(item, schema["items"], f"{ptr}/{i}")

    def _validate_object(
        self, value: Mapping[str, Any], schema: Mapping[str, Any], ptr: str
    ) -> Iterator[SchemaError]:
        for key in schema.get("required", ()):
            if key not in value:
                yield SchemaError(ptr, f"Pflichtfeld {key!r} fehlt")
        properties: Mapping[str, Any] = schema.get("properties", {})
        for key, item in value.items():
            child = f"{ptr}/{escape_pointer_token(key)}"
            if key in properties:
                yield from self._validate(item, properties[key], child)
            elif "additionalProperties" in schema:
                extra = schema["additionalProperties"]
                if extra is False:
                    yield SchemaError(child, f"unbekanntes Feld {key!r}")
                else:
                    yield from self._validate(item, extra, child)


SCHEMA_RESOURCE = "usecase-2.0.schema.json"


@lru_cache(maxsize=1)
def load_usecase_schema() -> dict[str, Any]:
    """Das mitgelieferte Use-Case-Schema laden."""
    text = (
        resources.files("gradweight_autonomy.validator")
        .joinpath("schemas")
        .joinpath(SCHEMA_RESOURCE)
        .read_text(encoding="utf-8")
    )
    data: dict[str, Any] = json.loads(text)
    return data


@lru_cache(maxsize=1)
def usecase_validator() -> SchemaValidator:
    """Validator für das mitgelieferte Use-Case-Schema."""
    return SchemaValidator(load_usecase_schema())
