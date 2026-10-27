"""Regel-Referenz als Markdown erzeugen (Quelle für ``docs/regeln.md``)."""

from __future__ import annotations

import json
from typing import Any

from gradweight_autonomy.validator.jsonschema_lite import load_usecase_schema
from gradweight_autonomy.validator.model import (
    ALLOWED_AXES,
    CONTROLS,
    EVIDENCE_TYPE_LABELS,
    EXCEPTION_ONLY_CONTROLS,
    LEVEL_NAMES,
    LEVEL_REQUIREMENTS,
    LEVELS,
    MANDATE_EVIDENCE_TYPES,
    MEASUREMENT_EVIDENCE_TYPES,
    SCHEMA_VERSION,
    Severity,
)
from gradweight_autonomy.validator.rules import RULES

_CELL = {Severity.ERROR: "F", Severity.WARNING: "W", Severity.NOTE: "H", None: "–"}


def rules_markdown() -> str:
    """Vollständige Regel-Referenz (Deutsch)."""
    out: list[str] = [
        "# Regel-Referenz GB-01 bis GB-" + RULES[-1].id.split("-")[1],
        "",
        (
            "<!-- Automatisch erzeugt mit `gw-autonomy rules --format markdown`. Nicht von Hand "
            "bearbeiten; ein Test vergleicht diese Datei mit dem Code. -->"
        ),
        "",
        (
            f"Der Validator kennt {len(RULES)} Regeln. Schweregrade: **F** = Fehler (Exit-Code 1), "
            "**W** = Warnung, **H** = Hinweis, **–** = greift auf diesem Grad nicht."
        ),
        "",
        "## Übersicht: höchster Schweregrad je Grad",
        "",
        "| Regel | Titel | " + " | ".join(f"G{lv}" for lv in LEVELS) + " | Greift |",
        "|---|---|" + "---|" * len(LEVELS) + "---|",
    ]
    for rule in RULES:
        cells = " | ".join(_CELL[s] for s in rule.matrix)
        out.append(
            f"| [{rule.id}](#{rule.id.lower()}) | {rule.title} | {cells} | {rule.condition} |"
        )
    out += [
        "",
        "Grade: " + "; ".join(f"{lv} = {name}" for lv, name in LEVEL_NAMES.items()) + ".",
        "",
        "## Zulässige Achsen je Grad (GB-02)",
        "",
        "| Grad | Name | Zulässige Kombinationen `who_plans` / `human_role` |",
        "|---|---|---|",
    ]
    for lv in LEVELS:
        combos = ", ".join(f"`{w}` / `{r}`" for w, r in sorted(ALLOWED_AXES[lv]))
        out.append(f"| {lv} | {LEVEL_NAMES[lv]} | {combos} |")
    out += [
        "",
        "## Regeln im Detail",
        "",
    ]
    for rule in RULES:
        out += [
            f"### {rule.id}",
            "",
            (
                f"**{rule.title}** (`{rule.name}`, Standard-Schweregrad: "
                f"{rule.default_severity.label})"
            ),
            "",
            f"- **Greift:** {rule.condition}",
            f"- **Prüft:** {rule.checks}",
            f"- **Warum:** {rule.rationale}",
            f"- **Behebung:** {rule.remediation}",
            "- **Referenzen:** " + "; ".join(rule.references),
            "",
        ]
    out += [
        "## Kontrollen und zulässige Nachweise",
        "",
        (
            "Eine Kontrolle gilt nur als umgesetzt, wenn `status` = `implemented` ist und "
            "mindestens ein Nachweis eines zulässigen Typs referenziert wird (GB-19)."
        ),
        "",
        "| Kontrolle | Titel | Pflicht | Zulässige Nachweistypen | Höchstalter |",
        "|---|---|---|---|---|",
    ]
    required: dict[str, str] = {
        req.control: f"ab Grad {req.min_level} ({req.severity.label})" for req in LEVEL_REQUIREMENTS
    }
    for control_id in EXCEPTION_ONLY_CONTROLS:
        required[control_id] = "bei human_role exception_only (Fehler)"
    for control in CONTROLS.values():
        age = f"{control.max_evidence_age_days} Tage" if control.max_evidence_age_days else "–"
        pflicht = required.get(control.id, f"bedingt, siehe {control.rule_id}")
        types = ", ".join(f"`{t.value}`" for t in control.evidence_types)
        out.append(f"| `{control.id}` | {control.title} | {pflicht} | {types} | {age} |")
    out += [
        "",
        "Mandat (`mandate.evidence`): "
        + ", ".join(f"`{t.value}`" for t in MANDATE_EVIDENCE_TYPES)
        + ". Messung (`measurement.evidence`): "
        + ", ".join(f"`{t.value}`" for t in MEASUREMENT_EVIDENCE_TYPES)
        + ".",
        "",
        "## Nachweistypen",
        "",
        "| Typ | Bedeutung |",
        "|---|---|",
    ]
    out += [f"| `{t.value}` | {label} |" for t, label in EVIDENCE_TYPE_LABELS.items()]
    return "\n".join(out) + "\n"


def rules_json() -> str:
    """Regel-Metadaten als JSON (für eigene Werkzeuge)."""
    data: list[dict[str, Any]] = [
        {
            "id": r.id,
            "name": r.name,
            "title": r.title,
            "condition": r.condition,
            "checks": r.checks,
            "rationale": r.rationale,
            "references": list(r.references),
            "remediation": r.remediation,
            "default_severity": r.default_severity.value,
            "severity_by_level": {
                str(lv): (s.value if s else None) for lv, s in zip(LEVELS, r.matrix, strict=True)
            },
        }
        for r in RULES
    ]
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def rules_text() -> str:
    """Kurzliste für das Terminal."""
    return "\n".join(f"{r.id}  {r.default_severity.label:<8} {r.title}" for r in RULES) + "\n"


def _type_text(node: dict[str, Any]) -> str:
    if "const" in node:
        return f"`{json.dumps(node['const'], ensure_ascii=False)}`"
    if "enum" in node:
        return " \\| ".join(f"`{v}`" for v in node["enum"])
    kind = str(node.get("type", "–"))
    limits = []
    for key, label in (("minimum", ">="), ("maximum", "<="), ("exclusiveMinimum", ">")):
        if key in node:
            limits.append(f"{label} {node[key]}")
    if "pattern" in node and kind == "string":
        limits.append("Muster")
    return kind + (f" ({', '.join(limits)})" if limits else "")


def schema_markdown() -> str:
    """Feldreferenz des Use-Case-Schemas (Quelle für ``docs/schema.md``)."""
    schema = load_usecase_schema()
    defs: dict[str, Any] = schema["$defs"]
    rows: list[str] = []

    def resolve(node: dict[str, Any]) -> dict[str, Any]:
        ref = node.get("$ref")
        return dict(defs[ref.rsplit("/", 1)[1]]) if isinstance(ref, str) else node

    def walk(node: dict[str, Any], prefix: str) -> None:
        node = resolve(node)
        required = set(node.get("required", ()))
        for name, raw in node.get("properties", {}).items():
            if name == "$schema":
                continue
            child = dict(resolve(raw))
            if "description" in raw:
                child["description"] = raw["description"]
            path = f"{prefix}{name}"
            if prefix == "controls.":
                continue
            kind = child.get("type")
            if kind == "array":
                items = resolve(child["items"])
                if items.get("type") == "object":
                    rows.append(
                        f"| `{path}[]` | Liste von Objekten | {_yes(name in required)} | "
                        f"{child.get('description', '')} |"
                    )
                    walk(items, f"{path}[].")
                else:
                    rows.append(
                        f"| `{path}[]` | Liste: {_type_text(items)} | "
                        f"{_yes(name in required)} | {child.get('description', '')} |"
                    )
            elif name == "controls":
                ids = ", ".join(f"`{c}`" for c in child["properties"])
                rows.append(f"| `controls.<kontrolle>` | Objekt | nein | Eine von: {ids} |")
                walk(defs["control"], "controls.<kontrolle>.")
            elif kind == "object":
                rows.append(
                    f"| `{path}` | Objekt | {_yes(name in required)} | "
                    f"{child.get('description', '')} |"
                )
                walk(child, f"{path}.")
            else:
                rows.append(
                    f"| `{path}` | {_type_text(child)} | {_yes(name in required)} | "
                    f"{child.get('description', '')} |"
                )

    walk(schema, "")
    head = [
        f"# Feldreferenz Use-Case-Schema {SCHEMA_VERSION}",
        "",
        (
            "<!-- Automatisch erzeugt mit `gw-autonomy schema --format markdown`. Nicht von Hand "
            "bearbeiten; ein Test vergleicht diese Datei mit dem Schema. -->"
        ),
        "",
        (
            "Schema: `src/gradweight_autonomy/validator/schemas/"
            f"usecase-{SCHEMA_VERSION}.schema.json` (`$id` `{schema['$id']}`). "
            "Unbekannte Felder sind nicht erlaubt."
        ),
        "",
        "| Feld | Typ | Pflicht | Beschreibung |",
        "|---|---|---|---|",
    ]
    return "\n".join(head + rows) + "\n"


def _yes(flag: bool) -> str:
    return "ja" if flag else "nein"
