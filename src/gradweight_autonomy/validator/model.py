"""Fachmodell: Autonomiegrade, Achsen, Kontrollen und Nachweistypen.

Dieses Modul ist die einzige Quelle für Wertemengen und Kontroll-Anforderungen.
Regeln, Dokumentation und Tests lesen von hier.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Severity(str, Enum):
    """Schweregrad eines Befunds (gleiche Namen wie SARIF ``level``)."""

    ERROR = "error"
    WARNING = "warning"
    NOTE = "note"

    @property
    def rank(self) -> int:
        return {"error": 3, "warning": 2, "note": 1}[self.value]

    @property
    def label(self) -> str:
        return {"error": "Fehler", "warning": "Warnung", "note": "Hinweis"}[self.value]


SCHEMA_VERSION = "2.0"

LEVELS = (0, 1, 2, 3, 4, 5)
LEVEL_NAMES: dict[int, str] = {
    0: "Keine KI-Autonomie",
    1: "Assistent",
    2: "Copilot",
    3: "Workflow",
    4: "Agent mit Mandat",
    5: "Autonom mit Ausnahmesteuerung",
}

WHO_PLANS = ("human", "fixed_chain", "model")
HUMAN_ROLES = ("full_control", "per_action", "per_gate", "mandate", "exception_only")
STEP_HUMAN_ROLES = (*HUMAN_ROLES, "none")
DATA_CLASSES = ("frei", "intern", "vertraulich", "geheim")
RESIDENCIES = ("on_prem", "ch", "eu", "public")
MEASUREMENT_METHODS = ("pass^k", "shadow")
MONEY_PERIODS = ("transaction", "day", "week", "month")
CONTROL_STATUSES = ("implemented", "planned", "not_applicable")

# Grad -> erlaubte Kombinationen (wer plant, wo greift der Mensch ein).
# Strenger freigeben als der Zielgrad ist erlaubt (z. B. Modell plant, Mensch
# gibt je Aktion frei = Grad 2). Eine feste Kette ist nie Grad 4 oder 5.
ALLOWED_AXES: dict[int, frozenset[tuple[str, str]]] = {
    0: frozenset({("human", "full_control")}),
    1: frozenset({("human", "full_control"), ("human", "per_action")}),
    2: frozenset({("human", "per_action"), ("model", "per_action")}),
    3: frozenset(
        {
            ("fixed_chain", "per_gate"),
            ("model", "per_gate"),
            ("fixed_chain", "mandate"),
            ("fixed_chain", "exception_only"),
        }
    ),
    4: frozenset({("model", "mandate"), ("model", "exception_only")}),
    5: frozenset({("model", "exception_only")}),
}


def min_level_for_axes(who_plans: str, human_role: str) -> int | None:
    """Kleinster Grad, für den die Achsenkombination erlaubt ist (``None``: nie)."""
    for level in LEVELS:
        if (who_plans, human_role) in ALLOWED_AXES[level]:
            return level
    return None


class EvidenceType(str, Enum):
    """Arten von Nachweisen."""

    TEST_REPORT = "test_report"
    APPROVAL_RECORD = "approval_record"
    CONFIG = "config"
    RUNBOOK = "runbook"
    POLICY = "policy"
    MEASUREMENT = "measurement"
    LOG_EXTRACT = "log_extract"
    ARCHITECTURE = "architecture"


EVIDENCE_TYPE_LABELS: dict[EvidenceType, str] = {
    EvidenceType.TEST_REPORT: "Testprotokoll (z. B. Notaus- oder Rollback-Test)",
    EvidenceType.APPROVAL_RECORD: "Freigabe- oder Entscheidprotokoll",
    EvidenceType.CONFIG: "Konfiguration (Datei, Berechtigung, Limite im Zielsystem)",
    EvidenceType.RUNBOOK: "Betriebsanleitung / Runbook",
    EvidenceType.POLICY: "Richtlinie oder Weisung",
    EvidenceType.MEASUREMENT: "Messbericht (pass^k, Schattenbetrieb, Übernahmequote)",
    EvidenceType.LOG_EXTRACT: "Auszug aus Protokoll oder Audit-Trail",
    EvidenceType.ARCHITECTURE: "Architektur- oder Datenflussbeschreibung",
}


@dataclass(frozen=True)
class Control:
    """Eine Kontrolle, deren Umsetzung mit Nachweisen belegt werden muss."""

    id: str
    title: str
    description: str
    evidence_types: tuple[EvidenceType, ...]
    rule_id: str
    max_evidence_age_days: int | None = None


_E = EvidenceType

CONTROLS: dict[str, Control] = {
    c.id: c
    for c in (
        Control(
            "audit_log",
            "Audit-Trail",
            "Wer hat wann was vorgeschlagen, freigegeben oder ausgeführt – manipulationserkennend.",
            (_E.CONFIG, _E.LOG_EXTRACT, _E.TEST_REPORT),
            "GB-11",
        ),
        Control(
            "agent_identity",
            "Eigene Agenten-Identität mit minimalen Rechten",
            "Der Agent nutzt ein eigenes Konto, das nur die nötigen Schnittstellen erreicht.",
            (_E.CONFIG, _E.APPROVAL_RECORD),
            "GB-11",
        ),
        Control(
            "exception_queue",
            "Ausnahme-Queue",
            "Fälle über festen Schwellen gehen deterministisch an einen Menschen.",
            (_E.CONFIG, _E.TEST_REPORT, _E.RUNBOOK),
            "GB-11",
        ),
        Control(
            "sampling_audit",
            "Stichproben-Audit",
            "Regelmässige, reproduzierbare Stichprobe der autonomen Entscheide.",
            (_E.MEASUREMENT, _E.RUNBOOK, _E.LOG_EXTRACT),
            "GB-11",
            max_evidence_age_days=180,
        ),
        Control(
            "incident_process",
            "Incident-Prozess",
            "Fehlentscheide werden gemeldet, bewertet und nachverfolgt.",
            (_E.RUNBOOK, _E.POLICY),
            "GB-12",
        ),
        Control(
            "automatic_rollback",
            "Automatische Rückstufung und Rollback",
            "Bei Schwellenriss greift die Rückstufung technisch, Aktionen sind umkehrbar.",
            (_E.TEST_REPORT, _E.RUNBOOK),
            "GB-12",
            max_evidence_age_days=365,
        ),
        Control(
            "kill_switch",
            "Notaus (getestet)",
            "Ein Notaus stoppt den Betrieb in einen sicheren Zustand; der Test ist protokolliert.",
            (_E.TEST_REPORT,),
            "GB-12",
            max_evidence_age_days=365,
        ),
        Control(
            "change_management",
            "Neubeurteilung bei Modell-, Prompt- oder Toolwechsel",
            "Jeder Wechsel löst einen neuen Stufenentscheid aus.",
            (_E.POLICY, _E.APPROVAL_RECORD),
            "GB-12",
        ),
        Control(
            "shadow_run",
            "Schattenbetrieb vor Inbetriebnahme",
            "Der neue Grad lief ohne Wirkung parallel; Abweichungen sind gemessen.",
            (_E.MEASUREMENT,),
            "GB-13",
        ),
        Control(
            "proposal_mode_first",
            "Vorschlagsmodus vor Mandat",
            "Vor dem Mandat lief der Fall im Vorschlagsmodus mit menschlicher Freigabe.",
            (_E.MEASUREMENT, _E.APPROVAL_RECORD),
            "GB-13",
        ),
        Control(
            "adoption_rate_monitoring",
            "Überwachung der Übernahmequote",
            "Wie oft Menschen KI-Vorschläge unverändert übernehmen, wird gemessen.",
            (_E.MEASUREMENT, _E.CONFIG),
            "GB-07",
            max_evidence_age_days=180,
        ),
        Control(
            "input_isolation",
            "Isolierte Vorklassifikation fremder Texte",
            "Fremde Texte werden von einem Modell ohne Werkzeuge in ein festes Schema "
            "überführt; der Entscheid sieht nur strukturierte Daten.",
            (_E.ARCHITECTURE, _E.TEST_REPORT),
            "GB-18",
        ),
        Control(
            "human_oversight",
            "Menschliche Aufsicht (EU AI Act Art. 14)",
            "Aufsichtspersonen verstehen Grenzen, erkennen Automation Bias, können "
            "übersteuern und anhalten.",
            (_E.RUNBOOK, _E.POLICY, _E.TEST_REPORT),
            "GB-22",
        ),
        Control(
            "human_review_on_request",
            "Überprüfung durch eine natürliche Person auf Verlangen (revDSG Art. 21)",
            "Betroffene werden über automatisierte Einzelentscheide informiert und können "
            "eine Überprüfung durch eine Person verlangen.",
            (_E.RUNBOOK, _E.POLICY),
            "GB-21",
        ),
    )
}

MANDATE_EVIDENCE_TYPES = (_E.CONFIG, _E.TEST_REPORT)
MEASUREMENT_EVIDENCE_TYPES = (_E.MEASUREMENT, _E.TEST_REPORT)


@dataclass(frozen=True)
class LevelRequirement:
    """Eine Kontrolle ist ab einem Grad Pflicht."""

    control: str
    min_level: int
    severity: Severity


# Grad-abhängige Pflichtkontrollen (GB-11, GB-12, GB-13).
LEVEL_REQUIREMENTS: tuple[LevelRequirement, ...] = (
    LevelRequirement("audit_log", 4, Severity.ERROR),
    LevelRequirement("agent_identity", 4, Severity.ERROR),
    LevelRequirement("incident_process", 3, Severity.ERROR),
    LevelRequirement("automatic_rollback", 3, Severity.ERROR),
    LevelRequirement("kill_switch", 3, Severity.ERROR),
    LevelRequirement("change_management", 3, Severity.WARNING),
    LevelRequirement("shadow_run", 4, Severity.ERROR),
    LevelRequirement("proposal_mode_first", 4, Severity.ERROR),
)

# Wer nur noch Ausnahmen sieht, braucht die Grad-5-Leitplanken – auf jedem Grad.
EXCEPTION_ONLY_CONTROLS = ("exception_queue", "sampling_audit")
