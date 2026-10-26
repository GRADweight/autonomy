"""bexio-Adapter: freigegebene Lieferantenrechnungen als Kreditor anlegen.

Schnittstelle: ``POST https://api.bexio.com/4.0/purchase/bills`` (bexio API,
Feldnamen gemäss docs.bexio.com, Stand Oktober 2026). Authentisierung mit
Bearer-Token (OAuth 2.0 oder Personal Access Token); Zugriff hängt zusätzlich
von den Rechten des Benutzers ab, dem das Token gehört.

Ablauf, den der Adapter erzwingt:

1. Eine bestandene Belegprüfung (:func:`~gradweight_autonomy.invoice_checks.check_invoice`)
   für genau diesen Betrag und diese Währung ist Pflicht.
2. Limiten (Betrag je Beleg, Anzahl und Summe je Tag) werden vor dem Aufruf in
   einem persistenten Ledger (SQLite) reserviert – atomar, auch über mehrere
   Prozesse auf derselben Datei.
3. Erst dann wird gesendet. Kein automatischer Retry: eine Wiederholung könnte
   doppelt buchen. Bei unklarem Ausgang (Timeout, 5xx) bleibt die Reservation
   bestehen und die Buchung muss abgeglichen werden.

Ehrliche Einordnung: Die Limiten sind eine clientseitige Schutzschicht. Als
Grenze «im Zielsystem» (GB-08/GB-09) taugen sie nur, wenn der Adapter in einem
eigenen Dienst läuft, der das bexio-Token hält und den der Agent nicht umgehen
kann. Betragsabhängige Limiten bietet die bexio-API nach unserem Kenntnisstand
nicht an.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from gradweight_autonomy._http import (
    HttpRequest,
    HttpResponse,
    Transport,
    TransportError,
    urllib_transport,
)
from gradweight_autonomy._resources import Closable
from gradweight_autonomy.invoice_checks import CENT, InvoiceCheckResult

API_BASE = "https://api.bexio.com"
BILLS_PATH = "/4.0/purchase/bills"
ADDRESS_TYPES = ("COMPANY", "PRIVATE")


class BexioError(RuntimeError):
    """Fehler des Adapters oder der bexio-API."""

    def __init__(self, code: str, message: str, http_status: int | None = None) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.http_status = http_status


class PrecheckFailedError(BexioError):
    """Belegprüfung fehlt, ist nicht bestanden oder passt nicht zur Rechnung."""


class LimitExceededError(BexioError):
    """Eine Buchungslimite würde überschritten."""


class OutcomeUnknownError(BexioError):
    """Ausgang unklar (Timeout, Serverfehler): Buchung manuell abgleichen."""


@dataclass(frozen=True)
class BillLine:
    """Position einer Lieferantenrechnung (bexio ``line_items``)."""

    title: str
    amount: Decimal
    tax_id: int
    booking_account_id: int


@dataclass(frozen=True)
class SupplierBill:
    """Lieferantenrechnung für bexio (``manual_amount`` = Bruttobetrag)."""

    supplier_id: int
    contact_partner_id: int
    bill_date: date
    due_date: date
    currency_code: str
    gross: Decimal
    lines: tuple[BillLine, ...]
    attachment_ids: tuple[str, ...]
    address_name: str
    address_type: str = "COMPANY"
    item_net: bool = False
    vendor_ref: str | None = None
    title: str | None = None

    def __post_init__(self) -> None:
        if not 1 <= len(self.lines) <= 100:
            raise ValueError("1 bis 100 Positionen erwartet")
        if not self.attachment_ids:
            raise ValueError("mindestens ein Beleg-Anhang (attachment_ids) ist Pflicht")
        if self.address_type not in ADDRESS_TYPES:
            raise ValueError(f"address_type muss einer von {ADDRESS_TYPES} sein")
        if self.due_date < self.bill_date:
            raise ValueError("due_date liegt vor bill_date")
        if self.title is not None and not 1 <= len(self.title) <= 80:
            raise ValueError("title muss 1 bis 80 Zeichen haben")
        if self.gross <= 0 or self.gross.quantize(CENT) != self.gross:
            raise ValueError("gross muss positiv sein und höchstens zwei Nachkommastellen haben")
        if not self.item_net and sum((ln.amount for ln in self.lines), Decimal(0)) != self.gross:
            raise ValueError("Summe der Bruttopositionen entspricht nicht gross")

    def to_payload(self) -> dict[str, Any]:
        """JSON-Nutzlast für ``POST /4.0/purchase/bills``."""
        payload: dict[str, Any] = {
            "supplier_id": self.supplier_id,
            "contact_partner_id": self.contact_partner_id,
            "bill_date": self.bill_date.isoformat(),
            "due_date": self.due_date.isoformat(),
            "manual_amount": True,
            "amount_man": float(self.gross),
            "currency_code": self.currency_code,
            "item_net": self.item_net,
            "attachment_ids": list(self.attachment_ids),
            "address": {"lastname_company": self.address_name, "type": self.address_type},
            "line_items": [
                {
                    "position": i,
                    "title": line.title,
                    "amount": float(line.amount),
                    "tax_id": line.tax_id,
                    "booking_account_id": line.booking_account_id,
                }
                for i, line in enumerate(self.lines)
            ],
            "discounts": [],
        }
        if self.vendor_ref:
            payload["vendor_ref"] = self.vendor_ref
        if self.title:
            payload["title"] = self.title
        return payload


@dataclass(frozen=True)
class BookingLimits:
    """Clientseitige Limiten je Währung."""

    max_amount: Decimal
    max_bills_per_day: int
    max_total_per_day: Decimal
    currency: str = "CHF"

    def __post_init__(self) -> None:
        if self.max_amount <= 0 or self.max_total_per_day <= 0 or self.max_bills_per_day < 1:
            raise ValueError("Limiten müssen positiv sein")


class LimitLedger(Closable):
    """Persistente Reservationen je Tag (SQLite, atomar über ``BEGIN IMMEDIATE``)."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False, isolation_level=None)
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS reservations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day TEXT NOT NULL,
                currency TEXT NOT NULL,
                amount TEXT NOT NULL,
                status TEXT NOT NULL,
                external_id TEXT,
                note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_res_day ON reservations (day, currency);
            """
        )

    def usage(self, day: date, currency: str) -> tuple[int, Decimal]:
        """Anzahl und Summe der nicht freigegebenen Reservationen eines Tages."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT amount FROM reservations WHERE day = ? AND currency = ? "
                "AND status != 'released'",
                (day.isoformat(), currency),
            ).fetchall()
        return len(rows), sum((Decimal(r[0]) for r in rows), Decimal(0))

    def reserve(self, amount: Decimal, *, day: date, limits: BookingLimits) -> int:
        """Reservieren oder :class:`LimitExceededError` werfen (atomar)."""
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                rows = self._conn.execute(
                    "SELECT amount FROM reservations WHERE day = ? AND currency = ? "
                    "AND status != 'released'",
                    (day.isoformat(), limits.currency),
                ).fetchall()
                count = len(rows)
                total = sum((Decimal(r[0]) for r in rows), Decimal(0))
                if count >= limits.max_bills_per_day:
                    raise LimitExceededError(  # noqa: TRY301 - Rollback im except
                        "limit_count",
                        f"Tageslimite von {limits.max_bills_per_day} Buchungen erreicht",
                    )
                if total + amount > limits.max_total_per_day:
                    raise LimitExceededError(  # noqa: TRY301
                        "limit_daily_total",
                        f"Tagessumme {total + amount} würde {limits.max_total_per_day} "
                        f"{limits.currency} überschreiten",
                    )
                cur = self._conn.execute(
                    "INSERT INTO reservations (day, currency, amount, status, created_at) "
                    "VALUES (?, ?, ?, 'reserved', ?)",
                    (
                        day.isoformat(),
                        limits.currency,
                        str(amount),
                        datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    ),
                )
                self._conn.execute("COMMIT")
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
        if cur.lastrowid is None:  # pragma: no cover
            raise BexioError("ledger", "INSERT lieferte keine ID")
        return int(cur.lastrowid)

    def _set(self, reservation_id: int, status: str, external_id: str | None, note: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE reservations SET status = ?, external_id = COALESCE(?, external_id), "
                "note = ? WHERE id = ?",
                (status, external_id, note, reservation_id),
            )

    def confirm(self, reservation_id: int, external_id: str | None) -> None:
        self._set(reservation_id, "confirmed", external_id, "")

    def release(self, reservation_id: int, note: str) -> None:
        self._set(reservation_id, "released", None, note)

    def mark_unknown(self, reservation_id: int, note: str) -> None:
        self._set(reservation_id, "unknown", None, note)

    def status(self, reservation_id: int) -> str:
        with self._lock:
            row = self._conn.execute(
                "SELECT status FROM reservations WHERE id = ?", (reservation_id,)
            ).fetchone()
        if row is None:
            raise KeyError(reservation_id)
        return str(row[0])

    def close(self) -> None:
        with self._lock:
            self._conn.close()


@dataclass(frozen=True)
class BexioResult:
    """Ergebnis einer (simulierten) Buchung."""

    dry_run: bool
    payload: Mapping[str, Any]
    bill_id: str | None = None
    document_no: str | None = None
    reservation_id: int | None = None
    raw: Mapping[str, Any] = field(default_factory=dict)


def _error_message(response: HttpResponse) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.body[:200].decode("utf-8", "replace")
    if isinstance(body, dict):
        return str(body.get("message") or body.get("error") or body)[:300]
    return str(body)[:300]


class BexioClient:
    """Schlanker Client für freigegebene Kreditorenbuchungen."""

    def __init__(
        self,
        token: str,
        *,
        limits: BookingLimits,
        ledger: LimitLedger,
        transport: Transport = urllib_transport,
        base_url: str = API_BASE,
        timeout_s: float = 30.0,
        dry_run: bool = False,
        today: Callable[[], date] = date.today,
    ) -> None:
        if not token and not dry_run:
            raise ValueError("token fehlt")
        self._token = token
        self._limits = limits
        self._ledger = ledger
        self._transport = transport
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s
        self._dry_run = dry_run
        self._today = today

    def __repr__(self) -> str:
        return f"BexioClient(base_url={self._base_url!r}, dry_run={self._dry_run}, token=***)"

    def _precheck(self, bill: SupplierBill, check: InvoiceCheckResult) -> None:
        if not check.passed:
            raise PrecheckFailedError("precheck_failed", check.summary())
        if check.facts.gross != bill.gross or check.facts.currency != bill.currency_code:
            raise PrecheckFailedError(
                "precheck_mismatch",
                "Rechnung entspricht nicht dem geprüften Beleg (Betrag/Währung)",
            )
        if bill.currency_code != self._limits.currency:
            raise LimitExceededError(
                "limit_currency", f"Währung {bill.currency_code} ist nicht freigegeben"
            )
        if bill.gross > self._limits.max_amount:
            raise LimitExceededError(
                "limit_amount",
                f"Betrag {bill.gross} über Limite {self._limits.max_amount} "
                f"{self._limits.currency}",
            )

    def create_supplier_bill(self, bill: SupplierBill, *, check: InvoiceCheckResult) -> BexioResult:
        """Lieferantenrechnung anlegen (oder im Dry-Run nur die Nutzlast liefern)."""
        self._precheck(bill, check)
        payload = bill.to_payload()
        if self._dry_run:
            return BexioResult(dry_run=True, payload=payload)
        reservation = self._ledger.reserve(bill.gross, day=self._today(), limits=self._limits)
        request = HttpRequest(
            "POST",
            self._base_url + BILLS_PATH,
            {
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json.dumps(payload).encode("utf-8"),
            self._timeout_s,
        )
        try:
            response = self._transport(request)
        except TransportError as exc:
            self._ledger.mark_unknown(reservation, str(exc))
            raise OutcomeUnknownError("outcome_unknown", f"keine Antwort von bexio: {exc}") from exc
        if response.status in (200, 201):
            body = response.json()
            bill_id = str(body.get("id")) if isinstance(body, dict) and body.get("id") else None
            document_no = body.get("document_no") if isinstance(body, dict) else None
            self._ledger.confirm(reservation, bill_id)
            return BexioResult(
                dry_run=False,
                payload=payload,
                bill_id=bill_id,
                document_no=str(document_no) if document_no else None,
                reservation_id=reservation,
                raw=body if isinstance(body, dict) else {},
            )
        if response.status >= 500:
            self._ledger.mark_unknown(reservation, f"HTTP {response.status}")
            raise OutcomeUnknownError(
                "outcome_unknown", f"bexio antwortete mit HTTP {response.status}", response.status
            )
        self._ledger.release(reservation, f"HTTP {response.status}")
        code = "rate_limited" if response.status == 429 else "api_error"
        raise BexioError(code, _error_message(response), response.status)
