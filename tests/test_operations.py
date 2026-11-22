"""Tracing, Ausnahme-Queue, Rollback-Register und Stichproben-Audit."""

from __future__ import annotations

import json
import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from gradweight_autonomy.audit import AuditEntry, AuditTrail
from gradweight_autonomy.exception_queue import (
    ExceptionDecision,
    ExceptionPolicy,
    ExceptionQueue,
    ExceptionQueueError,
    evaluate,
)
from gradweight_autonomy.rollback import (
    MissingParameterError,
    NotReversibleError,
    RollbackAlreadyFinalError,
    RollbackError,
    RollbackManager,
    RollbackNotFoundError,
)
from gradweight_autonomy.sampling_audit import (
    STANDARD_CRITERIA,
    SamplingAudit,
    human_in_chain,
    systematic_sample,
)
from gradweight_autonomy.tracing import TraceEvent, Tracer


# ---------------------------------------------------------------- tracing
def test_trace_event_timestamp_is_per_instance() -> None:
    a = TraceEvent("K", "u", "ollama", "m", 1, 1, 1, "ok", timestamp="2026-01-01T00:00:00Z")
    b = TraceEvent("K", "u", "ollama", "m", 1, 1, 1, "ok")
    assert a.timestamp != b.timestamp


def test_trace_event_validation() -> None:
    with pytest.raises(ValueError, match="status"):
        TraceEvent("K", "u", "p", "m", 1, 1, 1, "kaputt")
    with pytest.raises(ValueError, match="negativ"):
        TraceEvent("K", "u", "p", "m", -1, 1, 1, "ok")


def test_tracer_span_records_ok_and_error() -> None:
    ticks = iter([0.0, 0.25, 1.0, 1.5])
    tracer = Tracer(monotonic=lambda: next(ticks))
    with tracer.span(tenant="K", use_case="u", provider="ollama", model="m", request="abc") as s:
        s.finish(response="hello")
    with (
        pytest.raises(RuntimeError),
        tracer.span(tenant="K", use_case="u", provider="ollama", model="m"),
    ):
        raise RuntimeError("timeout")
    rows = tracer.query()
    assert [r["status"] for r in rows] == ["error", "ok"]
    assert rows[1]["duration_ms"] == 250
    assert rows[1]["response_chars"] == 5
    assert rows[0]["error"] == "RuntimeError"
    summary = tracer.summary(tenant="K")
    assert summary == {"calls": 2, "failures": 1, "failure_rate": 0.5, "avg_duration_ms": 375}
    assert tracer.query(status="ok", tenant="K")[0]["request_chars"] == 3
    tracer.close()


def test_tracer_empty_summary(tmp_path: Path) -> None:
    tracer = Tracer(tmp_path / "t.db")
    tracer.record(TraceEvent("K", "u", "p", "m", 5, 1, 1, "refusal"))
    assert tracer.summary(tenant="anderer")["calls"] == 0
    assert tracer.summary()["failure_rate"] == 1.0


# -------------------------------------------------------- exception queue
def test_policy_is_deterministic_and_exclusive_at_limit() -> None:
    policy = ExceptionPolicy(money_limit=Decimal(2000))
    assert not evaluate(policy, amount=Decimal(2000)).requires_human
    d = evaluate(policy, amount=Decimal("2000.01"))
    assert d.requires_human
    assert d.rule_id == "GB-09"
    assert evaluate(policy, amount=Decimal("2000.01")) == d


@given(
    limit=st.decimals(min_value=0, max_value=10**6, places=2),
    amount=st.decimals(min_value=0, max_value=10**6, places=2),
)
def test_money_rule_matches_definition(limit: Decimal, amount: Decimal) -> None:
    decision = evaluate(ExceptionPolicy(money_limit=limit), amount=amount)
    assert decision.requires_human == (amount > limit)


def test_policy_sensitive_and_error_threshold() -> None:
    assert (
        evaluate(ExceptionPolicy(sensitive_requires_review=True), sensitive=True).rule_id == "GB-15"
    )
    policy = ExceptionPolicy(error_threshold=3)
    assert not evaluate(policy, error_count=3).requires_human
    assert evaluate(policy, error_count=4).rule_id == "GB-12"
    assert not evaluate(ExceptionPolicy(), amount=Decimal(10**9), sensitive=True).requires_human


def test_policy_validation() -> None:
    with pytest.raises(ValueError, match="money_limit"):
        ExceptionPolicy(money_limit=Decimal(-1))
    with pytest.raises(ValueError, match="error_threshold"):
        ExceptionPolicy(error_threshold=-1)


def test_exception_lifecycle_and_audit() -> None:
    audit = AuditTrail()
    q = ExceptionQueue(audit=audit, policy=ExceptionPolicy(money_limit=Decimal(2000)))
    assert q.policy.money_limit == Decimal(2000)
    decision = q.evaluate(amount=Decimal(2450))
    eid = q.enqueue(
        tenant="K1",
        use_case="retouren",
        title="Gutschrift",
        payload={"betrag": Decimal("2450.00")},
        decision=decision,
    )
    assert q.get(eid).payload == {"betrag": "2450.00"}
    assert [i.id for i in q.pending(tenant="K1")] == [eid]
    item = q.resolve(eid, status="resolved", actor="teamleitung", reason="Kulanz bestätigt")
    assert item.status == "resolved"
    assert item.resolved_by == "teamleitung"
    with pytest.raises(ExceptionQueueError, match="final"):
        q.resolve(eid, status="dismissed", actor="x", reason="y")
    assert [e.action for e in audit.iter_entries()] == ["exception_raised", "exception_resolved"]
    assert q.summary() == {"open": 0, "resolved": 1, "dismissed": 0, "total": 1}
    q.close()


def test_exception_queue_rejects_invalid_use() -> None:
    q = ExceptionQueue(audit=AuditTrail(), policy=ExceptionPolicy())
    with pytest.raises(ExceptionQueueError, match="requires_human"):
        q.enqueue(
            tenant="K", use_case="u", title="t", payload={}, decision=ExceptionDecision(False, "")
        )
    eid = q.enqueue(
        tenant="K", use_case="u", title="t", payload={}, decision=ExceptionDecision(True, "x")
    )
    with pytest.raises(ValueError, match="status"):
        q.resolve(eid, status="open", actor="a", reason="r")
    with pytest.raises(ValueError, match="Pflicht"):
        q.resolve(eid, status="resolved", actor="", reason="r")
    with pytest.raises(KeyError):
        q.get(99)
    assert q.summary(tenant="K")["open"] == 1


# ---------------------------------------------------------------- rollback
def _register(rb: RollbackManager, **over: object) -> int:
    params: dict[str, object] = {
        "tenant": "K1",
        "use_case": "kreditoren",
        "actor": "agent-01",
        "description": "Rechnung gebucht",
        "reversible": True,
        "after_state": {"bill_id": "64bf865d"},
        "template": {"method": "delete", "endpoint": "/4.0/purchase/bills/{bill_id}"},
        "reason": "GB-12",
    }
    params.update(over)
    return rb.register(**params)  # type: ignore[arg-type]


def test_rollback_command_is_deterministic() -> None:
    audit = AuditTrail()
    rb = RollbackManager(audit=audit)
    rid = _register(
        rb,
        template={
            "method": "PUT",
            "endpoint": "/x/{bill_id}",
            "params": {"b": "{bill_id}", "a": 1},
        },
    )
    c1, c2 = rb.command(rid), rb.command(rid)
    assert c1 == c2
    assert c1.endpoint == "/x/64bf865d"
    assert c1.params == (("a", 1), ("b", "64bf865d"))
    assert json.loads(json.dumps(c1.as_dict()))["method"] == "PUT"
    assert rb.summary()["open"] == 1


def test_rollback_execution_is_final_and_audited() -> None:
    audit = AuditTrail()
    rb = RollbackManager(audit=audit)
    rid = _register(rb)
    assert rb.command(rid).method == "DELETE"
    entry = rb.record_execution(rid, success=False, result="HTTP 409", actor="ops")
    assert entry.status == "failed"
    with pytest.raises(RollbackAlreadyFinalError):
        rb.record_execution(rid, success=True, result="ok", actor="ops")
    assert [e.action for e in audit.iter_entries()] == ["rollback_registered", "rollback_failed"]
    assert rb.pending() == []
    assert rb.summary() == {"open": 0, "executed": 0, "failed": 1, "total": 1}


def test_not_reversible_needs_reason_and_raises() -> None:
    rb = RollbackManager()
    with pytest.raises(ValueError, match="Begründung"):
        _register(rb, reversible=False, reason="")
    rid = _register(rb, reversible=False, reason="Zahlung ausgelöst", template=None)
    with pytest.raises(NotReversibleError, match="Zahlung"):
        rb.command(rid)


def test_rollback_validation_errors() -> None:
    rb = RollbackManager()
    with pytest.raises(ValueError, match=r"template\.method"):
        _register(rb, template={"endpoint": "/x"})
    with pytest.raises(ValueError, match=r"template\.method"):
        _register(rb, template={"method": "GET", "endpoint": "/x"})
    rid = _register(rb, template={"method": "DELETE", "endpoint": "/x/{fehlt}"})
    with pytest.raises(MissingParameterError, match="fehlt"):
        rb.command(rid)
    rid2 = _register(rb, template={"method": "DELETE", "endpoint": "/x", "params": ["a"]})
    with pytest.raises(RollbackError, match="params"):
        rb.command(rid2)
    with pytest.raises(RollbackNotFoundError):
        rb.get(999)
    assert len(rb.pending(tenant="K1")) == 2
    rb.close()


# ---------------------------------------------------------- sampling audit
def _trail_with(n: int) -> AuditTrail:
    audit = AuditTrail()
    for i in range(n):
        good = i % 2 == 0
        audit.append(
            tenant="K1",
            use_case="retouren",
            actor="teamleitung" if good else "ki",
            action="decision",
            details={"note": "plausibel" if good else ""},
        )
    return audit


def test_systematic_sample_is_reproducible() -> None:
    audit = _trail_with(21)
    population = list(audit.iter_entries())
    s1 = systematic_sample(population, 5)
    s2 = systematic_sample(population, 5)
    assert [e.seq for e in s1] == [e.seq for e in s2] == [1, 5, 9, 13, 17]
    assert len(systematic_sample(population, 100)) == 21
    with pytest.raises(ValueError, match="n muss"):
        systematic_sample(population, 0)


def test_sampling_report_and_audit_of_audit() -> None:
    audit = _trail_with(10)
    sampler = SamplingAudit(audit)
    report = sampler.run(n=10, actor="revision", tenant="K1")
    assert (report.sample_size, report.passed, report.pass_rate) == (10, 5, 0.5)
    assert dict(report.failures_by_criterion) == {"human_in_chain": 5, "rationale_present": 5}
    last = audit.query(action="sampling_audit")[0]
    assert last.details["report"]["pass_rate"] == 0.5
    # Frühere Audit-Läufe zählen nicht zur Grundgesamtheit.
    assert sampler.run(n=100, actor="revision").population == 10
    assert audit.verify().ok


def test_sampling_with_failing_criterion_and_empty_population() -> None:
    sampler = SamplingAudit(_trail_with(3))

    def broken(entry: AuditEntry) -> tuple[bool, str]:
        raise KeyError("x")

    report = sampler.run(n=3, actor="rev", criteria=[("broken", broken)])
    assert report.passed == 0
    assert "KeyError" in report.assessments[0].results[0][2]
    empty = sampler.run(n=3, actor="rev", tenant="niemand", actions=["decision"])
    assert empty.sample_size == 0
    assert empty.pass_rate == 0.0
    with pytest.raises(ValueError, match="Kriterium"):
        sampler.run(n=1, actor="rev", criteria=[])
    assert human_in_chain(next(iter(_trail_with(1).iter_entries())))[0]
    assert {name for name, _ in STANDARD_CRITERIA} == {"human_in_chain", "rationale_present"}


def test_context_manager_closes(tmp_path: Path) -> None:
    with AuditTrail(tmp_path / "a.db") as audit:
        audit.append(tenant="K", use_case="u", actor="a", action="x")
    with pytest.raises(sqlite3.ProgrammingError):
        audit.count()
    with Tracer() as tracer, RollbackManager() as rb:
        assert tracer.summary()["calls"] == 0
        assert rb.summary()["total"] == 0
