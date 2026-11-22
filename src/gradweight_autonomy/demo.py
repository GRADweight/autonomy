"""Durchgang Grad 2: Lieferantenrechnung vom Posteingang bis zur Buchung.

Alle Daten sind fiktiv, bexio wird simuliert (kein Netzwerk), Uhrzeit und
HMAC-Schlüssel sind fest, damit die Ausgabe reproduzierbar ist.

Schritte: Fall prüfen -> KI-Extraktion gegen den Beleg abgleichen ->
Belegprüfung -> Vorschlag in die Freigabe-Queue -> Freigabe (Rolle,
Vier-Augen) -> Buchung über den bexio-Adapter -> Rollback registrieren ->
Audit-Kette prüfen und eine Manipulation erkennen.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from gradweight_autonomy._http import HttpRequest, HttpResponse
from gradweight_autonomy.approval import ApprovalDeniedError, ApprovalQueue
from gradweight_autonomy.audit import AuditTrail, VerificationResult
from gradweight_autonomy.authz import ApprovalPolicy
from gradweight_autonomy.bexio import (
    BexioClient,
    BillLine,
    BookingLimits,
    LimitLedger,
    SupplierBill,
)
from gradweight_autonomy.invoice_checks import (
    InvoiceCheckResult,
    InvoiceFacts,
    VatLine,
    check_invoice,
)
from gradweight_autonomy.rollback import RollbackManager
from gradweight_autonomy.source_check import Source, check_numbers
from gradweight_autonomy.validator import validate_case

DEMO_KEY = bytes(range(32))  # nur für die Demo; produktiv aus einem Secret-Store laden
AS_OF = date(2026, 10, 26)
TENANT = "muster-ag"
USE_CASE = "kreditoren"

# Gleicher Fall wie examples/gw2-kreditorenrechnung.json (ein Test hält beide gleich).
DEMO_CASE: dict[str, Any] = {
    "schema_version": "2.0",
    "id": "gw2-kreditorenrechnung",
    "title": "Lieferantenrechnungen erfassen und als Buchungsvorschlag in bexio vorlegen; "
    "Buchhaltung gibt jede Buchung frei",
    "level": 2,
    "who_plans": "model",
    "human_role": "per_action",
    "owner": "Leitung Finanzen",
    "risk": {
        "foreign_input": True,
        "sensitive_data": True,
        "external_action": True,
        "money_effect": True,
        "customer_facing": False,
        "customer_text_in_decisions": False,
        "safety_critical": False,
    },
    "data": {"classification": "vertraulich", "residency": "ch", "personal_data": True},
    "steps": [
        {
            "name": "Rechnung lesen und Felder extrahieren",
            "planned_by": "fixed_chain",
            "human_role": "none",
        },
        {
            "name": "Belegprüfung (IBAN, Referenz, MWST)",
            "planned_by": "fixed_chain",
            "human_role": "none",
        },
        {
            "name": "Buchung in bexio anlegen",
            "planned_by": "model",
            "human_role": "per_action",
            "state_change": True,
            "external": True,
            "money": True,
        },
    ],
    "controls": {
        "adoption_rate_monitoring": {"status": "implemented", "evidence": ["kred-uebernahmequote"]},
        "audit_log": {"status": "implemented", "evidence": ["kred-audit-config"]},
    },
    "evidence": [
        {
            "id": "kred-uebernahmequote",
            "type": "measurement",
            "ref": "evidence/gw2-kreditorenrechnung/uebernahmequote-2026-09.md",
            "date": "2026-10-02",
            "description": "Messbericht Übernahmequote Kreditorenvorschläge September 2026",
        },
        {
            "id": "kred-audit-config",
            "type": "config",
            "ref": "evidence/gw2-kreditorenrechnung/audit-konfiguration.md",
            "date": "2026-09-10",
            "description": "Konfiguration Audit-Trail und Belegprüfung vor Buchung",
        },
    ],
}

BELEG_TEXT = (
    "Muster Lieferant AG, CHE-100.155.212 MWST\n"
    "Rechnung RE-2026-0042 vom 02.10.2026, Leistung September 2026 (Lieferdatum 30.09.2026)\n"
    "Dienstleistung September: CHF 1'000.00, MWST 8.1 %: CHF 81.00, Total CHF 1'081.00\n"
    "Zahlbar bis 01.11.2026 auf CH44 3199 9123 0008 8901 2, "
    "Referenz 21 00000 00003 13947 14300 09017"
)
KI_EXTRAKTION = (
    "Rechnung RE-2026-0042: Total CHF 1'081.00 inkl. MWST 8.1 % (CHF 81.00), "
    "fällig am 01.11.2026, IBAN CH44 3199 9123 0008 8901 2."
)


class _Clock:
    def __init__(self) -> None:
        self._t = datetime(2026, 10, 26, 9, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        self._t += timedelta(seconds=7)
        return self._t


def _simulated_bexio(request: HttpRequest) -> HttpResponse:
    """Simulierte bexio-Antwort (kein Netzwerk)."""
    payload = json.loads(request.body or b"{}")
    body = {"id": "64bf865d-988a-496d-a24f-bab2d52e4b4a", "document_no": "LR-00042", **payload}
    return HttpResponse(201, json.dumps(body).encode("utf-8"))


def _line(step: int, title: str, result: str) -> None:
    print(f"{step} · {title}")
    print(f"    {result}")


def _book_and_register_rollback(
    workdir: Path, audit: AuditTrail, clock: _Clock, action_id: int, beleg: InvoiceCheckResult
) -> str | None:
    """Schritte 6 und 7: Buchung über den Adapter, Rollback-Pfad registrieren."""
    bill = SupplierBill(
        supplier_id=1323,
        contact_partner_id=647,
        bill_date=date(2026, 10, 2),
        due_date=date(2026, 11, 1),
        currency_code="CHF",
        gross=Decimal("1081.00"),
        lines=(BillLine("Dienstleistung September", Decimal("1081.00"), 15, 16),),
        attachment_ids=("e84b9fe2-3fe2-4fcf-8c30-298fe16adb14",),
        address_name="Muster Lieferant AG",
        vendor_ref="RE-2026-0042",
    )
    limits = BookingLimits(
        Decimal("5000"), max_bills_per_day=20, max_total_per_day=Decimal("20000")
    )
    with LimitLedger(workdir / "ledger.db") as ledger:
        client = BexioClient(
            "demo-token",
            limits=limits,
            ledger=ledger,
            transport=_simulated_bexio,
            today=lambda: AS_OF,
        )
        booked = client.create_supplier_bill(bill, check=beleg)
    audit.append(
        tenant=TENANT,
        use_case=USE_CASE,
        actor="bexio-adapter",
        action="bill_created",
        details={
            "action_id": action_id,
            "bill_id": booked.bill_id,
            "document_no": booked.document_no,
        },
    )
    _line(
        6,
        "Buchung über den bexio-Adapter",
        f"POST /4.0/purchase/bills -> Beleg {booked.document_no}",
    )

    with RollbackManager(audit=audit, clock=clock) as rollback:
        entry = rollback.register(
            tenant=TENANT,
            use_case=USE_CASE,
            actor="bexio-adapter",
            description="Kreditor RE-2026-0042 angelegt",
            reversible=True,
            after_state={"bill_id": booked.bill_id},
            template={"method": "DELETE", "endpoint": "/4.0/purchase/bills/{bill_id}"},
            reason="Rollback-Pfad je wirksamer Aktion",
        )
        command = rollback.command(entry)
    _line(7, "Rollback registrieren", f"{command.method} {command.endpoint}")
    return booked.bill_id


def _tamper_and_verify(db: Path, head: tuple[int, str]) -> VerificationResult:
    """Gegenprobe: Freigebende Person direkt in der Datenbank ändern, dann prüfen."""
    conn = sqlite3.connect(db)
    conn.execute("DROP TRIGGER audit_log_no_update")
    conn.execute("UPDATE audit_log SET actor = 'p.muster' WHERE action = 'action_approved'")
    conn.commit()
    conn.close()
    with AuditTrail(db, hmac_key=DEMO_KEY) as tampered:
        broken = tampered.verify(expected_head=head)
    print(f"    Gegenprobe (freigebende Person in der Datenbank geändert): {broken.summary()}")
    return broken


def run_demo(workdir: Path) -> int:
    """Demo ausführen; Rückgabe 0, wenn alle Schritte wie erwartet verlaufen."""
    print("Demo: Lieferantenrechnung bis zur Buchung (Grad 2, fiktive Daten, bexio simuliert)\n")

    report = validate_case(DEMO_CASE, as_of=AS_OF)
    warnings = ", ".join(sorted({f.rule_id for f in report.findings}))
    _line(1, "Fall prüfen", f"{report.case_id}: {'bestanden' if report.ok else 'NICHT bestanden'} "
          f"(Hinweise/Warnungen: {warnings or 'keine'})")  # fmt: skip

    abgleich = check_numbers(KI_EXTRAKTION, [Source(BELEG_TEXT, "beleg.pdf")])
    _line(2, "KI-Extraktion gegen Beleg abgleichen", abgleich.summary())
    falsch = check_numbers(KI_EXTRAKTION.replace("1'081.00", "1'801.00"), [Source(BELEG_TEXT)])
    print(f"    Gegenprobe mit Zahlendreher: {falsch.summary()}")

    facts = InvoiceFacts(
        iban="CH44 3199 9123 0008 8901 2",
        reference="21 00000 00003 13947 14300 09017",
        supplier_uid="CHE-100.155.212 MWST",
        supply_date=date(2026, 9, 30),
        currency="CHF",
        gross=Decimal("1081.00"),
        vat_lines=(VatLine(Decimal("8.1"), Decimal("1000.00"), Decimal("81.00")),),
    )
    beleg = check_invoice(facts)
    _line(3, "Belegprüfung (IBAN, QR-Referenz, MWST, UID)", beleg.summary())

    clock = _Clock()
    db = workdir / "audit.db"
    audit = AuditTrail(db, hmac_key=DEMO_KEY, clock=clock)
    policy = ApprovalPolicy({USE_CASE: ["buchhaltung"]})
    queue = ApprovalQueue(audit=audit, policy=policy, clock=clock)
    action_id = queue.propose(
        tenant=TENANT,
        use_case=USE_CASE,
        title="Rechnung RE-2026-0042 buchen (CHF 1'081.00)",
        payload={"rechnung": "RE-2026-0042", "betrag": Decimal("1081.00"), "waehrung": "CHF"},
        proposed_by="ki",
        checks=[beleg.to_check_outcome()],
    )
    _line(
        4, "Vorschlag in die Freigabe-Queue", f"Aktion #{action_id} offen, Belegprüfung angehängt"
    )

    refusals = []
    for actor, role in (("ki", "buchhaltung"), ("p.muster", "marketing")):
        try:
            queue.approve(action_id, actor=actor, role=role)
        except ApprovalDeniedError as exc:
            refusals.append(str(exc))
    approved = queue.approve(action_id, actor="a.beispiel", role="buchhaltung", note="geprüft")
    _line(5, "Freigabe", f"abgelehnt: {refusals[0]} | {refusals[1]}")
    print(
        f"    freigegeben von {approved.decided_by} (Rolle buchhaltung): status={approved.status}"
    )

    booked_id = _book_and_register_rollback(workdir, audit, clock, action_id, beleg)

    result = audit.verify()
    head = audit.head()
    audit.close()
    queue.close()
    status = "intakt" if result.ok else "VERLETZT"
    _line(
        8,
        "Audit-Kette prüfen (HMAC-SHA-256)",
        f"Kette {status}: {result.entries_checked} Einträge, Kopf {head[0]}:{head[1][:16]}…",
    )

    broken = _tamper_and_verify(db, head)

    ok = (
        report.ok
        and abgleich.passed
        and not falsch.passed
        and beleg.passed
        and len(refusals) == 2
        and booked_id is not None
        and result.ok
        and not broken.ok
    )
    print("\nDemo " + ("erfolgreich." if ok else "mit unerwartetem Ergebnis beendet."))
    return 0 if ok else 1


def main() -> int:
    """Einstiegspunkt für ``gw-autonomy demo``."""
    with tempfile.TemporaryDirectory(prefix="gw-autonomy-demo-") as tmp:
        return run_demo(Path(tmp))
