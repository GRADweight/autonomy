"""Tests für den gradBuild-Validator (unittest, keine Abhängigkeiten)."""
from __future__ import annotations

import copy
import unittest

from gradbuild import examples
from gradbuild import schema
from gradbuild.validate import evaluate_case


def _sev(case: dict, rule: str, severity: str) -> bool:
    rep = evaluate_case(case)
    return any(f.rule == rule and f.severity == severity for f in rep.findings)


def _copy(case_id: str) -> dict:
    """Tiefe Kopie eines Beispiel-Falls.

    `dict(case)` kopiert nur die oberste Ebene; `case["governance"]` und
    `case["mandate"]` verweisen noch auf die globalen `examples.EXAMPLES`.
    Wer in Tests dann `case["governance"]["adoption_rate_monitored"] = False`
    setzt, verunreinigt das globale Beispiel-Objekt und bricht spätere
    Tests (z. B. TestAllExamplesPass). `copy.deepcopy` behebt das.
    """
    return copy.deepcopy(examples.EXAMPLES[case_id])


class TestSchema(unittest.TestCase):
    def test_missing_level(self):
        case = _copy("gw0-marktforschung")
        del case["level"]
        rep = evaluate_case(case)
        self.assertTrue(any(f.rule == "GB-01" and f.severity == "error" for f in rep.findings))

    def test_bad_who_plans(self):
        case = _copy("gw0-marktforschung")
        case["who_plans"] = "wizard"
        rep = evaluate_case(case)
        self.assertTrue(any(f.rule == "GB-01" and "who_plans" in f.message for f in rep.findings))


class TestAxes(unittest.TestCase):
    def test_grade5_with_per_action_rejected(self):
        case = _copy("gw5-standardretouren")
        case["human_role"] = "per_action"
        self.assertTrue(_sev(case, "GB-02", "error"))

    def test_grade0_with_mandate_rejected(self):
        case = _copy("gw0-marktforschung")
        case["level"] = 3
        case["who_plans"] = "fixed_chain"
        case["human_role"] = "exception_only"
        # Ohne safety/governance-Fehler erlaubt? Ja — dunkle Variante Grad 3 ist legal.
        self.assertFalse(_sev(case, "GB-02", "error"))


class TestRuleOfTwo(unittest.TestCase):
    def test_grade4_all_three_error(self):
        case = _copy("gw5-standardretouren")
        case["level"] = 4
        case["human_role"] = "mandate"
        case["mandate"]["limits_in_system"] = True
        case["foreign_input"] = True  # alle drei Eigenschaften → bei Grad 4 ein Error
        self.assertTrue(_sev(case, "GB-03", "error"))

    def test_grade3_all_three_warn_only(self):
        case = _copy("gw3-predictive-maintenance")
        case["foreign_input"] = True  # alle drei Eigenschaften → nur Warnung bei Grad 3
        self.assertTrue(_sev(case, "GB-03", "warn"))
        self.assertFalse(_sev(case, "GB-03", "error"))


class TestCeiling(unittest.TestCase):
    def test_above_ceiling_error(self):
        case = _copy("gw2-bewerbungsvorsortierung")
        case["level"] = 3
        case["who_plans"] = "fixed_chain"
        case["human_role"] = "per_gate"
        self.assertTrue(_sev(case, "GB-04", "error"))

    def test_at_ceiling_not_error(self):
        case = _copy("gw2-bewerbungsvorsortierung")
        self.assertFalse(_sev(case, "GB-04", "error"))


class TestSafetyDeckel(unittest.TestCase):
    def test_grade4_safety_error(self):
        case = _copy("gw3-predictive-maintenance")
        case["level"] = 4
        case["who_plans"] = "model"
        case["human_role"] = "mandate"
        self.assertTrue(_sev(case, "GB-06", "error"))

    def test_grade3_safety_warn(self):
        case = _copy("gw3-predictive-maintenance")
        self.assertTrue(_sev(case, "GB-06", "warn"))


class TestAutomationBias(unittest.TestCase):
    def test_grade2_without_adoption_monitoring_error(self):
        case = _copy("gw2-bewerbungsvorsortierung")
        case["governance"]["adoption_rate_monitored"] = False
        self.assertTrue(_sev(case, "GB-07", "error"))


class TestMandate(unittest.TestCase):
    def test_mandate_without_limits_error(self):
        case = _copy("gw4-c-teile-nachbestellen")
        case["mandate"]["limits_in_system"] = False
        self.assertTrue(_sev(case, "GB-08", "error"))

    def test_mandate_with_limits_ok(self):
        case = _copy("gw4-c-teile-nachbestellen")
        self.assertFalse(_sev(case, "GB-08", "error"))


class TestIdentity(unittest.TestCase):
    def test_grade4_without_identity_error(self):
        case = _copy("gw4-c-teile-nachbestellen")
        case["governance"]["agent_identity_min_privilege"] = False
        self.assertTrue(_sev(case, "GB-11", "error"))


class TestEscalation(unittest.TestCase):
    def test_grade4_without_rollback_error(self):
        case = _copy("gw4-c-teile-nachbestellen")
        case["governance"]["automatic_rollback"] = False
        self.assertTrue(_sev(case, "GB-12", "error"))

    def test_grade4_without_kill_switch_error(self):
        case = _copy("gw4-c-teile-nachbestellen")
        case["governance"]["kill_switch_tested"] = False
        self.assertTrue(_sev(case, "GB-12", "error"))


class TestShadowAndProposal(unittest.TestCase):
    def test_grade5_without_proposal_mode_error(self):
        case = _copy("gw5-standardretouren")
        case["governance"]["proposal_mode_first"] = False
        self.assertTrue(_sev(case, "GB-13", "error"))


class TestMeasurement(unittest.TestCase):
    def test_grade3_without_measurement_error(self):
        case = _copy("gw3-predictive-maintenance")
        del case["measurement"]
        self.assertTrue(_sev(case, "GB-14", "error"))

    def test_bad_method_error(self):
        case = _copy("gw3-predictive-maintenance")
        case["measurement"] = {"method": " vibes "}
        self.assertTrue(_sev(case, "GB-14", "error"))


class TestDataClass(unittest.TestCase):
    def test_sensitive_without_data_class(self):
        case = _copy("gw1-produktwissen-innendienst")
        case["data_class"] = None
        self.assertTrue(_sev(case, "GB-15", "error"))

    def test_geheim_at_grade4(self):
        case = _copy("gw4-c-teile-nachbestellen")
        case["data_class"] = "geheim"
        self.assertTrue(_sev(case, "GB-15", "error"))


class TestCounterexample(unittest.TestCase):
    """Die bewusst gescheiterte Datei muss mehrere Fehler produzieren."""

    def test_counterexample_fails(self):
        with open("examples/counterexample.json", encoding="utf-8") as f:
            import json
            case = json.load(f)
        rep = evaluate_case(case)
        rules = {f.rule for f in rep.findings if f.severity == "error"}
        # Erwartet: Rule of Two (GB-03), Grad-5-Kontrollen (GB-11), Schatten/Vorschlag (GB-13)
        self.assertIn("GB-03", rules)
        self.assertIn("GB-11", rules)
        self.assertIn("GB-13", rules)
        self.assertFalse(rep.ok)


class TestAllExamplesPass(unittest.TestCase):
    def test_referenced_examples_clean(self):
        for cid, case in examples.EXAMPLES.items():
            with self.subTest(cid=cid):
                rep = evaluate_case(case)
                self.assertTrue(
                    rep.ok,
                    msg=f"{cid}: {[(f.rule, f.severity, f.message) for f in rep.findings if f.severity == 'error']}",
                )


if __name__ == "__main__":
    unittest.main()
