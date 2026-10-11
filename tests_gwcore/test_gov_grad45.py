"""Tests für die Grad-4/5-Bausteine: ExceptionQueue + SamplingAudit.

Diese beiden Bausteine schliessen die Lücken aus
docs/roadmap-grad-03-05.md Abschnitt 2.2, die dort als «nur im JSON,
kein Code» benannt waren:

- `exception_queue=true`  -> gw_core.exception_queue.ExceptionQueue
- `sampling_audit=true`   -> gw_core.sampling_audit.SamplingAudit

Der Fokus der Tests ist die EIGENSCHAFT, nicht nur die Funktion:
Determinismus (gleiche Eingabe -> gleicher Befund), Append-only
(entschieden = final), und geschlossene Audit-Kette (GB-11).
"""

import json
import unittest

from gw_core.audit import AuditTrail
from gw_core.exception_queue import ExceptionPolicy, ExceptionQueue
from gw_core.sampling_audit import SamplingAudit, STANDARD_KRITERIEN


# --------------------------------------------------------------------------- #
# 1 · ExceptionQueue                                                          #
# --------------------------------------------------------------------------- #
class TestExceptionPolicyDeterminism(unittest.TestCase):
    """Dieser Baustein MUSS deterministisch sein — das ist sein Zweck."""

    def test_gleich_eingabe_gleich_befund(self):
        audit = AuditTrail()
        q = ExceptionQueue(audit=audit, policy=ExceptionPolicy(geld_limit=2000.0))
        erste = q.pruefe(betrag=2500.0)
        zweite = q.pruefe(betrag=2500.0)
        dritte = q.pruefe(betrag=2500.0)
        self.assertEqual(
            (erste.obliegt_mensch, erste.grund, erste.rule),
            (zweite.obligiert_mensch if False else zweite.obliegt_mensch,
             zweite.grund, zweite.rule),
        )
        self.assertEqual(
            (zweite.obliegt_mensch, zweite.rule), (dritte.obliegt_mensch, dritte.rule)
        )

    def test_ueber_limit_auusnahme(self):
        q = ExceptionQueue(policy=ExceptionPolicy(geld_limit=2000.0))
        b = q.pruefe(betrag=2001.0)
        self.assertTrue(b.obliegt_mensch)
        self.assertEqual(b.rule, "GB-09")

    def test_unter_limit_vorbeigehaeng(self):
        q = ExceptionQueue(policy=ExceptionPolicy(geld_limit=2000.0))
        b = q.pruefe(betrag=1999.0)
        self.assertFalse(b.obliegt_mensch)

    def test_genau_bei_limit_kein_auusnahme(self):
        # Grenze: strikt «grosser als» — exakt am Limit bleibt im System.
        q = ExceptionQueue(policy=ExceptionPolicy(geld_limit=2000.0))
        self.assertFalse(q.pruefe(betrag=2000.0).obliegt_mensch)

    def test_sensible_daten_fuer_der_klarung(self):
        q = ExceptionQueue(policy=ExceptionPolicy(sensible_erfordert_klarung=True))
        b = q.pruefe(sensible=True)
        self.assertTrue(b.obliegt_mensch)
        self.assertEqual(b.rule, "GB-15")

    def test_fehlerhaufung_circuit_breaker(self):
        q = ExceptionQueue(policy=ExceptionPolicy(fehlerschwelle=3))
        self.assertFalse(q.pruefe(fehler_zaehler=3).obliegt_mensch)
        self.assertTrue(q.pruefe(fehler_zaehler=4).obliegt_mensch)

    def test_keine_policy_pure_vorbeigehaeng(self):
        # Keine Schwellen gesetzt -> der Baustein entscheidet nichts.
        q = ExceptionQueue()
        self.assertFalse(q.pruefe(betrag=10**9, sensible=True).obliegt_mensch)


class TestExceptionQueueLebenszyklus(unittest.TestCase):
    _POLICY = ExceptionPolicy(geld_limit=2000.0)

    def test_einrei_offen_dann_entlastet(self):
        audit = AuditTrail()
        q = ExceptionQueue(audit=audit, policy=self._POLICY)
        eid = q.einrei(
            mandant="K1",
            prototyp="04",
            titel="Nebenkostenanlassung ueber limit",
            payload={"betrag": 2450.0},
            entscheid=q.pruefe(betrag=2450.0),
        )
        offene = q.offene(mandant="K1")
        self.assertEqual(len(offene), 1)
        self.assertEqual(offene[0].id, eid)
        a = q.entscheide(eid, status="entlastet", actor="Edin")
        self.assertEqual(a.status, "entlastet")
        self.assertEqual(a.erledigt_von, "Edin")
        self.assertEqual(q.offene(mandant="K1"), [])

    def test_doppeltentlastet_verboten(self):
        q = ExceptionQueue(policy=self._POLICY)
        eid = q.einrei(
            mandant="K1", prototyp="04", titel="t",
            payload={}, entscheid=q.pruefe(betrag=3000.0),
        )
        q.entscheide(eid, status="entlastet", actor="Edin")
        with self.assertRaises(RuntimeError):
            q.entscheide(eid, status="entlastet", actor="Anderer")

    def test_ungueltiger_zielstatus(self):
        q = ExceptionQueue(policy=self._POLICY)
        eid = q.einrei(
            mandant="K1", prototyp="04", titel="t",
            payload={}, entscheid=q.pruefe(betrag=3000.0),
        )
        with self.assertRaises(ValueError):
            q.entscheide(eid, status="offen", actor="Edin")

    def test_audit_kette_vollstaendig(self):
        # GB-11: jeder Schritt in der Queue MUSS im Trail nachweisbar sein.
        audit = AuditTrail()
        q = ExceptionQueue(audit=audit, policy=self._POLICY)
        eid = q.einrei(
            mandant="K1", prototyp="04", titel="t",
            payload={"betrag": 3000.0}, entscheid=q.pruefe(betrag=3000.0),
        )
        q.entscheide(eid, status="entlastet", actor="Edin")
        acts = [r["action"] for r in audit.query(mandant="K1")]
        self.assertIn("ausnahme_einreichte", acts)
        self.assertIn("ausnahme_entlastet", acts)

    def test_kpi_einseiter(self):
        q = ExceptionQueue(policy=self._POLICY)
        for i, betrag in enumerate([100, 2100, 500, 3000]):
            q.einrei(
                mandant="K1", prototyp="04", titel=f"Aktion {i}",
                payload={"betrag": betrag}, entscheid=q.pruefe(betrag=betrag),
            )
        # 2 ueber limit, 2 unter: alle 4 in der Queue (Einreichung ist frei).
        q.entscheide(q.offene()[0].id, status="entlastet", actor="Edin")
        q.entscheide(q.offene()[0].id, status="abgelehnt", actor="Edin")
        kpi = q.einseiter(mandant="K1")
        self.assertEqual(kpi["total"], 4)
        self.assertEqual(kpi["entlastet"], 1)
        self.assertEqual(kpi["abgelehnt"], 1)
        self.assertEqual(kpi["offen"], 2)

    def test_mandanten_getrennt(self):
        q = ExceptionQueue(policy=self._POLICY)
        e1 = q.einrei(mandant="A", prototyp="04", titel="a", payload={},
                      entscheid=q.pruefe(betrag=10000))
        e2 = q.einrei(mandant="B", prototyp="04", titel="b", payload={},
                      entscheid=q.pruefe(betrag=10000))
        self.assertEqual([a.id for a in q.offene(mandant="A")], [e1])
        self.assertEqual([a.id for a in q.offene(mandant="B")], [e2])


# --------------------------------------------------------------------------- #
# 2 · SamplingAudit                                                           #
# --------------------------------------------------------------------------- #
class TestStichprobe(unittest.TestCase):
    def _fuer_neue(self, n: int = 21):
        audit = AuditTrail()
        sampler = SamplingAudit(audit=audit)
        for i in range(n):
            # Halb Mensch, halb System — damit die Kriterien sichtbar sind.
            actor = "Edin" if i % 2 == 0 else "llm"
            sampler.beobachte(
                mandant="K1", prototyp="04", actor=actor,
                action="freigabe" if i % 2 == 0 else "entlastung",
                details={"begruendung": "k" if i % 3 != 0 else ""},
            )
        return audit, sampler

    def test_deterministisch_gleiche_stichprobe_mal_zwei(self):
        _, sampler = self._fuer_neue()
        s1 = sampler.stichprobe(mandant="K1", n=5)
        s2 = sampler.stichprobe(mandant="K1", n=5)
        self.assertEqual([e["id"] for e in s1], [e["id"] for e in s2])

    def test_n_klein_gibt_teil_n_gross_gibt_ganzes(self):
        _, sampler = self._fuer_neue(n=21)
        self.assertEqual(len(sampler.stichprobe(mandant="K1", n=5)), 5)
        self.assertEqual(len(sampler.stichprobe(mandant="K1", n=1000)), 21)

    def test_n_unter_eins_verwehrt(self):
        _, sampler = self._fuer_neue()
        with self.assertRaises(ValueError):
            sampler.stichprobe(mandant="K1", n=0)


class TestAuditBericht(unittest.TestCase):
    def _sammler(self):
        audit = AuditTrail()
        sampler = SamplingAudit(audit=audit)
        # 10 Einträge: 5 mit Menschen + Begründung, 5 ohne
        for i in range(10):
            gut = i % 2 == 0
            sampler.beobachte(
                mandant="K1", prototyp="04",
                actor="Edin" if gut else "llm",
                action="freigabe",
                details={"begruendung": "betrag plausibel" if gut else ""},
            )
        return audit, sampler

    def test_quote_und_befund(self):
        _, sampler = self._sammler()
        bericht = sampler.durchfuehre(mandant="K1", n=10, actor="revision")
        self.assertEqual(bericht.stichprobe_groesse, 10)
        self.assertEqual(bericht.passquote, 0.5)  # 5 gut / 5 schlecht
        self.assertEqual(bericht.pro_kriterium_gescheitert["mensch_in_kette"], 5)
        self.assertEqual(bericht.pro_kriterium_gescheitert["begrundung_vorhanden"], 5)

    def test_observabilitaet_der_observabilitaet(self):
        # GB-11: auch die Beaufsichtigung muss im Trail sichtbar sein.
        audit, sampler = self._sammler()
        sampler.durchfuehre(mandant="K1", n=10, actor="revision")
        acts = [r["action"] for r in audit.query(mandant="K1")]
        self.assertIn("stichproben_audit", acts)
        # und wieder lesbar:
        wieder = sampler.letzte_berichte(mandant="K1")
        self.assertIsNotNone(wieder)
        self.assertEqual(wieder.passquote, 0.5)
        self.assertEqual(len(wieder.eintraege), 10)

    def test_evidenz_serialisierbar(self):
        _, sampler = self._sammler()
        bericht = sampler.durchfuehre(mandant="K1", n=4, actor="revision")
        d = bericht.als_dict()
        roh = json.dumps(d, ensure_ascii=False)  # muss nicht werfen
        self.assertIn("passquote", roh)
        self.assertIn("eintraege", roh)

    def test_leere_trail_kein_crash(self):
        sampler = SamplingAudit()
        bericht = sampler.durchfuehre(mandant="Niemand", n=10)
        self.assertEqual(bericht.stichprobe_groesse, 0)
        self.assertEqual(bericht.passquote, 0.0)

    def test_standard_kriterien_vorhanden(self):
        self.assertEqual(
            {name for name, _ in STANDARD_KRITERIEN},
            {"mensch_in_kette", "begrundung_vorhanden"},
        )


if __name__ == "__main__":
    unittest.main()
