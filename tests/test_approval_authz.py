"""Freigabe-Queue und Freigabe-Policy (fail-closed)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gradweight_autonomy.approval import (
    ActionAlreadyDecidedError,
    ActionNotFoundError,
    ApprovalDeniedError,
    ApprovalQueue,
    CheckOutcome,
)
from gradweight_autonomy.audit import AuditTrail
from gradweight_autonomy.authz import ApprovalPolicy, PolicyError

POLICY = ApprovalPolicy(
    {"kreditoren": ["buchhaltung", "cfo"], "bewerbungen": ["hr-leitung"], "*": ["revision"]}
)


def _queue() -> tuple[ApprovalQueue, AuditTrail]:
    audit = AuditTrail()
    return ApprovalQueue(audit=audit, policy=POLICY), audit


def _actions(audit: AuditTrail) -> list[str]:
    return [e.action for e in audit.iter_entries()]


# ---------------------------------------------------------------- policy
def test_policy_permits_listed_and_wildcard_roles() -> None:
    assert POLICY.check(role="buchhaltung", use_case="kreditoren").allowed
    assert POLICY.check(role="revision", use_case="bewerbungen").allowed
    denied = POLICY.check(role="marketing", use_case="kreditoren")
    assert not denied.allowed
    assert "buchhaltung, cfo, revision" in denied.reason


def test_policy_denies_unknown_use_case_without_default() -> None:
    policy = ApprovalPolicy({"kreditoren": ["cfo"]})
    assert not policy.check(role="cfo", use_case="unbekannt").allowed
    assert "keine" in policy.check(role="cfo", use_case="unbekannt").reason


def test_policy_default_entry_applies() -> None:
    policy = ApprovalPolicy({"default": ["teamleitung"]})
    assert policy.check(role="teamleitung", use_case="irgendwas").allowed


def test_policy_has_no_implicit_superuser() -> None:
    assert not POLICY.check(role="admin", use_case="kreditoren").allowed


def test_policy_empty_role_denied() -> None:
    assert not POLICY.check(role="", use_case="kreditoren").allowed


@pytest.mark.parametrize(
    "text",
    ["[]", "{", '{"a": "cfo"}', '{"a": [""]}', '{"": ["x"]}', '{"a": 3}'],
)
def test_policy_rejects_invalid_definitions(text: str) -> None:
    with pytest.raises(PolicyError):
        ApprovalPolicy.from_json(text)


def test_policy_constructor_rejects_non_mapping() -> None:
    with pytest.raises(PolicyError):
        ApprovalPolicy(["cfo"])  # type: ignore[arg-type]


def test_policy_from_env_and_file(tmp_path: Path) -> None:
    f = tmp_path / "policy.json"
    f.write_text(json.dumps({"kreditoren": ["cfo"]}), encoding="utf-8")
    assert (
        ApprovalPolicy.from_env({"GW_APPROVAL_POLICY_FILE": str(f)})
        .check(role="cfo", use_case="kreditoren")
        .allowed
    )
    assert (
        ApprovalPolicy.from_env({"GW_APPROVAL_POLICY": '{"x": ["y"]}'})
        .check(role="y", use_case="x")
        .allowed
    )
    empty = ApprovalPolicy.from_env({})
    assert not empty.check(role="cfo", use_case="kreditoren").allowed


def test_policy_missing_file_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(PolicyError, match="nicht lesbar"):
        ApprovalPolicy.from_env({"GW_APPROVAL_POLICY_FILE": str(tmp_path / "fehlt.json")})


# ----------------------------------------------------------------- queue
def test_propose_then_approve_writes_audit_chain() -> None:
    q, audit = _queue()
    aid = q.propose(tenant="K1", use_case="kreditoren", title="Rechnung buchen", payload={"x": 1})
    action = q.approve(aid, actor="m.muster", role="buchhaltung", note="geprüft")
    assert action.status == "approved"
    assert action.decided_by == "m.muster"
    assert _actions(audit) == ["action_proposed", "action_approved"]
    assert audit.verify().ok


def test_role_not_in_policy_is_refused_and_audited() -> None:
    q, audit = _queue()
    aid = q.propose(tenant="K1", use_case="kreditoren", title="t", payload={})
    with pytest.raises(ApprovalDeniedError, match="nicht freigeben"):
        q.approve(aid, actor="m.muster", role="marketing")
    assert _actions(audit)[-1] == "decision_refused"
    assert q.get(aid).status == "open"


def test_four_eyes_principle() -> None:
    q, _ = _queue()
    aid = q.propose(
        tenant="K1", use_case="kreditoren", title="t", payload={}, proposed_by="m.muster"
    )
    with pytest.raises(ApprovalDeniedError, match="Vier-Augen"):
        q.approve(aid, actor="m.muster", role="buchhaltung")


def test_approver_must_be() -> None:
    q, _ = _queue()
    aid = q.propose(
        tenant="K1", use_case="kreditoren", title="t", payload={}, approver_must_be="cfo.person"
    )
    with pytest.raises(ApprovalDeniedError, match="Nur"):
        q.approve(aid, actor="andere", role="cfo")
    assert q.approve(aid, actor="cfo.person", role="cfo").status == "approved"


def test_decisions_are_final() -> None:
    q, _ = _queue()
    aid = q.propose(tenant="K1", use_case="kreditoren", title="t", payload={})
    q.reject(aid, actor="m.muster", reason="Betrag falsch")
    with pytest.raises(ActionAlreadyDecidedError):
        q.approve(aid, actor="m.muster", role="buchhaltung")
    with pytest.raises(ActionAlreadyDecidedError):
        q.reject(aid, actor="m.muster", reason="nochmals")


def test_failed_blocking_check_prevents_approval() -> None:
    q, audit = _queue()
    aid = q.propose(
        tenant="K1",
        use_case="kreditoren",
        title="t",
        payload={},
        checks=[
            CheckOutcome("belegpruefung", passed=False, detail="IBAN ungültig"),
            CheckOutcome("info", passed=False, blocking=False),
        ],
    )
    assert not q.get(aid).checks_passed
    with pytest.raises(ApprovalDeniedError, match="belegpruefung"):
        q.approve(aid, actor="m.muster", role="buchhaltung")
    proposed = audit.query(action="action_proposed")[0].details
    assert proposed["checks"][0]["detail"] == "IBAN ungültig"


def test_non_blocking_failed_check_does_not_block() -> None:
    q, _ = _queue()
    aid = q.propose(
        tenant="K1",
        use_case="kreditoren",
        title="t",
        payload={},
        checks=[CheckOutcome("hinweis", passed=False, blocking=False)],
    )
    assert q.approve(aid, actor="x", role="cfo").status == "approved"


def test_amend_requires_passing_checks_for_new_payload() -> None:
    q, _ = _queue()
    aid = q.propose(tenant="K1", use_case="kreditoren", title="t", payload={"betrag": "100"})
    with pytest.raises(ApprovalDeniedError):
        q.amend(
            aid,
            actor="x",
            role="cfo",
            new_payload={"betrag": "90"},
            checks=[CheckOutcome("belegpruefung", passed=False)],
        )
    action = q.amend(
        aid,
        actor="x",
        role="cfo",
        new_payload={"betrag": "90"},
        checks=[CheckOutcome("belegpruefung", passed=True)],
        note="Skonto",
    )
    assert action.status == "amended"
    assert action.payload == {"betrag": "90"}
    assert action.checks[0].passed


def test_reject_needs_reason_and_actor() -> None:
    q, _ = _queue()
    aid = q.propose(tenant="K1", use_case="kreditoren", title="t", payload={})
    with pytest.raises(ValueError, match="Begründung"):
        q.reject(aid, actor="x", reason="")
    with pytest.raises(ValueError, match="actor"):
        q.reject(aid, actor="", reason="r")
    with pytest.raises(ValueError, match="actor"):
        q.approve(aid, actor="", role="cfo")


def test_unknown_action_and_empty_title() -> None:
    q, _ = _queue()
    with pytest.raises(ActionNotFoundError):
        q.get(42)
    with pytest.raises(ValueError, match="title"):
        q.propose(tenant="K", use_case="u", title="", payload={})


def test_pending_and_summary() -> None:
    q, _ = _queue()
    a1 = q.propose(tenant="K", use_case="kreditoren", title="a", payload={})
    a2 = q.propose(tenant="K", use_case="kreditoren", title="b", payload={})
    a3 = q.propose(tenant="K", use_case="kreditoren", title="c", payload={})
    q.propose(tenant="other", use_case="kreditoren", title="d", payload={})
    q.approve(a1, actor="x", role="cfo")
    q.reject(a2, actor="x", reason="nein")
    assert [a.id for a in q.pending(tenant="K")] == [a3]
    assert len(q.pending()) == 2
    s = q.summary(tenant="K")
    assert (s.open, s.approved, s.rejected, s.total) == (1, 1, 1, 3)
    assert s.human_override_rate == 0.5
    q.close()


def test_override_rate_empty() -> None:
    q, _ = _queue()
    assert q.summary().human_override_rate == 0.0


def test_file_backed_queue_persists(tmp_path: Path) -> None:
    db = tmp_path / "q.db"
    audit = AuditTrail()
    q = ApprovalQueue(db, audit=audit, policy=POLICY)
    aid = q.propose(tenant="K", use_case="kreditoren", title="a", payload={"n": 1})
    q.close()
    again = ApprovalQueue(db, audit=audit, policy=POLICY)
    assert again.get(aid).payload == {"n": 1}
