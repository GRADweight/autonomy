"""bexio-Adapter: Vorprüfung, Limiten, Nutzlast, Fehlerpfade (ohne Netzwerk)."""

from __future__ import annotations

import json
import threading
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from gradweight_autonomy._http import HttpRequest, HttpResponse, TransportError
from gradweight_autonomy.bexio import (
    BexioClient,
    BexioError,
    BillLine,
    BookingLimits,
    LimitExceededError,
    LimitLedger,
    OutcomeUnknownError,
    PrecheckFailedError,
    SupplierBill,
)
from gradweight_autonomy.invoice_checks import InvoiceFacts, VatLine, check_invoice

TODAY = date(2026, 10, 26)
LIMITS = BookingLimits(
    max_amount=Decimal("5000"), max_bills_per_day=3, max_total_per_day=Decimal("8000")
)


def facts(gross: str = "1081.00") -> InvoiceFacts:
    g = Decimal(gross)
    net = (g / Decimal("1.081")).quantize(Decimal("0.01"))
    return InvoiceFacts(
        iban="CH44 3199 9123 0008 8901 2",
        reference="21 00000 00003 13947 14300 09017",
        supplier_uid="CHE-100.155.212 MWST",
        supply_date=date(2026, 10, 1),
        currency="CHF",
        gross=g,
        vat_lines=(VatLine(Decimal("8.1"), net, g - net),),
    )


def bill(gross: str = "1081.00", **over: object) -> SupplierBill:
    params: dict[str, object] = {
        "supplier_id": 1323,
        "contact_partner_id": 647,
        "bill_date": date(2026, 10, 2),
        "due_date": date(2026, 11, 1),
        "currency_code": "CHF",
        "gross": Decimal(gross),
        "lines": (
            BillLine("Dienstleistung Oktober", Decimal(gross), tax_id=15, booking_account_id=16),
        ),
        "attachment_ids": ("e84b9fe2-3fe2-4fcf-8c30-298fe16adb14",),
        "address_name": "Muster Lieferant AG",
        "vendor_ref": "RE-2026-0042",
        "title": "Rechnung RE-2026-0042",
    }
    params.update(over)
    return SupplierBill(**params)  # type: ignore[arg-type]


class Fake:
    def __init__(self, *responses: HttpResponse | Exception) -> None:
        self.responses = list(responses)
        self.requests: list[HttpRequest] = []

    def __call__(self, request: HttpRequest) -> HttpResponse:
        self.requests.append(request)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def created(bill_id: str = "64bf865d-988a-496d-a24f-bab2d52e4b4a") -> HttpResponse:
    return HttpResponse(201, json.dumps({"id": bill_id, "document_no": "LR-12345"}).encode())


def client(fake: Fake, ledger: LimitLedger | None = None, **kw: object) -> BexioClient:
    return BexioClient(
        "pat-test",
        limits=LIMITS,
        ledger=ledger or LimitLedger(),
        transport=fake,
        today=lambda: TODAY,
        **kw,  # type: ignore[arg-type]
    )


# ------------------------------------------------------------------ Erfolg
def test_successful_booking_sends_v4_payload() -> None:
    fake = Fake(created())
    ledger = LimitLedger()
    result = client(fake, ledger).create_supplier_bill(bill(), check=check_invoice(facts()))
    assert (result.bill_id, result.document_no, result.dry_run) == (
        "64bf865d-988a-496d-a24f-bab2d52e4b4a",
        "LR-12345",
        False,
    )
    req = fake.requests[0]
    assert req.method == "POST"
    assert req.url == "https://api.bexio.com/4.0/purchase/bills"
    assert req.headers["Authorization"] == "Bearer pat-test"
    payload = json.loads(req.body or b"")
    assert payload["manual_amount"] is True
    assert payload["amount_man"] == 1081.0
    assert payload["line_items"][0] == {
        "position": 0,
        "title": "Dienstleistung Oktober",
        "amount": 1081.0,
        "tax_id": 15,
        "booking_account_id": 16,
    }
    assert payload["address"] == {"lastname_company": "Muster Lieferant AG", "type": "COMPANY"}
    assert payload["attachment_ids"]
    assert payload["discounts"] == []
    assert result.reservation_id is not None
    assert ledger.status(result.reservation_id) == "confirmed"
    assert ledger.usage(TODAY, "CHF") == (1, Decimal("1081.00"))


def test_dry_run_sends_nothing_and_reserves_nothing() -> None:
    fake = Fake()
    ledger = LimitLedger()
    c = BexioClient("", limits=LIMITS, ledger=ledger, transport=fake, dry_run=True)
    result = c.create_supplier_bill(bill(), check=check_invoice(facts()))
    assert result.dry_run
    assert result.payload["vendor_ref"] == "RE-2026-0042"
    assert fake.requests == []
    assert ledger.usage(date.today(), "CHF") == (0, Decimal(0))  # noqa: DTZ011


def test_token_not_in_repr_and_required() -> None:
    assert "pat-test" not in repr(client(Fake()))
    with pytest.raises(ValueError, match="token"):
        BexioClient("", limits=LIMITS, ledger=LimitLedger())


# ------------------------------------------------------------- Vorprüfung
def test_failed_precheck_blocks_before_any_call() -> None:
    fake = Fake()
    bad = check_invoice(facts().__class__(**{**facts().__dict__, "reference": None}))
    with pytest.raises(PrecheckFailedError, match="QR-IBAN verlangt"):
        client(fake).create_supplier_bill(bill(), check=bad)
    assert fake.requests == []


def test_check_must_match_bill() -> None:
    with pytest.raises(PrecheckFailedError, match="geprüften Beleg"):
        client(Fake()).create_supplier_bill(bill("1081.00"), check=check_invoice(facts("2162.00")))


# ----------------------------------------------------------------- Limiten
def test_amount_and_currency_limits() -> None:
    with pytest.raises(LimitExceededError, match="über Limite"):
        client(Fake()).create_supplier_bill(bill("5405.00"), check=check_invoice(facts("5405.00")))
    eur = bill(currency_code="EUR")
    eur_facts = facts().__class__(**{**facts().__dict__, "currency": "EUR"})
    with pytest.raises(LimitExceededError, match="nicht freigegeben"):
        client(Fake()).create_supplier_bill(eur, check=check_invoice(eur_facts))


def test_daily_limits_persist_across_instances(tmp_path: Path) -> None:
    db = tmp_path / "ledger.db"
    with LimitLedger(db) as ledger:
        c = client(Fake(created("a"), created("b")), ledger)
        c.create_supplier_bill(bill("4324.00"), check=check_invoice(facts("4324.00")))
        c.create_supplier_bill(bill("3243.00"), check=check_invoice(facts("3243.00")))
    with LimitLedger(db) as reopened:
        assert reopened.usage(TODAY, "CHF") == (2, Decimal("7567.00"))
        fake = Fake()
        with pytest.raises(LimitExceededError, match="Tagessumme"):
            client(fake, reopened).create_supplier_bill(
                bill("1081.00"), check=check_invoice(facts())
            )
        assert fake.requests == []


def test_daily_count_limit() -> None:
    ledger = LimitLedger()
    c = client(Fake(created("a"), created("b"), created("c")), ledger)
    for _ in range(3):
        c.create_supplier_bill(bill("10.81"), check=check_invoice(facts("10.81")))
    with pytest.raises(LimitExceededError, match="Tageslimite"):
        c.create_supplier_bill(bill("10.81"), check=check_invoice(facts("10.81")))


def test_concurrent_reservations_respect_count_limit(tmp_path: Path) -> None:
    db = tmp_path / "ledger.db"
    limits = BookingLimits(
        max_amount=Decimal(10), max_bills_per_day=5, max_total_per_day=Decimal(1000)
    )
    granted: list[int] = []
    errors: list[Exception] = []

    def worker() -> None:
        with LimitLedger(db) as ledger:
            for _ in range(5):
                try:
                    granted.append(ledger.reserve(Decimal(1), day=TODAY, limits=limits))
                except LimitExceededError as exc:
                    errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(granted) == 5
    assert len(errors) == 15


# ------------------------------------------------------------- Fehlerpfade
def test_client_error_releases_reservation() -> None:
    ledger = LimitLedger()
    fake = Fake(HttpResponse(400, b'{"message": "supplier_id unbekannt"}'))
    with pytest.raises(BexioError, match="supplier_id unbekannt") as info:
        client(fake, ledger).create_supplier_bill(bill(), check=check_invoice(facts()))
    assert info.value.code == "api_error"
    assert ledger.usage(TODAY, "CHF") == (0, Decimal(0))


def test_rate_limit_is_not_retried() -> None:
    fake = Fake(HttpResponse(429, b"slow down"))
    with pytest.raises(BexioError) as info:
        client(fake).create_supplier_bill(bill(), check=check_invoice(facts()))
    assert info.value.code == "rate_limited"
    assert info.value.http_status == 429
    assert len(fake.requests) == 1


@pytest.mark.parametrize("failure", [TransportError("timeout"), HttpResponse(502, b"")])
def test_ambiguous_outcome_keeps_reservation(failure: HttpResponse | Exception) -> None:
    ledger = LimitLedger()
    with pytest.raises(OutcomeUnknownError):
        client(Fake(failure), ledger).create_supplier_bill(bill(), check=check_invoice(facts()))
    assert ledger.usage(TODAY, "CHF") == (1, Decimal("1081.00"))


def test_success_without_id_and_non_json_error() -> None:
    ledger = LimitLedger()
    result = client(Fake(HttpResponse(200, b"{}")), ledger).create_supplier_bill(
        bill(), check=check_invoice(facts())
    )
    assert result.bill_id is None
    with pytest.raises(BexioError, match="Gateway kaputt"):
        client(Fake(HttpResponse(403, b"Gateway kaputt")), ledger).create_supplier_bill(
            bill(), check=check_invoice(facts())
        )
    with pytest.raises(BexioError, match=r"\['x'\]"):
        client(Fake(HttpResponse(404, b'["x"]')), ledger).create_supplier_bill(
            bill(), check=check_invoice(facts())
        )
    with pytest.raises(KeyError):
        ledger.status(999)


# ---------------------------------------------------------- Validierung Bill
@pytest.mark.parametrize(
    ("over", "message"),
    [
        ({"lines": ()}, "Positionen"),
        ({"attachment_ids": ()}, "Anhang"),
        ({"address_type": "FIRMA"}, "address_type"),
        ({"due_date": date(2026, 9, 1)}, "due_date"),
        ({"title": "x" * 81}, "title"),
        ({"gross": Decimal("1081.001")}, "Nachkommastellen"),
        ({"lines": (BillLine("Teil", Decimal("999.00"), 15, 16),)}, "Summe"),
    ],
)
def test_bill_validation(over: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        bill(**over)


def test_limits_validation() -> None:
    with pytest.raises(ValueError, match="positiv"):
        BookingLimits(max_amount=Decimal(0), max_bills_per_day=1, max_total_per_day=Decimal(1))


def test_net_lines_skip_gross_sum_check() -> None:
    b = bill(item_net=True, lines=(BillLine("Netto", Decimal("1000.00"), 15, 16),))
    assert b.to_payload()["item_net"] is True
