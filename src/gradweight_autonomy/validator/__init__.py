"""Policy-as-Code-Validator für Use-Case-Beschreibungen (Schema 2.0, Regeln GB-01 bis GB-22).

>>> from datetime import date
>>> from gradweight_autonomy.validator import validate_text
>>> report = validate_text('{"schema_version": "2.0"}', as_of=date(2026, 10, 26))
>>> report.ok, sorted(report.rule_ids())
(False, ['GB-01'])
"""

from gradweight_autonomy.validator.engine import (
    CaseReport,
    Finding,
    validate_case,
    validate_path,
    validate_text,
)
from gradweight_autonomy.validator.model import CONTROLS, LEVEL_NAMES, SCHEMA_VERSION, Severity
from gradweight_autonomy.validator.rules import RULES, RULES_BY_ID, Rule

__all__ = [
    "CONTROLS",
    "LEVEL_NAMES",
    "RULES",
    "RULES_BY_ID",
    "SCHEMA_VERSION",
    "CaseReport",
    "Finding",
    "Rule",
    "Severity",
    "validate_case",
    "validate_path",
    "validate_text",
]
