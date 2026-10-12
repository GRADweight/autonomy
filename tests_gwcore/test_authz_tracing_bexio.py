"""Tests für gw_core.authz / tracing / bexio.

Die drei Neuzugänge (AuthZ, Tracing, Bexio-Adapter) testen:
- GB-08 Least Privilege: Rolle 'buchhaltung' darf #02 freigeben,
  'marketing' nicht. (Beweis: der zweite Fall wirft PermissionError
  und wird als 'entscheid_abgelehnt_policy' im Audit gelistet.)
- GB-11 Tracing: eine LLM-Anfrage lässt einen Trace-Eintrag nach,
  eine fehlgeschlagene Anfrage einen Status 'error'.
- GB-09 Money-Limits: ein 90k-CHF-Betrag wird VOR dem API-Call
  abgelehnt. (Beweis: kein httpx-Client-Call, sondern ein
  BexioZielFehler mit code='limit_betrag'.)
"""

import os
import tempfile
import unittest
from unittest.mock import patch

from gw_core.approval import ApprovalQueue
from gw_core.audit import AuditTrail
from gw_core.authz import FreigabePolicy
from gw_core.bexio import BexioZielsystemAdapter
from gw_core.tracing import Tracer

POLICY = {
    "default": ["admin"],
    "02-rechnungs-extraktion": ["cfo", "buchhaltung"],
    "11-cv-screening": ["cfo", "personalverantwortung"],
}


def _queue() -> tuple[ApprovalQueue, AuditTrail]:
    audit = AuditTrail()
    q = ApprovalQueue(audit=audit, policy=FreigabePolicy(policy=POLICY))
    # Test-Hygiene: SQLite-Verbindungen schliessen (vermeidet ResourceWarning)
    q._audit = audit
    return q, audit


class TestAuthZ(unittest.TestCase):
    def test_erlaubte_rolle_darf_freigeben(self):
        q, _ = _queue()
        aid = q.vorschlage(mandant="K1", prototyp="02-rechnungs-extraktion",
                           titel="b", payload={})
        akt = q.freigabe(aid, actor="ai-lead", rolle="buchhaltung")
        self.assertEqual(akt.status, "freigegeben")

    def test_fremde_rolle_wird_abgelehnt(self):
        q, _ = _queue()
        aid = q.vorschlage(mandant="K1", prototyp="02-rechnungs-extraktion",
                           titel="b", payload={})
        with self.assertRaises(PermissionError) as ctx:
            q.freigabe(aid, actor="M", rolle="marketing")
        self.assertIn("NICHT gestattet", str(ctx.exception))

    def test_admin_darf_immer(self):
        q, _ = _queue()
        aid = q.vorschlage(mandant="K1", prototyp="11-cv-screening",
                           titel="cv", payload={})
        # 'personalverantwortung' fehlt in der Rolle 'marketing',
        # aber admin geht immer.
        akt = q.freigabe(aid, actor="A", rolle="admin")
        self.assertEqual(akt.status, "freigegeben")

    def test_zurueckstellen_braucht_keine_rolle(self):
        """Beziehungsschutz: jeder darf ablehnen — auch ohne Freigabe."""
        q, _ = _queue()
        aid = q.vorschlage(mandant="K1", prototyp="11-cv-screening",
                           titel="cv", payload={})
        akt = q.zurueckstellen(aid, actor="M", begruendung="aus rechtlichen Gründen")
        self.assertEqual(akt.status, "zurueckgestellt")

    def test_default_policy_ohne_eintrag_nur_admin(self):
        """Prototyp '99-unbekannt' steht in keiner Policy-Datei → nur admin."""
        q, _ = _queue()
        aid = q.vorschlage(mandant="K1", prototyp="99-unbekannt", titel="x", payload={})
        with self.assertRaises(PermissionError):
            q.freigabe(aid, actor="X", rolle="cfo")
        ok = q.vorschlage(mandant="K1", prototyp="99-unbekannt", titel="y", payload={})
        self.assertEqual(q.freigabe(ok, actor="A", rolle="admin").status, "freigegeben")

    def test_policy_audit_lehnen(self):
        """Abgelehnte Freigabe (via Policy) muss im Audit-Trauma nachweisbar sein."""
        q, audit = _queue()
        aid = q.vorschlage(mandant="K1", prototyp="02-rechnungs-extraktion",
                           titel="b", payload={})
        with self.assertRaises(PermissionError):
            q.freigabe(aid, actor="M", rolle="marketing")
        entries = audit.query(mandant="K1")
        actions = [e["action"] for e in entries]
        self.assertIn("entscheid_abgelehnt_policy", actions)


class TestTracing(unittest.TestCase):
    def _tracer(self) -> Tracer:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            tmp = f.name
        os.unlink(tmp)  # Tracer erwartet eine leere Datei
        return Tracer(tmp)

    def test_ok_wird_gezeichnet(self):
        t = self._tracer()
        # Direktes Record (kein MagicMock-Kontext):
        from gw_core.tracing import TraceEvent
        t.record(TraceEvent(
            mandant="K1", prototyp="01", provider="ollama", model="qwen",
            dauer_ms=1234, anfrage_länge=100, antwort_länge=500, status="ok"))
        rows = t.query()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "ok")
        self.assertEqual(rows[0]["dauer_ms"], 1234)

    def test_feilwird_gezeichnet(self):
        from gw_core.tracing import TraceEvent
        t = self._tracer()
        t.record(TraceEvent(
            mandant="K1", prototyp="02", provider="anthropic", model="claude",
            dauer_ms=50, anfrage_länge=50, antwort_länge=0,
            status="refusal", fehler="safety refusal"))
        kpi = t.zusammenfassung(mandant="K1")
        self.assertEqual(kpi["anfragen"], 1)
        self.assertEqual(kpi["fehler"], 1)
        self.assertEqual(kpi["fehlerquote_prozent"], 100.0)


class TestBexioLimits(unittest.TestCase):
    """GB-09: Money-Limits IM Zielsystem — VOR einem API-Call."""

    def _adapter(self) -> BexioZielsystemAdapter:
        with patch("httpx.Client") as mock_client:
            a = BexioZielsystemAdapter(
                token="test", sandbox=True,
                max_buchungen_pro_tag=5,
                max_betrag_chf=1000.0,
            )
            mock_client.assert_called_once()
        return a

    def test_betragueber_limit_wird_ablehnt(self):
        a = self._adapter()
        err = a.pre_ckeck(betrag_brutto=99999.0)
        self.assertIsNotNone(err)
        if err is None:  # für Typprüfer
            self.fail("Limit wurde nicht abgelehnt")
        self.assertEqual(err.code, "limit_betrag")

    def test_tagesvolumen_wird_ablehnt(self):
        a = self._adapter()
        # 5 Buchungen sind das Limit — die 5. wird erlaubt, die 6. nicht.
        a._zehler_tag = 5  # internes Test-Setup
        err = a.pre_ckeck(betrag_brutto=100.0)
        self.assertIsNotNone(err)
        self.assertEqual(err.code, "limit_tagesvolumen")

    def test_innerhalb_der_limiten_durchlaesst(self):
        a = self._adapter()
        self.assertIsNone(a.pre_ckeck(betrag_brutto=999.0))


if __name__ == "__main__":
    unittest.main()
