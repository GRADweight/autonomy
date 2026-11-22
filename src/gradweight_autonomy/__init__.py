"""gradweight-autonomy: Autonomiegrade für KI in KMU-Prozessen.

Teilpakete und Module:

* :mod:`gradweight_autonomy.validator` – Policy-as-Code-Validator (GB-Regeln, SARIF)
* :mod:`gradweight_autonomy.audit` – Audit-Trail mit Hash-Kette
* :mod:`gradweight_autonomy.approval` – Freigabe-Queue (Vier-Augen-Prinzip)
* :mod:`gradweight_autonomy.authz` – Freigabe-Policy (Rolle x Anwendungsfall)
* :mod:`gradweight_autonomy.tracing` – Metadaten von Modellaufrufen
* :mod:`gradweight_autonomy.exception_queue` – Ausnahme-Queue (Grad 5)
* :mod:`gradweight_autonomy.sampling_audit` – reproduzierbare Stichproben
* :mod:`gradweight_autonomy.rollback` – Rollback-Register

Alle Module nutzen nur die Python-Standardbibliothek.
"""

__version__ = "2.0.0"

__all__ = ["__version__"]
