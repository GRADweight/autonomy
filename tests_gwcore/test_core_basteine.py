"""Tests für gw_core.audit / approval / verify — die 3 fehlenden shared-Bausteine."""

import unittest

from gw_core.approval import ApprovalQueue
from gw_core.audit import AuditTrail
from gw_core.verify import Zitat, pruefe_antwort


class TestAuditTrail(unittest.TestCase):
    def test_append_only_log_und_query(self):
        a = AuditTrail()
        rid1 = a.log(mandant="K1", prototyp="02", actor="ai-lead", action="freigabe")
        rid2 = a.log(mandant="K1", prototyp="02", actor="ai-lead", action="zurueck")
        self.assertGreater(rid2, rid1)
        self.assertEqual(a.zähler(mandant="K1"), 2)
        rows = a.query(mandant="K1")
        self.assertEqual(rows[0]["action"], "zurueck")  # neueste zuerst
        self.assertEqual(rows[-1]["action"], "freigabe")

    def test_mandantentrennung(self):
        a = AuditTrail()
        a.log(mandant="A", prototyp="01", actor="x", action="a")
        a.log(mandant="B", prototyp="01", actor="x", action="b")
        self.assertEqual(a.zähler(mandant="A"), 1)
        self.assertEqual(a.zähler(mandant="B"), 1)
        self.assertEqual(len(a.query(mandant="A")), 1)

    def test_details_json_rundreise(self):
        a = AuditTrail()
        a.log(mandant="K", prototyp="02", actor="ai-lead",
              action="freigabe", details={"betrag": 1081.0, "iban": "CH93..."})
        row = a.query(mandant="K")[0]
        self.assertEqual(row["details"]["betrag"], 1081.0)

    def test_export_csv(self):
        a = AuditTrail()
        a.log(mandant="K", prototyp="02", actor="ai-lead", action="x")
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            p = a.export(Path(tmp) / "audit_test.csv")
            inhalt = p.read_text(encoding="utf-8")
        self.assertIn("actor", inhalt)
        self.assertIn("ai-lead", inhalt)


class TestApprovalQueue(unittest.TestCase):
    def _q(self):
        audit = AuditTrail()
        return ApprovalQueue(audit=audit), audit

    def test_vorschlag_dann_freigabe(self):
        q, audit = self._q()
        aid = q.vorschlage(mandant="K1", prototyp="02-rechnung",
                           titel="Rechnung buchen", payload={"betrag": 1081.0})
        act = q.freigabe(aid, actor="ai-lead")
        self.assertEqual(act.status, "freigegeben")
        self.assertEqual(act.erledigt_von, "ai-lead")
        # Jede Entscheidung muss im Audit-Trail stehen (GB-11)
        acts = [r["action"] for r in audit.query(mandant="K1")]
        self.assertIn("aktion_vorgeschlagen", acts)
        self.assertIn("aktion_freigegeben", acts)

    def test_zurueckstellen_bewahrt_grund(self):
        q, _ = self._q()
        aid = q.vorschlage(mandant="K", prototyp="24-mahnung",
                           titel="Mahnung senden", payload={"stufe": 2})
        act = q.zurueckstellen(aid, actor="ai-lead", begruendung="Kunde ist Stammkunde")
        self.assertEqual(act.status, "zurueckgestellt")
        self.assertIn("Stammkunde", act.anmerkungen)

    def test_anpassen_veraendert_payload(self):
        q, _ = self._q()
        aid = q.vorschlage(mandant="K", prototyp="02", titel="buchen",
                           payload={"betrag": 1000.0})
        act = q.anpassen(aid, actor="ai-lead", neue_payload={"betrag": 980.0})
        self.assertEqual(act.status, "angepasst")
        self.assertEqual(act.payload["betrag"], 980.0)

    def test_freigabe_nur_an_rechte_ckeck(self):
        q, _ = self._q()
        aid = q.vorschlage(mandant="K", prototyp="02", titel="zahlt",
                           payload={}, freigabe_nur_an="CFO")
        with self.assertRaises(PermissionError):
            q.freigabe(aid, actor="fremd")
        ok = q.freigabe(aid, actor="CFO")
        self.assertEqual(ok.status, "freigegeben")

    def test_offene_liste(self):
        q, _ = self._q()
        q.vorschlage(mandant="K", prototyp="02", titel="a", payload={})
        a2 = q.vorschlage(mandant="K", prototyp="02", titel="b", payload={})
        q.freigabe(a2, actor="ai-lead")
        offene = q.offene(mandant="K")
        self.assertEqual(len(offene), 1)
        self.assertEqual(offene[0].titel, "a")

    def test_einseiter_zählt(self):
        q, _ = self._q()
        a1 = q.vorschlage(mandant="K", prototyp="02", titel="a", payload={})
        a2 = q.vorschlage(mandant="K", prototyp="02", titel="b", payload={})
        a3 = q.vorschlage(mandant="K", prototyp="02", titel="c", payload={})
        q.freigabe(a1, actor="ai-lead")
        q.anpassen(a2, actor="ai-lead", neue_payload={})
        q.zurueckstellen(a3, actor="ai-lead", begruendung="x")
        s = q.einseiter(mandant="K")
        self.assertIn("Total Aktionen: 3", s)
        self.assertIn("Angepasst vom Menschen: 1", s)
        self.assertIn("Zurückgestellt: 1", s)


class TestZweitmodellPruefung(unittest.TestCase):
    QUELLEN = [
        Zitat(text="Der Rechnungsbetrag beträgt CHF 1081.00.", quelle="d1.pdf"),
        Zitat(text="MwSt-Satz beträgt 8.1 % (Normaltarif).", quelle="d1.pdf"),
        Zitat(text="Fälligkeit am 31.07.2026, Rechnungsdatum 01.07.2026.", quelle="d1.pdf"),
    ]

    def test_gedeckte_antwort_ok(self):
        antwort = ("Der Rechnungsbetrag beträgt CHF 1081.00. Die MwSt beträgt 8.1 %. "
                   "Fällig am 31.07.2026.")
        bef = pruefe_antwort(antwort, self.QUELLEN)
        self.assertTrue(bef.ok, msg=bef.zusammenfassung())
        self.assertGreaterEqual(bef.gepueft, 3)

    def test_halluzinierter_betrag_wird_gemarkt(self):
        antwort = "Der Rechnungsbetrag beträgt CHF 5432.00."
        bef = pruefe_antwort(antwort, self.QUELLEN)
        self.assertFalse(bef.ok)
        self.assertIn("5432.00", bef.fehlende)

    def test_halluzinierter_satz_wird_gemarkt(self):
        antwort = "Der MwSt-Satz liegt bei 19 %. Die Fälligkeit ist der 31.07.2026."
        bef = pruefe_antwort(antwort, self.QUELLEN)
        self.assertFalse(bef.ok)
        self.assertIn("19 %", bef.fehlende)
        # Der gedeckte Teil darf nicht im Fehlend-Katalog stehen
        self.assertNotIn("31.07.2026", bef.fehlende)

    def test_iso_datum_geprüft(self):
        bef_ok = pruefe_antwort("Datum: 2026-07-01", self.QUELLEN)
        self.assertTrue(bef_ok.ok)
        bef_ko = pruefe_antwort("Datum: 2026-12-31", self.QUELLEN)
        self.assertFalse(bef_ko.ok)

    def test_leere_fundstelle_alle_punkte_fehlt(self):
        bef = pruefe_antwort("Betrag 1081.00", [])
        self.assertFalse(bef.ok)


if __name__ == "__main__":
    unittest.main()
