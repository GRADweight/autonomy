"""Freigabe-Policy: welche Rolle darf für welchen Anwendungsfall freigeben.

Format (JSON-Objekt, Anwendungsfall -> Liste erlaubter Rollen)::

    {
      "kreditoren": ["buchhaltung", "cfo"],
      "bewerbungen": ["hr-leitung"],
      "*": ["revision"],
      "default": []
    }

* ``"*"``: Rollen, die für **alle** Anwendungsfälle freigeben dürfen. Es gibt
  keine eingebaute Superuser-Rolle; wer eine braucht, trägt sie hier sichtbar ein.
* ``"default"``: gilt für Anwendungsfälle ohne eigenen Eintrag. Fehlt er, darf
  für nicht aufgeführte Anwendungsfälle niemand freigeben (fail-closed).

Die Policy prüft nur die *Rolle*. Wer eine Rolle tragen darf (Authentisierung),
entscheidet das umgebende System (IdP, Gateway).
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ENV_POLICY = "GW_APPROVAL_POLICY"
ENV_POLICY_FILE = "GW_APPROVAL_POLICY_FILE"
WILDCARD = "*"
DEFAULT = "default"


class PolicyError(ValueError):
    """Policy fehlt, ist unlesbar oder hat ein ungültiges Format."""


@dataclass(frozen=True)
class AuthzDecision:
    """Ergebnis einer Rollenprüfung."""

    allowed: bool
    use_case: str
    role: str
    permitted_roles: tuple[str, ...]
    reason: str


class ApprovalPolicy:
    """Rollen x Anwendungsfall; deny by default."""

    def __init__(self, rules: Mapping[str, Sequence[str]]) -> None:
        if not isinstance(rules, Mapping):
            raise PolicyError("Policy muss ein JSON-Objekt sein")
        parsed: dict[str, tuple[str, ...]] = {}
        for use_case, roles in rules.items():
            if not isinstance(use_case, str) or not use_case:
                raise PolicyError("Policy-Schlüssel müssen nicht-leere Strings sein")
            if isinstance(roles, str) or not isinstance(roles, Sequence):
                raise PolicyError(f"Policy-Eintrag {use_case!r} muss eine Liste von Rollen sein")
            cleaned = tuple(dict.fromkeys(str(r) for r in roles))
            if any(not r for r in cleaned):
                raise PolicyError(f"Policy-Eintrag {use_case!r} enthält eine leere Rolle")
            parsed[use_case] = cleaned
        self._rules = parsed

    @classmethod
    def from_json(cls, text: str) -> ApprovalPolicy:
        """Policy aus einem JSON-Text laden."""
        try:
            data: Any = json.loads(text)
        except json.JSONDecodeError as exc:
            raise PolicyError(f"Policy ist kein gültiges JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise PolicyError("Policy muss ein JSON-Objekt sein")
        return cls(data)

    @classmethod
    def from_file(cls, path: str | Path) -> ApprovalPolicy:
        """Policy aus einer Datei laden; eine fehlende Datei ist ein Fehler."""
        p = Path(path)
        try:
            text = p.read_text(encoding="utf-8")
        except OSError as exc:
            raise PolicyError(f"Policy-Datei nicht lesbar: {p} ({exc})") from exc
        return cls.from_json(text)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> ApprovalPolicy:
        """Policy aus ``GW_APPROVAL_POLICY`` (JSON) oder ``GW_APPROVAL_POLICY_FILE``.

        Ist nichts gesetzt, entsteht eine leere Policy: niemand darf freigeben.
        """
        source = os.environ if env is None else env
        if source.get(ENV_POLICY):
            return cls.from_json(source[ENV_POLICY])
        if source.get(ENV_POLICY_FILE):
            return cls.from_file(source[ENV_POLICY_FILE])
        return cls({})

    def permitted_roles(self, use_case: str) -> tuple[str, ...]:
        """Erlaubte Rollen für einen Anwendungsfall (inkl. ``"*"``)."""
        specific = self._rules.get(use_case, self._rules.get(DEFAULT, ()))
        return tuple(dict.fromkeys((*specific, *self._rules.get(WILDCARD, ()))))

    def check(self, *, role: str, use_case: str) -> AuthzDecision:
        """Prüfen, ob ``role`` für ``use_case`` freigeben darf."""
        permitted = self.permitted_roles(use_case)
        if role and role in permitted:
            return AuthzDecision(
                True, use_case, role, permitted, f"Rolle {role!r} darf {use_case!r} freigeben."
            )
        shown = ", ".join(permitted) if permitted else "keine"
        return AuthzDecision(
            False,
            use_case,
            role,
            permitted,
            f"Rolle {role!r} darf {use_case!r} nicht freigeben (erlaubt: {shown}).",
        )
