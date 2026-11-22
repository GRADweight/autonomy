"""Regelwerk GB-01 bis GB-22 (einzige Quelle für Prüflogik und Regel-Doku).

Jede Regel hat ID, Titel, Prüfgegenstand, Begründung, Referenzen, Behebung und
eine Matrix «höchster Schweregrad je Grad 0–5». Grad-abhängige Prüfungen lesen
ihren Schweregrad aus dieser Matrix; die generierte Regel-Doku
(``docs/regeln.md``) und das Verhalten können deshalb nicht auseinanderlaufen.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from gradweight_autonomy.validator.model import (
    ALLOWED_AXES,
    CONTROLS,
    EXCEPTION_ONLY_CONTROLS,
    LEVEL_NAMES,
    LEVEL_REQUIREMENTS,
    LEVELS,
    MANDATE_EVIDENCE_TYPES,
    MEASUREMENT_EVIDENCE_TYPES,
    EvidenceType,
    Severity,
    min_level_for_axes,
)

E, W, N = Severity.ERROR, Severity.WARNING, Severity.NOTE
Matrix = tuple[Severity | None, ...]


@dataclass(frozen=True)
class Hit:
    """Ein Treffer einer Regel (ohne Regel-ID)."""

    severity: Severity
    message: str
    pointer: str = ""


@dataclass(frozen=True)
class CaseContext:
    """Ein schema-gültiger Fall plus Prüfparameter."""

    case: Mapping[str, Any]
    as_of: date
    base_dir: Path | None = None
    check_evidence_files: bool = False

    @property
    def level(self) -> int:
        return int(self.case["level"])

    @property
    def who_plans(self) -> str:
        return str(self.case["who_plans"])

    @property
    def human_role(self) -> str:
        return str(self.case["human_role"])

    def risk(self, name: str) -> bool:
        return bool(self.case["risk"][name])

    @property
    def data(self) -> Mapping[str, Any]:
        data: Mapping[str, Any] = self.case["data"]
        return data

    def data_flag(self, name: str) -> bool:
        return bool(self.data.get(name, False))

    @property
    def controls(self) -> Mapping[str, Mapping[str, Any]]:
        controls: Mapping[str, Mapping[str, Any]] = self.case["controls"]
        return controls

    def control_status(self, control_id: str) -> str | None:
        entry = self.controls.get(control_id)
        return str(entry["status"]) if entry is not None else None

    def implemented(self, control_id: str) -> bool:
        return self.control_status(control_id) == "implemented"

    @property
    def evidence(self) -> Sequence[Mapping[str, Any]]:
        items: Sequence[Mapping[str, Any]] = self.case["evidence"]
        return items

    @property
    def evidence_by_id(self) -> dict[str, Mapping[str, Any]]:
        result: dict[str, Mapping[str, Any]] = {}
        for item in self.evidence:
            result.setdefault(str(item["id"]), item)
        return result


CheckFn = Callable[[CaseContext, "Rule"], Iterable[Hit]]


@dataclass(frozen=True)
class Rule:
    """Eine Prüfregel mit Metadaten für Doku und SARIF."""

    id: str
    name: str  # Bezeichner für SARIF (CamelCase)
    title: str
    condition: str
    checks: str
    rationale: str
    references: tuple[str, ...]
    remediation: str
    matrix: Matrix
    check: CheckFn | None = field(default=None, repr=False, compare=False)

    def severity_at(self, level: int) -> Severity | None:
        return self.matrix[level]

    @property
    def default_severity(self) -> Severity:
        present = [s for s in self.matrix if s is not None]
        return max(present, key=lambda s: s.rank) if present else N


def _all(sev: Severity) -> Matrix:
    return (sev,) * len(LEVELS)


def _from(level: int, sev: Severity, below: Severity | None = None) -> Matrix:
    return tuple(sev if lv >= level else below for lv in LEVELS)


def _requirements_matrix(rule_id: str, *, exception_only: bool = False) -> Matrix:
    cells: list[Severity | None] = [None] * len(LEVELS)
    for req in LEVEL_REQUIREMENTS:
        if CONTROLS[req.control].rule_id != rule_id:
            continue
        for lv in LEVELS:
            current = cells[lv]
            if lv >= req.min_level and (current is None or req.severity.rank > current.rank):
                cells[lv] = req.severity
    if exception_only:
        for lv in LEVELS:
            if any("exception_only" in combo for combo in ALLOWED_AXES[lv]):
                cells[lv] = E
    return tuple(cells)


def _status_text(ctx: CaseContext, control_id: str) -> str:
    status = ctx.control_status(control_id)
    if status == "planned":
        return "ist erst geplant"
    if status == "not_applicable":
        return "ist als nicht anwendbar markiert"
    return "fehlt"


def _control_pointer(ctx: CaseContext, control_id: str) -> str:
    return f"/controls/{control_id}" if control_id in ctx.controls else "/controls"


def _require_control(
    ctx: CaseContext, control_id: str, severity: Severity, why: str
) -> Iterator[Hit]:
    if not ctx.implemented(control_id):
        title = CONTROLS[control_id].title
        yield Hit(
            severity,
            f"Kontrolle «{title}» ({control_id}) {_status_text(ctx, control_id)}; {why}.",
            _control_pointer(ctx, control_id),
        )


# --------------------------------------------------------------------------- GB-02
def _gb02(ctx: CaseContext, rule: Rule) -> Iterator[Hit]:
    combo = (ctx.who_plans, ctx.human_role)
    if combo in ALLOWED_AXES[ctx.level]:
        return
    allowed = ", ".join(f"{w}/{r}" for w, r in sorted(ALLOWED_AXES[ctx.level]))
    fitting = min_level_for_axes(*combo)
    hint = (
        f" Diese Kombination entspricht frühestens Grad {fitting}."
        if fitting is not None
        else " Diese Kombination ist für keinen Grad zulässig."
    )
    sev = rule.severity_at(ctx.level)
    if sev is not None:
        yield Hit(
            sev,
            f"who_plans={ctx.who_plans!r} mit human_role={ctx.human_role!r} ist für Grad "
            f"{ctx.level} nicht zulässig (zulässig: {allowed}).{hint}",
            "/human_role",
        )


# --------------------------------------------------------------------------- GB-03
def _gb03(ctx: CaseContext, rule: Rule) -> Iterator[Hit]:
    if not (
        ctx.risk("foreign_input") and ctx.risk("sensitive_data") and ctx.risk("external_action")
    ):
        return
    sev = rule.severity_at(ctx.level)
    if sev is None:  # pragma: no cover - Matrix ist vollständig
        return
    if sev is E:
        msg = (
            f"Fremde Eingaben, sensible Daten und Aussenwirkung zugleich bei Grad {ctx.level}: "
            "ohne Mensch in der Kette nicht zulässig, auch nicht mit Mandat."
        )
    else:
        msg = (
            "Fremde Eingaben, sensible Daten und Aussenwirkung zugleich: nur zulässig, weil "
            f"bei Grad {ctx.level} ein Mensch jede Wirkung freigibt. Prüfen, ob das wirklich "
            "an jedem wirksamen Punkt gilt."
        )
    yield Hit(sev, msg, "/risk")


# --------------------------------------------------------------------------- GB-04
def _gb04(ctx: CaseContext, rule: Rule) -> Iterator[Hit]:
    ceiling = ctx.case.get("ceiling")
    if not isinstance(ceiling, Mapping):
        return
    max_level = int(ceiling["max_level"])
    if ctx.level > max_level:
        sev = rule.severity_at(ctx.level) or E
        yield Hit(
            sev,
            f"Grad {ctx.level} überschreitet den Deckel {max_level} "
            f"(Grund: {ceiling['reason']}; Grundlage: {ceiling['regulation']}).",
            "/level",
        )
    else:
        yield Hit(N, f"Deckel Grad {max_level} gesetzt: {ceiling['reason']}.", "/ceiling")


# --------------------------------------------------------------------------- GB-05
def _gb05(ctx: CaseContext, rule: Rule) -> Iterator[Hit]:
    if not (ctx.risk("customer_text_in_decisions") and ctx.risk("foreign_input")):
        return
    if ctx.implemented("input_isolation"):
        yield Hit(
            N,
            "Fremde Texte fliessen ein, werden aber isoliert vorklassifiziert (input_isolation).",
            "/risk/customer_text_in_decisions",
        )
        return
    sev = rule.severity_at(ctx.level)
    if sev is not None:
        yield Hit(
            sev,
            "Freitexte von Kundinnen und Kunden fliessen ungefiltert in Entscheide ein "
            "(Einfallstor für Prompt-Injection).",
            "/risk/customer_text_in_decisions",
        )


# --------------------------------------------------------------------------- GB-06
def _gb06(ctx: CaseContext, rule: Rule) -> Iterator[Hit]:
    if not ctx.risk("safety_critical"):
        return
    sev = rule.severity_at(ctx.level)
    if sev is E:
        yield Hit(
            sev,
            f"Schutzfunktion betroffen und Grad {ctx.level}: Schutzfunktionen bleiben "
            "deterministisch und ausserhalb des Modells; höchstens Grad 3.",
            "/risk/safety_critical",
        )
    elif sev is not None:
        yield Hit(
            sev,
            "Schutzfunktion betroffen: Die KI darf beraten, aber nicht in der Sicherheitskette "
            "liegen; Grad ist auf 3 gedeckelt.",
            "/risk/safety_critical",
        )


# --------------------------------------------------------------------------- GB-07
def _gb07(ctx: CaseContext, rule: Rule) -> Iterator[Hit]:
    if ctx.human_role not in ("per_action", "per_gate"):
        return
    sev = rule.severity_at(ctx.level)
    if sev is not None:
        yield from _require_control(
            ctx,
            "adoption_rate_monitoring",
            sev,
            f"bei Freigabe durch Menschen (Grad {ctx.level}) Pflicht gegen Automation Bias",
        )


# --------------------------------------------------------------------------- GB-08
def _gb08(ctx: CaseContext, rule: Rule) -> Iterator[Hit]:
    if ctx.human_role != "mandate":
        return
    sev = rule.severity_at(ctx.level) or E
    mandate = ctx.case.get("mandate")
    if not isinstance(mandate, Mapping):
        yield Hit(sev, "human_role='mandate', aber das Objekt 'mandate' fehlt.", "/human_role")
        return
    if not mandate["limits_in_system"]:
        yield Hit(
            sev,
            "Mandat ohne Durchsetzung im Zielsystem (limits_in_system=false): Grenzen im "
            "Prompt lassen sich per Prompt-Injection umgehen.",
            "/mandate/limits_in_system",
        )


# --------------------------------------------------------------------------- GB-09
def _gb09(ctx: CaseContext, rule: Rule) -> Iterator[Hit]:
    if not ctx.risk("money_effect") or ctx.human_role not in ("mandate", "exception_only"):
        return
    sev = rule.severity_at(ctx.level) or E
    mandate = ctx.case.get("mandate")
    if not isinstance(mandate, Mapping):
        yield Hit(
            sev,
            "Geldwirkung ohne menschliche Freigabe je Aktion, aber kein Mandat mit Betragsgrenze.",
            "/risk/money_effect",
        )
        return
    if not mandate["limits_in_system"]:
        yield Hit(
            sev,
            "Geldwirkung: Die Betragsgrenze muss im Zielsystem durchgesetzt werden "
            "(limits_in_system=false).",
            "/mandate/limits_in_system",
        )
    if "money_limit" not in mandate:
        yield Hit(
            sev,
            "Geldwirkung ohne bezifferte Betragsgrenze (mandate.money_limit mit Betrag, "
            "Währung und Bezugsgrösse).",
            "/mandate",
        )


# --------------------------------------------------------------------------- GB-10
def _gb10(ctx: CaseContext, rule: Rule) -> Iterator[Hit]:
    sev = rule.severity_at(ctx.level)
    if sev is not None and ctx.risk("external_action"):
        yield Hit(
            sev,
            "Grad 1 (Assistent) hat keine Aussenwirkung: keine Sende- oder Schreibwerkzeuge.",
            "/risk/external_action",
        )


# --------------------------------------------------------------------- GB-11/12/13
def _level_requirements(rule_id: str) -> CheckFn:
    def check(ctx: CaseContext, _rule: Rule) -> Iterator[Hit]:
        for req in LEVEL_REQUIREMENTS:
            if CONTROLS[req.control].rule_id == rule_id and ctx.level >= req.min_level:
                yield from _require_control(
                    ctx, req.control, req.severity, f"ab Grad {req.min_level} Pflicht"
                )
        if rule_id == "GB-11" and ctx.human_role == "exception_only":
            for control_id in EXCEPTION_ONLY_CONTROLS:
                yield from _require_control(
                    ctx,
                    control_id,
                    E,
                    "wer nur noch Ausnahmen sieht (exception_only), braucht sie auf jedem Grad",
                )

    return check


# --------------------------------------------------------------------------- GB-14
def _gb14(ctx: CaseContext, _rule: Rule) -> Iterator[Hit]:
    measurement = ctx.case.get("measurement")
    if not isinstance(measurement, Mapping):
        if ctx.level >= 3:
            yield Hit(
                E,
                f"Grad {ctx.level} ohne Messung (pass^k oder Schattenbetrieb).",
                "/measurement" if "measurement" in ctx.case else "",
            )
        return
    method = measurement["method"]
    if method == "pass^k":
        k = measurement.get("k")
        if k is None:
            yield Hit(E, "Messmethode pass^k ohne k (Wiederholungen je Aufgabe).", "/measurement")
        elif int(k) < 2:
            yield Hit(
                W,
                "pass^k mit k=1 misst keine Konsistenz über Wiederholungen; k >= 2 wählen.",
                "/measurement/k",
            )
    elif method == "shadow" and not ctx.implemented("shadow_run"):
        yield Hit(
            W,
            "Messmethode 'shadow', aber Kontrolle shadow_run ist nicht umgesetzt.",
            "/measurement/method",
        )


# --------------------------------------------------------------------------- GB-15
def _gb15(ctx: CaseContext, _rule: Rule) -> Iterator[Hit]:
    classification = ctx.data["classification"]
    residency = ctx.data["residency"]
    if ctx.risk("sensitive_data") and classification == "frei":
        yield Hit(
            E,
            "sensible Daten, aber Datenklasse 'frei'.",
            "/data/classification",
        )
    if classification == "geheim":
        if ctx.level >= 4:
            yield Hit(
                E,
                f"Datenklasse 'geheim' bei Grad {ctx.level}: nur ohne KI-Autonomie oder höchstens "
                "Grad 3 auf eigener Infrastruktur.",
                "/data/classification",
            )
        if residency != "on_prem":
            yield Hit(
                E,
                f"Datenklasse 'geheim' mit Verarbeitungsort {residency!r}: nur 'on_prem' zulässig.",
                "/data/residency",
            )
    if classification == "vertraulich" and residency == "public":
        yield Hit(
            W,
            "Vertrauliche Daten in einer beliebigen öffentlichen Cloud: Standort, "
            "Auftragsbearbeitung und Bekanntgabe ins Ausland prüfen.",
            "/data/residency",
        )


# --------------------------------------------------------------------------- GB-16
def _effective(step: Mapping[str, Any]) -> bool:
    return any(bool(step.get(k, False)) for k in ("state_change", "external", "money"))


def _gb16(ctx: CaseContext, _rule: Rule) -> Iterator[Hit]:
    steps = ctx.case.get("steps")
    if not isinstance(steps, list):
        return
    for i, step in enumerate(steps):
        if not _effective(step):
            continue
        combo = (str(step["planned_by"]), str(step["human_role"]))
        ptr = f"/steps/{i}"
        if combo[1] == "none":
            yield Hit(
                E,
                f"Schritt {step['name']!r} hat Wirkung, aber keine menschliche Rolle "
                "(human_role='none').",
                f"{ptr}/human_role",
            )
        elif combo not in ALLOWED_AXES[ctx.level]:
            fitting = min_level_for_axes(*combo)
            yield Hit(
                E,
                f"Schritt {step['name']!r} ({combo[0]}/{combo[1]}) passt nicht zu Grad "
                f"{ctx.level}; er entspricht frühestens Grad {fitting}.",
                ptr,
            )


# --------------------------------------------------------------------------- GB-17
def _gb17(ctx: CaseContext, _rule: Rule) -> Iterator[Hit]:
    if ctx.risk("money_effect") and not ctx.risk("external_action"):
        yield Hit(
            E,
            "money_effect=true, aber external_action=false: Zahlungen, Buchungen und "
            "Bestellungen sind Aussenwirkung.",
            "/risk/external_action",
        )
    if ctx.risk("customer_facing") and not ctx.risk("external_action"):
        yield Hit(
            E,
            "customer_facing=true, aber external_action=false: Ausgaben an Kundinnen und "
            "Kunden sind Aussenwirkung.",
            "/risk/external_action",
        )
    classification = ctx.data["classification"]
    if classification in ("vertraulich", "geheim") and not ctx.risk("sensitive_data"):
        yield Hit(
            E,
            f"Datenklasse {classification!r}, aber sensitive_data=false.",
            "/risk/sensitive_data",
        )
    if ctx.data_flag("special_categories"):
        if not ctx.data_flag("personal_data"):
            yield Hit(
                E,
                "special_categories=true setzt personal_data=true voraus.",
                "/data/personal_data",
            )
        if classification not in ("vertraulich", "geheim"):
            yield Hit(
                E,
                "Besonders schützenswerte Personendaten verlangen mindestens Datenklasse "
                "'vertraulich'.",
                "/data/classification",
            )
    if ctx.data_flag("automated_individual_decisions") and not ctx.data_flag("personal_data"):
        yield Hit(
            E,
            "automated_individual_decisions=true setzt personal_data=true voraus.",
            "/data/personal_data",
        )
    if ctx.data_flag("personal_data") and classification == "frei":
        yield Hit(
            W, "Personendaten mit Datenklasse 'frei': Einstufung prüfen.", "/data/classification"
        )


# --------------------------------------------------------------------------- GB-18
def _gb18(ctx: CaseContext, _rule: Rule) -> Iterator[Hit]:
    if ctx.risk("customer_text_in_decisions") and not ctx.risk("foreign_input"):
        yield from _require_control(
            ctx,
            "input_isolation",
            E,
            "nur mit belegter Isolation fremder Texte darf foreign_input=false gesetzt werden",
        )


# --------------------------------------------------------------------------- GB-19
def _check_refs(
    ctx: CaseContext,
    refs: Sequence[str],
    allowed: Sequence[EvidenceType],
    ptr: str,
    what: str,
) -> Iterator[Hit]:
    by_id = ctx.evidence_by_id
    allowed_values = {t.value for t in allowed}
    for i, ref in enumerate(refs):
        item = by_id.get(ref)
        if item is None:
            yield Hit(
                E, f"{what}: Nachweis {ref!r} ist in 'evidence' nicht definiert.", f"{ptr}/{i}"
            )
        elif item["type"] not in allowed_values:
            yield Hit(
                E,
                f"{what}: Nachweis {ref!r} hat Typ {item['type']!r}; zulässig: "
                f"{', '.join(sorted(allowed_values))}.",
                f"{ptr}/{i}",
            )


def _gb19(ctx: CaseContext, _rule: Rule) -> Iterator[Hit]:
    seen: set[str] = set()
    for i, item in enumerate(ctx.evidence):
        if item["id"] in seen:
            yield Hit(E, f"Nachweis-ID {item['id']!r} ist doppelt vergeben.", f"/evidence/{i}/id")
        seen.add(str(item["id"]))
    referenced: set[str] = set()
    for control_id, entry in ctx.controls.items():
        ptr = f"/controls/{control_id}"
        refs = list(entry.get("evidence", []))
        referenced.update(refs)
        title = CONTROLS[control_id].title
        if entry["status"] == "implemented":
            if not refs:
                yield Hit(
                    E,
                    f"Kontrolle «{title}» ist als umgesetzt deklariert, aber ohne Nachweis.",
                    ptr,
                )
            yield from _check_refs(
                ctx, refs, CONTROLS[control_id].evidence_types, f"{ptr}/evidence", f"«{title}»"
            )
        elif entry["status"] == "not_applicable" and not entry.get("rationale"):
            yield Hit(E, f"«{title}» als nicht anwendbar markiert, aber ohne Begründung.", ptr)
    mandate = ctx.case.get("mandate")
    if isinstance(mandate, Mapping):
        refs = list(mandate["evidence"])
        referenced.update(refs)
        if mandate["limits_in_system"] and not refs:
            yield Hit(E, "Mandatsgrenzen im Zielsystem behauptet, aber ohne Nachweis.", "/mandate")
        yield from _check_refs(ctx, refs, MANDATE_EVIDENCE_TYPES, "/mandate/evidence", "Mandat")
    measurement = ctx.case.get("measurement")
    if isinstance(measurement, Mapping):
        refs = list(measurement["evidence"])
        referenced.update(refs)
        if not refs:
            yield Hit(E, "Messung deklariert, aber ohne Messbericht.", "/measurement")
        yield from _check_refs(
            ctx, refs, MEASUREMENT_EVIDENCE_TYPES, "/measurement/evidence", "Messung"
        )
    for i, item in enumerate(ctx.evidence):
        if item["id"] not in referenced:
            yield Hit(
                N, f"Nachweis {item['id']!r} wird von keiner Angabe referenziert.", f"/evidence/{i}"
            )


# --------------------------------------------------------------------------- GB-20
def _parse_date(text: str) -> date | None:
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _max_age(ctx: CaseContext, evidence_id: str) -> tuple[int, str] | None:
    """Strengste Altersgrenze aller umgesetzten Kontrollen, die den Nachweis nutzen."""
    best: tuple[int, str] | None = None
    for control_id, entry in ctx.controls.items():
        limit = CONTROLS[control_id].max_evidence_age_days
        if limit is None or entry["status"] != "implemented":
            continue
        if evidence_id in entry.get("evidence", []) and (best is None or limit < best[0]):
            best = (limit, CONTROLS[control_id].title)
    return best


def _is_local_ref(ref: str) -> bool:
    return not (ref.startswith(("https://", "urn:")))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _gb20(ctx: CaseContext, _rule: Rule) -> Iterator[Hit]:
    for i, item in enumerate(ctx.evidence):
        ptr = f"/evidence/{i}"
        day = _parse_date(str(item["date"]))
        if day is None:
            yield Hit(
                E, f"Nachweis {item['id']!r}: ungültiges Datum {item['date']!r}.", f"{ptr}/date"
            )
        elif day > ctx.as_of:
            yield Hit(
                E,
                f"Nachweis {item['id']!r} ist auf {day.isoformat()} datiert und liegt nach dem "
                f"Stichtag {ctx.as_of.isoformat()}.",
                f"{ptr}/date",
            )
        else:
            limit = _max_age(ctx, str(item["id"]))
            age = (ctx.as_of - day).days
            if limit is not None and age > limit[0]:
                yield Hit(
                    W,
                    f"Nachweis {item['id']!r} ist {age} Tage alt; für «{limit[1]}» gelten "
                    f"höchstens {limit[0]} Tage.",
                    f"{ptr}/date",
                )
        if (
            ctx.check_evidence_files
            and ctx.base_dir is not None
            and _is_local_ref(str(item["ref"]))
        ):
            yield from _check_file(ctx.base_dir, item, ptr)


def _check_file(base_dir: Path, item: Mapping[str, Any], ptr: str) -> Iterator[Hit]:
    base = base_dir.resolve()
    target = (base / str(item["ref"])).resolve()
    if not target.is_relative_to(base):
        yield Hit(
            E, f"Nachweis {item['id']!r} zeigt aus dem Fall-Verzeichnis hinaus.", f"{ptr}/ref"
        )
        return
    if not target.is_file():
        yield Hit(
            E, f"Nachweis {item['id']!r}: Datei {item['ref']!r} nicht gefunden.", f"{ptr}/ref"
        )
        return
    expected = item.get("sha256")
    if expected is not None and _sha256_file(target) != expected:
        yield Hit(
            E,
            f"Nachweis {item['id']!r}: SHA-256 der Datei weicht vom deklarierten Wert ab.",
            f"{ptr}/sha256",
        )


# --------------------------------------------------------------------------- GB-21
def _gb21(ctx: CaseContext, _rule: Rule) -> Iterator[Hit]:
    if not ctx.data_flag("automated_individual_decisions"):
        return
    status = ctx.control_status("human_review_on_request")
    if status == "not_applicable":
        return  # Ausnahme nach Art. 21 Abs. 3 – Begründung prüft GB-19
    yield from _require_control(
        ctx,
        "human_review_on_request",
        E,
        "bei automatisierten Einzelentscheiden haben Betroffene Anspruch auf Information "
        "und auf Überprüfung durch eine Person (Ausnahmen: Art. 21 Abs. 3, dann "
        "not_applicable mit Begründung)",
    )


# --------------------------------------------------------------------------- GB-22
def _gb22(ctx: CaseContext, _rule: Rule) -> Iterator[Hit]:
    regulatory = ctx.case.get("regulatory")
    if not isinstance(regulatory, Mapping) or not regulatory.get("eu_ai_act_high_risk"):
        return
    why = "für Hochrisiko-KI-Systeme verlangt der EU AI Act"
    yield from _require_control(ctx, "human_oversight", E, f"{why} menschliche Aufsicht (Art. 14)")
    yield from _require_control(
        ctx, "audit_log", E, f"{why} automatische Protokollierung (Art. 12)"
    )
    if not regulatory.get("eu_ai_act_category"):
        yield Hit(
            W, "Hochrisiko deklariert, aber ohne Fundstelle (eu_ai_act_category).", "/regulatory"
        )
    if ctx.level >= 4:
        yield Hit(
            W,
            f"Hochrisiko-System mit Grad {ctx.level}: Übersteuern und Anhalten (Art. 14 Abs. 4 "
            "lit. d und e) müssen auch ohne Freigabe je Aktion wirksam sein; prüfen, ob ein "
            "tieferer Grad genügt.",
            "/level",
        )


# ------------------------------------------------------------------------- Registry
_META = "Meta AI, «Agents Rule of Two» (31.10.2025), ai.meta.com/blog/practical-ai-agent-security"
_OWASP = "OWASP Top 10 for LLM Applications 2025, LLM06 «Excessive Agency»"
_MODEL = "GRADweight-Autonomiemodell (docs/autonomiegrade.md)"

RULES: tuple[Rule, ...] = (
    Rule(
        id="GB-01",
        name="SchemaConformance",
        title="Schema und Syntax",
        condition="immer",
        checks="Die Datei ist gültiges JSON ohne doppelte Schlüssel und erfüllt das "
        "Use-Case-Schema 2.0.",
        rationale="Nur eine eindeutige, vollständige Beschreibung lässt sich fachlich prüfen. "
        "Bei Schemafehlern werden die übrigen Regeln nicht ausgewertet.",
        references=("JSON Schema Draft 2020-12", "usecase-2.0.schema.json (dieses Repo)"),
        remediation="Fehlende Pflichtfelder ergänzen, Tippfehler in Feldnamen und Werten "
        "korrigieren.",
        matrix=_all(E),
    ),
    Rule(
        id="GB-02",
        name="AxesMatchLevel",
        title="Achsen passen zum Grad",
        condition="immer",
        checks="Die Kombination aus who_plans und human_role ist für den deklarierten Grad "
        "zulässig.",
        rationale="Der Grad folgt aus zwei Fragen: Wer plant den Weg, und wo greift der Mensch "
        "ein? Ein Grad, der nicht zu den Achsen passt, verschleiert die tatsächliche Autonomie.",
        references=(_MODEL,),
        remediation="Grad an die Achsen anpassen oder die Freigabe strenger gestalten.",
        matrix=_all(E),
        check=_gb02,
    ),
    Rule(
        id="GB-03",
        name="RuleOfTwo",
        title="Rule of Two",
        condition="fremde Eingaben, sensible Daten und Aussenwirkung zugleich",
        checks="Nicht alle drei Eigenschaften [A] fremde Eingaben, [B] sensible Daten und "
        "[C] Aussenwirkung treffen gleichzeitig zu.",
        rationale="Solange Prompt-Injection nicht zuverlässig erkannt wird, kann ein Agent mit "
        "allen drei Eigenschaften zur Datenabfluss- oder Fehlhandlungskette werden. Bis Grad 3 "
        "bricht ein Mensch die Kette; ab Grad 4 muss eine Eigenschaft strukturell wegfallen.",
        references=(_META, "CVE-2025-32711 (EchoLeak, Microsoft 365 Copilot, 2025)"),
        remediation="Eine Eigenschaft strukturell entfernen: nur vertrauenswürdige Quellen "
        "(EDI/ERP statt Freitext), fremde Texte isoliert vorklassifizieren oder ohne Aussenwirkung "
        "arbeiten.",
        matrix=_from(4, E, W),
        check=_gb03,
    ),
    Rule(
        id="GB-04",
        name="CeilingRespected",
        title="Deckel eingehalten",
        condition="falls ceiling gesetzt",
        checks="Der Grad liegt nicht über einem beschlossenen Deckel (ceiling.max_level).",
        rationale="Deckel halten fest, welche Autonomie eine Organisation für einen Anwendungsfall "
        "zulässt, etwa wegen Regulierung. Aufheben darf ihn nur das Gremium, das ihn "
        "beschlossen hat.",
        references=("EU AI Act (VO (EU) 2024/1689) Art. 6 und Anhang III, als typischer Anlass",),
        remediation="Grad senken oder den Deckel formell durch das zuständige Gremium ändern "
        "lassen.",
        matrix=_all(E),
        check=_gb04,
    ),
    Rule(
        id="GB-05",
        name="ForeignTextInDecisions",
        title="Fremde Texte in Entscheiden",
        condition="customer_text_in_decisions und foreign_input",
        checks="Fliessen fremde Freitexte in Entscheide ein, werden sie isoliert vorklassifiziert.",
        rationale="Freitext ist der Hauptkanal für Prompt-Injection. Ein Modell ohne Werkzeuge, "
        "das Text in ein festes Schema überführt, begrenzt den Schaden.",
        references=(_META, _OWASP),
        remediation="Kontrolle input_isolation umsetzen und belegen.",
        matrix=_all(W),
        check=_gb05,
    ),
    Rule(
        id="GB-06",
        name="SafetyFunctionsOutsideModel",
        title="Schutzfunktionen ausserhalb des Modells",
        condition="safety_critical",
        checks="Bei Schutzfunktionen bleibt der Grad höchstens 3.",
        rationale="Schutzfunktionen müssen deterministisch und nachweisbar bleiben. Die "
        "Maschinenverordnung führt Sicherheitsbauteile mit selbstlernendem Verhalten als Maschinen "
        "mit erhöhtem Risiko (Anhang I Teil A, Konformitätsbewertung mit Stelle).",
        references=(
            (
                "Verordnung (EU) 2023/1230 (Maschinenverordnung), in Kraft seit 19.07.2023, "
                "anwendbar ab 20.01.2027"
            ),
            "ISO/IEC TR 5469:2024 (Functional safety and AI systems)",
        ),
        remediation="Die KI berät (Wartungsvorschlag, Ticket), die Schutzfunktion bleibt "
        "klassische Sicherheitstechnik.",
        matrix=_from(4, E, W),
        check=_gb06,
    ),
    Rule(
        id="GB-07",
        name="AdoptionRateMonitored",
        title="Übernahmequote überwacht",
        condition="human_role per_action oder per_gate",
        checks="Wo Menschen KI-Vorschläge freigeben, wird die Übernahmequote gemessen.",
        rationale="Werden Vorschläge fast immer unverändert bestätigt, ist die menschliche Prüfung "
        "nur noch Durchklicken (Automation Bias).",
        references=("EU AI Act Art. 14 Abs. 4 lit. b (Automation Bias)",),
        remediation="Kontrolle adoption_rate_monitoring umsetzen (z. B. Kennzahl aus der "
        "Freigabe-Queue) und regelmässig Stichproben ziehen.",
        matrix=(None, None, E, E, None, None),
        check=_gb07,
    ),
    Rule(
        id="GB-08",
        name="MandateEnforcedInSystem",
        title="Mandat im Zielsystem durchgesetzt",
        condition="human_role mandate",
        checks="Ein Mandat existiert und seine Grenzen wirken im Zielsystem (limits_in_system).",
        rationale="Grenzen im Prompt sind Bitten an das Modell. Wirksam sind nur Grenzen, die das "
        "Zielsystem oder ein vorgeschalteter Dienst technisch erzwingt.",
        references=(_OWASP,),
        remediation="Limiten als Berechtigung, Freigabestrategie oder Gateway-Regel umsetzen und "
        "mit Konfiguration oder Test belegen.",
        matrix=(None, None, None, E, E, None),
        check=_gb08,
    ),
    Rule(
        id="GB-09",
        name="MoneyLimitDefined",
        title="Geldwirkung mit Betragsgrenze",
        condition="money_effect ohne Freigabe je Aktion (mandate, exception_only)",
        checks="Geldwirkung ohne menschliche Freigabe je Aktion hat eine bezifferte, im "
        "Zielsystem durchgesetzte Betragsgrenze.",
        rationale="Ohne Betragsgrenze ist der mögliche Schaden eines Fehlentscheids unbegrenzt.",
        references=(_OWASP,),
        remediation="mandate.money_limit (Betrag, Währung, Bezugsgrösse) setzen und im Zielsystem "
        "erzwingen.",
        matrix=(None, None, None, E, E, E),
        check=_gb09,
    ),
    Rule(
        id="GB-10",
        name="AssistantWithoutExternalEffect",
        title="Assistent ohne Aussenwirkung",
        condition="Grad 1",
        checks="Grad 1 hat keine Aussenwirkung.",
        rationale="Ein Assistent unterstützt Menschen; schreibt oder sendet er selbst, ist es "
        "mindestens ein Copilot mit Freigabe je Aktion.",
        references=(_MODEL,),
        remediation="Aussenwirkung entfernen oder Grad 2 mit Freigabe-Queue wählen.",
        matrix=(None, E, None, None, None, None),
        check=_gb10,
    ),
    Rule(
        id="GB-11",
        name="IdentityAndObservability",
        title="Identität und Beobachtbarkeit",
        condition="ab Grad 4; Ausnahme-Kontrollen bei human_role exception_only",
        checks="Ab Grad 4 sind Audit-Trail und eigene Agenten-Identität umgesetzt; wer nur "
        "Ausnahmen sieht, hat Ausnahme-Queue und Stichproben-Audit.",
        rationale="Ohne Menschen in jeder Aktion braucht es Nachvollziehbarkeit, minimale Rechte "
        "und eine feste Schwelle, ab der ein Mensch übernimmt.",
        references=("EU AI Act Art. 12 (Aufzeichnungspflichten)", _OWASP),
        remediation="Bausteine audit, exception_queue und sampling_audit einsetzen; "
        "Agenten-Konto mit minimalen Rechten einrichten und belegen.",
        matrix=_requirements_matrix("GB-11", exception_only=True),
        check=_level_requirements("GB-11"),
    ),
    Rule(
        id="GB-12",
        name="FallbackReady",
        title="Rückfallebene bereit",
        condition="ab Grad 3",
        checks="Incident-Prozess, automatische Rückstufung und ein getesteter Notaus sind "
        "umgesetzt; Wechsel von Modell, Prompt oder Werkzeug lösen eine Neubeurteilung aus.",
        rationale="Je weniger Menschen im Takt eingreifen, desto schneller muss ein Fehler "
        "technisch gestoppt und rückgängig gemacht werden können.",
        references=("EU AI Act Art. 14 Abs. 4 lit. d und e (Übersteuern, Anhalten)",),
        remediation="Notaus testen und protokollieren, Rollback-Pfad je Aktion definieren "
        "(Baustein rollback), Änderungsprozess festlegen.",
        matrix=_requirements_matrix("GB-12"),
        check=_level_requirements("GB-12"),
    ),
    Rule(
        id="GB-13",
        name="ShadowAndProposalFirst",
        title="Schattenbetrieb und Vorschlagsmodus zuerst",
        condition="ab Grad 4",
        checks="Vor dem Mandat lief der Fall im Schattenbetrieb und im Vorschlagsmodus.",
        rationale="Autonomie wird verdient, nicht eingeschaltet: Erst messen, was das System "
        "täte, dann mit Freigabe, dann mit Mandat.",
        references=(_MODEL,),
        remediation="Schattenbetrieb und Vorschlagsphase durchführen und Messberichte ablegen.",
        matrix=_requirements_matrix("GB-13"),
        check=_level_requirements("GB-13"),
    ),
    Rule(
        id="GB-14",
        name="MeasurementDefined",
        title="Messung definiert",
        condition="ab Grad 3 Pflicht; falls angegeben immer vollständig",
        checks="Ab Grad 3 ist eine Messmethode (pass^k oder Schattenbetrieb) festgelegt und "
        "vollständig (bei pass^k mit k).",
        rationale="Eine einmalig korrekte Antwort sagt wenig über Zuverlässigkeit. pass^k misst, "
        "ob eine Aufgabe in k Wiederholungen jedes Mal gelingt.",
        references=("Yao et al., «τ-bench», arXiv:2406.12045 (2024), Metrik pass^k",),
        remediation="measurement mit Methode, k (bei pass^k) und Messbericht ergänzen.",
        matrix=_all(E),
        check=_gb14,
    ),
    Rule(
        id="GB-15",
        name="DataClassAndResidency",
        title="Datenklasse und Verarbeitungsort",
        condition="immer",
        checks="Sensible Daten sind klassifiziert; 'geheim' nur auf eigener Infrastruktur und "
        "höchstens Grad 3; 'vertraulich' nicht in beliebiger öffentlicher Cloud.",
        rationale="Datenklasse und Verarbeitungsort bestimmen, welche Infrastruktur und welche "
        "Autonomie vertretbar sind.",
        references=(
            "revDSG (SR 235.1) Art. 8 (Datensicherheit) und Art. 16 (Bekanntgabe ins Ausland)",
        ),
        remediation="Datenklasse korrekt setzen; Verarbeitungsort oder Grad anpassen.",
        matrix=_all(E),
        check=_gb15,
    ),
    Rule(
        id="GB-16",
        name="StepsConsistent",
        title="Schritte passen zum Grad",
        condition="falls steps angegeben",
        checks="Jeder wirksame Schritt hat eine menschliche Rolle und eine für den Grad "
        "zulässige Achsenkombination.",
        rationale="Der Grad eines Prozesses ist der Grad seines autonomsten wirksamen Schritts. "
        "Ein einzelner Schritt mit Mandat macht aus einem Copilot einen Agenten.",
        references=(_MODEL,),
        remediation="Grad erhöhen (mit den Kontrollen des Grads) oder den Schritt strenger "
        "freigeben.",
        matrix=_all(E),
        check=_gb16,
    ),
    Rule(
        id="GB-17",
        name="RiskAttributesConsistent",
        title="Risikomerkmale widerspruchsfrei",
        condition="immer",
        checks="Risikomerkmale und Datenangaben widersprechen sich nicht (z. B. Geldwirkung ohne "
        "Aussenwirkung, vertrauliche Daten ohne sensitive_data).",
        rationale="Die Rule of Two zählt deklarierte Merkmale. Widersprüchliche Angaben würden "
        "sie aushebeln.",
        references=(_META, "revDSG Art. 5 lit. c (besonders schützenswerte Personendaten)"),
        remediation="Merkmale ehrlich setzen; die Regel zeigt das betroffene Feld.",
        matrix=_all(E),
        check=_gb17,
    ),
    Rule(
        id="GB-18",
        name="IsolationEvidenced",
        title="Belegter Strukturbruch",
        condition="customer_text_in_decisions ohne foreign_input",
        checks="Wer fremde Kundentexte verarbeitet und trotzdem foreign_input=false deklariert, "
        "belegt die isolierte Vorklassifikation.",
        rationale="foreign_input=false ist der häufigste Weg, die Rule of Two auf dem Papier zu "
        "erfüllen. Zulässig ist das nur, wenn der Entscheid nachweislich nur strukturierte Daten "
        "sieht.",
        references=(_META,),
        remediation="Kontrolle input_isolation mit Architekturbeschreibung oder Test belegen, "
        "sonst foreign_input=true setzen.",
        matrix=_all(E),
        check=_gb18,
    ),
    Rule(
        id="GB-19",
        name="EvidenceRequired",
        title="Nachweispflicht",
        condition="immer",
        checks="Jede als umgesetzt deklarierte Kontrolle, jedes Mandat und jede Messung "
        "verweist auf mindestens einen Nachweis passenden Typs; nicht anwendbare Kontrollen "
        "sind begründet.",
        rationale="Ein Häkchen ist eine Behauptung. Erst der Verweis auf Testprotokoll, "
        "Konfiguration oder Freigabe macht die Angabe prüfbar.",
        references=("ISO/IEC 42001:2023, Abschnitt 7.5 (dokumentierte Information)",),
        remediation="Nachweis in 'evidence' erfassen (Typ, Ablageort, Datum) und referenzieren.",
        matrix=_all(E),
        check=_gb19,
    ),
    Rule(
        id="GB-20",
        name="EvidenceQuality",
        title="Nachweisqualität",
        condition="immer; Dateiprüfung mit --check-evidence",
        checks="Nachweise sind gültig datiert, nicht aus der Zukunft und nicht veraltet; mit "
        "--check-evidence existieren lokale Dateien und stimmen mit dem SHA-256 überein.",
        rationale="Ein Notaus-Test von vor drei Jahren belegt den heutigen Zustand nicht. Ein "
        "Hash bindet den Fall an genau die geprüfte Fassung des Nachweises.",
        references=("ISO/IEC 42001:2023, Abschnitt 7.5 (dokumentierte Information)",),
        remediation="Test wiederholen und Nachweis aktualisieren; Hash nach Änderung neu setzen.",
        matrix=_all(E),
        check=_gb20,
    ),
    Rule(
        id="GB-21",
        name="AutomatedDecisionRights",
        title="Automatisierte Einzelentscheide (revDSG)",
        condition="automated_individual_decisions",
        checks="Bei ausschliesslich automatisierten Einzelentscheiden ist die Überprüfung durch "
        "eine Person auf Verlangen umgesetzt oder eine Ausnahme begründet.",
        rationale="Betroffene sind über automatisierte Einzelentscheide zu informieren und können "
        "eine Überprüfung durch eine natürliche Person verlangen, ausser bei den Ausnahmen nach "
        "Abs. 3 (Vertrag mit gewährtem Begehren, ausdrückliche Einwilligung).",
        references=("revDSG (SR 235.1) Art. 21, in Kraft seit 01.09.2023",),
        remediation="Prozess für Information und menschliche Überprüfung einrichten oder die "
        "Ausnahme als not_applicable mit Begründung dokumentieren.",
        matrix=_all(E),
        check=_gb21,
    ),
    Rule(
        id="GB-22",
        name="HighRiskOversight",
        title="Hochrisiko nach EU AI Act",
        condition="regulatory.eu_ai_act_high_risk",
        checks="Hochrisiko-Systeme belegen menschliche Aufsicht und Protokollierung; hohe Grade "
        "werden markiert.",
        rationale="Art. 14 verlangt, dass Menschen das System verstehen, Automation Bias erkennen, "
        "übersteuern und anhalten können; Art. 12 verlangt automatische Protokolle.",
        references=(
            "EU AI Act (VO (EU) 2024/1689) Art. 12 und Art. 14",
            "Pflichten für Anhang-III-Systeme gelten nach VO (EU) 2026/1744 ab 02.12.2027",
        ),
        remediation="Kontrollen human_oversight und audit_log umsetzen und belegen; Fundstelle "
        "der Einstufung angeben.",
        matrix=_all(E),
        check=_gb22,
    ),
)

RULES_BY_ID: dict[str, Rule] = {rule.id: rule for rule in RULES}


def level_label(level: int) -> str:
    """«Grad 4 (Agent mit Mandat)»."""
    return f"Grad {level} ({LEVEL_NAMES[level]})"
