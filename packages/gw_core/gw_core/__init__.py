"""gw_core — GRADweight Governance-Bausteine (Subset).

Ausgewaehlte, getestete Bausteine aus dem gemeinsamen Kern:
- audit:     Audit-Trail (append-only, wer/was/wann, CSV-Export)
- approval:  Approval-Queue (Freigabe/Anpassen/Zurueckstellen)
- authz:     Freigabe-Policy (Rolle x Kontext, Least Privilege)
- tracing:   LLM-Request-Trace (Identitaet & Beobachtbarkeit)
- verify:    Zweitmodell-Pruefung (Antwort gegen Fundstellen, VETO)
- bexio:     Zielsystem-Adapter (systemseitige Limiten, Dry-Run)

Nicht enthalten (eigene Projekte mit eigenen Abhaengigkeiten):
config, llm, chunking, documents, embeddings, vectorstore.
"""

from gw_core.approval import Aktion, ApprovalQueue
from gw_core.audit import AuditTrail
from gw_core.authz import FreigabeEntscheid, FreigabePolicy
from gw_core.bexio import BexioFehler, BexioZielFehler, BexioZielsystemAdapter
from gw_core.exception_queue import (
    Ausnahme,
    ExceptionEntscheid,
    ExceptionPolicy,
    ExceptionQueue,
)
from gw_core.sampling_audit import (
    AuditBericht,
    SamplingAudit,
    STANDARD_KRITERIEN,
)
from gw_core.tracing import TraceEvent, Tracer, TracingKontext
from gw_core.verify import Befund, Zitat, pruefe_antwort

__all__ = [
    "Aktion", "ApprovalQueue",
    "AuditBericht", "AuditTrail",
    "Ausnahme",
    "Befund", "Zitat", "pruefe_antwort",
    "BexioFehler", "BexioZielFehler", "BexioZielsystemAdapter",
    "ExceptionEntscheid", "ExceptionPolicy", "ExceptionQueue",
    "FreigabeEntscheid", "FreigabePolicy",
    "SamplingAudit", "STANDARD_KRITERIEN",
    "Tracer", "TracingKontext", "TraceEvent",
]
