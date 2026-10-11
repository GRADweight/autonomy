"""Case-Schema für gradBuild.

Ein Use Case wird als flaches JSON-Objekt beschrieben (siehe docs/schema.md /
README, Abschnitt "Schema"). Diese Module enthält die konstanten Wertemengen
und die Basis-Schemaprüfung (GB-01).
"""
from __future__ import annotations

DATA_CLASSES = ("frei", "intern", "vertraulich", "geheim")
RESIDENCIES = ("public", "ch", "eu", "on_prem")

# Wer bestimmt den Weg (Achse 1)?
WHO_PLANS = ("human", "fixed_chain", "model")

# Wo greift der Mensch ein (Achse 2)?
HUMAN_ROLES = ("full_control", "per_action", "per_gate", "mandate", "exception_only")

# Grad -> erlaubte Kombinationen (Achse 1, Achse 2).
#
#   Achse 1 — Wer bestimmt den Weg?   human | fixed_chain | model
#   Achse 2 — Wo greift der Mensch ein? full_control | per_action | per_gate |
#                                        mandate | exception_only
#
# Grundregeln (README «Regeln»):
#  * Grad = autonomster WEG mit Wirkung (Recherche ohne Wirkung zählt nicht).
#  * Zielarchitektur bauen, Freigabe strenger stellen: ein Agent (model) darf
#    in Vorschlags-/Gate-Modus laufen, solange die Freigabe strenger ist —
#    deshalb ist (model, per_action) bei Grad 2 und (model, per_gate) bei
#    Grad 3 erlaubt (Übergangs-Phasen).
#  * Der Grad folgt dem Weg: eine fixed_chain ist nie Grad 4/5; «Dunkel-
#    Varianten» (Kette ohne Gates) bleiben beim Grad der Kette mit
#    erweiterten Leitplanken der Zielstufe (GB-12/GB-13).
ALLOWED_AXES = {
    0: {("human", "full_control")},
    1: {("human", "full_control"), ("human", "per_action")},  # jeder ausgeführte Schritt wird vom Menschen aufgerufen/angezeigt
    2: {("human", "per_action"), ("model", "per_action")},
    3: {
        ("fixed_chain", "per_gate"),
        ("model", "per_gate"),          # Agent im Gate-Modus (strenger als Mandat)
        ("fixed_chain", "mandate"),     # Dunkel-Variante: Kette + erweiterte Leitplanken
        ("fixed_chain", "exception_only"),
    },
    4: {("model", "mandate"), ("model", "exception_only")},
    5: {("model", "exception_only")},
}

REQUIRED_TOP_KEYS = (
    "id",
    "title",
    "level",
    "who_plans",
    "human_role",
    "foreign_input",
    "sensitive_data",
    "external_action",
    "money_effect",
    "customer_facing",
    "customer_text_in_decisions",
    "safety_critical",
    "data_class",
    "governance",
)

REQUIRED_GOVERNANCE_KEYS = (
    "owner",
    "audit_log",
    "incident_log",
    "automatic_rollback",
    "kill_switch_tested",
    "agent_identity_min_privilege",
    "adoption_rate_monitored",
    "exception_queue",
    "sampling_audit",
    "decides_new_on_model_prompt_tool_change",
    "shadow_run_first",
    "proposal_mode_first",
)

BOOL_KEYS = (
    "foreign_input",
    "sensitive_data",
    "external_action",
    "money_effect",
    "customer_facing",
    "customer_text_in_decisions",
    "safety_critical",
)


def schema_errors(case: dict) -> list[str]:
    """GB-01: Strukturprüfung. Gibt eine Liste von Fehlertexten zurück."""
    errs: list[str] = []
    for key in REQUIRED_TOP_KEYS:
        if key not in case:
            errs.append(f"fehlendes Feld '{key}'")

    level = case.get("level")
    if not isinstance(level, int) or isinstance(level, bool) or not 0 <= level <= 5:
        errs.append("'level' muss eine ganze Zahl zwischen 0 und 5 sein")

    who_plans = case.get("who_plans")
    if who_plans is not None and who_plans not in WHO_PLANS:
        errs.append(f"'who_plans' muss eine von {WHO_PLANS} sein")

    human_role = case.get("human_role")
    if human_role is not None and human_role not in HUMAN_ROLES:
        errs.append(f"'human_role' muss eine von {HUMAN_ROLES} sein")

    for key in BOOL_KEYS:
        if key in case and not isinstance(case[key], bool):
            errs.append(f"'{key}' muss true/false sein")

    data_class = case.get("data_class")
    if data_class is not None and data_class not in DATA_CLASSES:
        errs.append(f"'data_class' muss eine von {DATA_CLASSES} sein")

    residency = case.get("data_residency")
    if residency is not None and residency not in RESIDENCIES:
        errs.append(f"'data_residency' muss eine von {RESIDENCIES} sein")

    governance = case.get("governance")
    if isinstance(governance, dict):
        for key in REQUIRED_GOVERNANCE_KEYS:
            if key not in governance:
                errs.append(f"governance: fehlendes Feld '{key}'")
        for key in REQUIRED_GOVERNANCE_KEYS:
            if key in governance and key != "owner" and not isinstance(governance[key], bool):
                errs.append(f"governance['{key}'] muss true/false sein")
        owner = governance.get("owner")
        if owner is not None and not isinstance(owner, str):
            errs.append("governance['owner'] muss ein String sein")
    elif governance is not None:
        errs.append("'governance' muss ein Objekt sein")

    mandate = case.get("mandate")
    if mandate is not None:
        if not isinstance(mandate, dict):
            errs.append("'mandate' muss ein Objekt sein")
        else:
            if not isinstance(mandate.get("limits_in_system", False), bool):
                errs.append("mandate['limits_in_system'] muss true/false sein")

    ceiling = case.get("ceiling")
    if ceiling is not None:
        if not isinstance(ceiling, dict):
            errs.append("'ceiling' muss ein Objekt sein")
        else:
            if not isinstance(ceiling.get("max_level"), int):
                errs.append("ceiling['max_level'] muss eine ganze Zahl sein")
            if not ceiling.get("reason"):
                errs.append("ceiling['reason'] fehlt (Grund des Deckels)")
            if not ceiling.get("regulation"):
                errs.append("ceiling['regulation'] fehlt (Rechtsgrundlage)")

    measurement = case.get("measurement")
    if measurement is not None:
        if not isinstance(measurement, dict):
            errs.append("'measurement' muss ein Objekt sein")
        else:
            if not isinstance(measurement.get("method"), str):
                errs.append("measurement['method'] muss ein String sein")
            steps = case.get("steps")
            if steps is not None and not isinstance(steps, list):
                errs.append("'steps' muss eine Liste sein")
    return errs
