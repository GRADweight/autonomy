"""Tests für gw_core.rollback (GB-12, Grad >= 4).

Liefert den dritten Grad-4-Baustein aus
docs/roadmap-grad-03-05.md §2.2 (`automatic_rollback=true`).
Die Tests messen dieselben Eigenschaften wie die vorherigen zwei
Bausteine:

- **Determinismus** — gleicher Eintrag → gleicher Befehl,
  zweimal hintereinander, ohne Nebeneffekt.
- **Append-only** — einmal `durchgefuert`/`gescheitert` ist der
  Eintrag final; ein zweiter `ausfuehren`-Aufruf wirft.
- **Expliziter Befund statt stilles Scheitern** — `reversibel=False`,
  fehlende Parameter, fehlende Methode werfen mit klarer Begründung.
- **Kein transport** — `befehl()` macht keinen HTTP-Call, es liefert
  nur den Befehl (Layer-Architektur, siehe Doku §1 Technik-Wahl).
"""

import unittest

from gw_core.rollback import (
    MissingRollbackParameterFehler,
    RollbackBereitsAbgeschlossenFehler,
    RollbackEintragNichtGefundenFehler,
    RollbackManager,
    RollbackUnmoeglichFehler,
)


class TestRegistrieren(unittest.TestCase):
    def test_gleiche_ingaben_gleicher_befehl(self):
        rb = RollbackManager()
        rid = rb.registrieren(**_params())
        b1 = rb.befehl(rid)
        b2 = rb.befehl(rid)
        self.assertEqual(b1, b2)   # Determinismus: zweimal → identisch


    def test_nicht_reversible_verlangt_kein_template(self):
        rb = RollbackManager()
        rid = rb.registrieren(
            mandant="K1", prototyp="04", actor="agent",
            beschreibung="Banküberweisung ausgeführt",
            reversibel=False,
            grund="GB-12: Überweisunge sind nicht reversibel "
                  "(Zielbank hat die Transaktion bereits verbucht)",
        )
        e = rb.read(rid)
        self.assertFalse(e.reversibel)

    def test_reversible_ohne_methode_verwirft(self):
        rb = RollbackManager()
        with self.assertRaises(ValueError):
            rb.registrieren(
                mandant="K1", prototyp="04", actor="agent",
                beschreibung="Aktion X",
                reversibel=True,
                einkehren_template={"endpoint": "/x"},  # keine methode
            )


class TestBefehl(unittest.TestCase):
    def test_deterministisch(self):
        rb = RollbackManager()
        rid = rb.registrieren(**_params())
        b1 = rb.befehl(rid)
        b2 = rb.befehl(rid)
        self.assertEqual(b1.methode, b2.methode)
        self.assertEqual(b1.endpunkt, b2.endpunkt)
        self.assertEqual(b1.parameter, b2.parameter)        # identisch
        self.assertEqual(b1.als_dict(), b2.als_dict())      # serialisierbar
        # und kein Neben-Effekt:
        self.assertEqual(len(rb.offene()), 1)               # nur einer
        self.assertEqual(rb.zähler(), {
            "offen": 1, "durchgefuert": 0, "gescheitert": 0, "total": 1,
        })

    def test_reversible_verlangt_ein_template(self):
        rb = RollbackManager()
        with self.assertRaises(ValueError):
            rb.registrieren(
                mandant="K1", prototyp="04", actor="agent",
                beschreibung="x", reversibel=True,
            )

    def test_nicht_reversible_wirft(self):
        rb = RollbackManager()
        rid = rb.registrieren(
            mandant="K1", prototyp="08", actor="agent",
            beschreibung="Überweisung", reversibel=False,
            grund="GB-12: nicht reversibel",
        )
        with self.assertRaises(RollbackUnmoeglichFehler) as ctx:
            rb.befehl(rid)
        self.assertIn("nicht reversibel", str(ctx.exception))

    def test_parameter_sortiert_und_deterministisch(self):
        rb = RollbackManager()
        rid = rb.registrieren(
            mandant="K1", prototyp="04", actor="agent",
            beschreibung="Aktion mit 2 Parametern",
            reversibel=True,
            nachher_state={"foo": 2, "bar": 1},
            # Reversed Input → sortierte Output (deterministisch)
            einkehren_template={
                "methode": "PUT",
                "endpoint": "/x",
                "parameter": {"b": 2, "a": 1},
            },
            grund="GB-12",
        )
        befehl = rb.befehl(rid)
        # .parameter ist ein sortiertes tuple: ("a",1) vor ("b",2), egal
        # in welcher Reihenfolge das Template sie enthält.
        self.assertEqual(list(befehl.parameter), [("a", 1), ("b", 2)])

    def test_fehlerhafte_platzhalter(self):
        rb = RollbackManager()
        rid = rb.registrieren(
            mandant="K1", prototyp="04", actor="agent",
            beschreibung="Aktion Y",
            reversibel=True,
            nachher_state={"a": 1},
            einkehren_template={
                "methode": "PUT",
                "endpoint": "/x/{a}/{b}",   # {b} geht nicht
            },
            grund="GB-12",
        )
        with self.assertRaises(MissingRollbackParameterFehler):
            rb.befehl(rid)

    def test_nicht_gesuchte_wirft(self):
        rb = RollbackManager()
        with self.assertRaises(RollbackEintragNichtGefundenFehler):
            rb.befehl(9999)

    def test_als_dict_serialisierbar(self):
        import json
        rb = RollbackManager()
        rid = rb.registrieren(**_params())
        roh = json.dumps(rb.befehl(rid).als_dict(), ensure_ascii=False)
        self.assertIn("DELETE", roh)
        self.assertIn("/kb_bill/12903", roh)


class TestAppendOnly(unittest.TestCase):
    def test_doppelt_unverbaubar(self):
        rb = RollbackManager()
        rid = rb.registrieren(**_params())
        rb.ausfuehren(rid, success=True, resultat="ok", on_behalf_of="Edin")
        with self.assertRaises(RollbackBereitsAbgeschlossenFehler) as ctx:
            rb.ausfuehren(rid, success=True, resultat="ok", on_behalf_of="x")
        self.assertIn("bereits", str(ctx.exception))

    def test_ausfuehrung_verandert_nicht_vorher(self):
        rb = RollbackManager()
        rid = rb.registrieren(**_params())
        rb.ausfuehren(rid, success=True, resultat="ok", on_behalf_of="Edin")
        e = rb.read(rid)
        self.assertEqual(e.status, "durchgefuert")
        self.assertEqual(e.status_begruendung, "ok")
        self.assertEqual(e.aufgabe_von, "Edin")

    def test_ausfuehrung_mit_fehlermeldung(self):
        rb = RollbackManager()
        rid = rb.registrieren(**_params())
        rb.ausfuehren(rid, success=False,
                      resultat="HTTP 410 Gone", on_behalf_of="system")
        e = rb.read(rid)
        self.assertEqual(e.status, "gescheitert")
        self.assertEqual(e.status_begruendung, "HTTP 410 Gone")

    def test_zeitpunkt_wird_gespeichert(self):
        rb = RollbackManager()
        rid = rb.registrieren(**_params(), ts="2026-01-01T00:00:00Z")
        rb.ausfuehren(rid, success=True, resultat="ok",
                      on_behalf_of="Edin", ts="2026-01-02T00:00:00Z")
        e = rb.read(rid)
        self.assertEqual(e.status, "durchgefuert")
        # ts-Feld im Eintrag:
        self.assertEqual(e.ts, "2026-01-01T00:00:00Z")


def _params(**over) -> dict:
    basis = dict(
        mandant="K1", prototyp="04", actor="agent-01",
        beschreibung="Rechnung RE-2026-0042 gebucht (1281.00 CHF)",
        reversibel=True,
        vorher_state={},
        vorher_quelle="system",
        nachher_state={"bexio_id": 12903, "status": "created"},
        nachher_quelle="bexio_api",
        einkehren_template={
            "methode": "DELETE",
            "endpoint": "/kb_bill/{bexio_id}",
        },
        grund="GB-12: jede wirkungsvolle Aktion braucht einen Rollback-Pfad",
    )
    basis.update(over)
    return basis


if __name__ == "__main__":
    unittest.main()
