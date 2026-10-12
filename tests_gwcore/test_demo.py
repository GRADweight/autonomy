"""Pytest: gw_core.demo — der Freigabe-Pfad muss in einem Durchlauf laufen.

Die Demo ist gleichzeitig der «Smoke-Test» für die vier Bausteine
(ApprovalQueue, AuditTrail, FreigabePolicy, pruefe_antwort) im
zusammengesetzten Zustand — was `tests_gwcore/` je einzeln prüft,
läuft hier als ein Pfad.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "examples" / "gw1-produktwissen-innendienst.json"

sys.path.insert(0, str(ROOT / "packages" / "gw_core"))

from gw_core import demo  # noqa: E402


def test_demo_case_file_exists() -> None:
    assert CASE.exists(), f"Demo-Fall fehlt: {CASE}"
    data = json.loads(CASE.read_text(encoding="utf-8"))
    assert data["id"] == "gw1-produktwissen-innendienst"
    assert data["human_role"] == "per_action"


def test_demo_run_returns_zero() -> None:
    # `run_demo` ist der einzige Seiteneffekt mit Determinismus:
    # Freigabe-Status + Prüfung-OK, sonst Exit 1.
    assert demo.run_demo(CASE) == 0


def test_demo_policy_denies_unlisted_role() -> None:
    # GB-08: die Rolle-Prüfung darf NICHT umgangen werden, nur weil
    # die Demo eine Policy übergibt — ein Test für die Enforcements-Ebene.
    from gw_core.approval import ApprovalQueue
    from gw_core.audit import AuditTrail
    from gw_core.authz import FreigabePolicy

    q = ApprovalQueue(audit=AuditTrail(), policy=FreigabePolicy(policy={"default": ["ai-lead"]}))
    aid = q.vorschlage(
        mandant="t", prototyp="t", titel="t", payload={}, vorgeschlagen_von="llm"
    )
    with pytest.raises(PermissionError):
        q.freigabe(aid, actor="outsider", rolle="outsider")
    q.schliesse()
