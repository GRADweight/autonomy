"""gradBuild — Autonomiegrade für KI in KMU-Prozessen: Modell, Regeln, Validator.

Ein Python-Paket ohne externe Abhängigkeiten (Python 3.9+).
"""

__version__ = "0.1.0"

from . import schema  # noqa: F401
from .validate import CaseReport, Finding, evaluate_case, evaluate_paths  # noqa: F401

# Backwards-/Ergonomie-Aliases
validate_case = evaluate_case
