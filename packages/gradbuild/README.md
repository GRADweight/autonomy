# gradBuild: Autonomiegrade für KI in KMU-Prozessen

> **Verortet: der Mensch.** `gradBuild` ist die Entscheidungsvorlage, die
> festhält, *welcher Mensch bei welchem Schritt eines KI-Prozesses eingreift*,
> plus ein Validator, der prüft, ob die Vorlage intern konsistent und den
> Regeln GB-01…GB-16 folgend formuliert ist.

**Version 0.2.0 · Zero-Deps (nur Python-Stdlib) · MIT**

---

## 1 · Was dieses Paket ist (und was nicht)

| Ja | Nein |
|---|---|
| sechs Autonomiegrade in einer 2-Achsen-Matrix | keine Runtime, es läuft keinen Agenten |
| machine-readable Case-Schema (JSON) | keine LLM-Aufrufe, keine externen APIs |
| 16 Validierungsregeln (GB-01…GB-16) | keine Ausführung, es verifiziert nur |
| CLI-Validator: `python -m gradbuild.cli <datei>` | keine Tool-Registry für externe Tools |
| 6 referenzkonforme Beispiele + 1 bewusst gescheiterter | keine Anbindung an Zielsysteme |
| Quellen und Begriffsdefinitionen (Regulatorik) | kein Audit-Log, kein Observability-Dashboard |

**Wer nutzt das:** Solo-Unternehmer:innen und kleine Teams, die ihren
Autonomiegrad vor *und* nach jeder Änderung dokumentieren und maschinell
prüfen wollen, z. B. im Stufen-Review, bei Modell-/Prompt-/Toolwechsel (GB-12).

---

## 2 · Die 6 Autonomiegrade

| Grad | Name | Wer plant? | Wo greift der Mensch? |
|---|---|---|---|
| **0** | Keine Autonomie | Mensch | `full_control`, jeder Schritt |
| **1** | Assistent | Mensch | `full_control` / `per_action` |
| **2** | Copilot | Mensch *oder* Modell | `per_action`, jede Aktion wird freigegeben |
| **3** | Workflow | `fixed_chain` *oder* Modell (Gate-Modus) | `per_gate` (+ Dunkel-Varianten `mandate` / `exception_only` nur mit `fixed_chain`) |
| **4** | Delegiert (Mandat) | Modell | `mandate`, Limiten **im Zielsystem** (ERP/API), nicht im Prompt |
| **5** | Eigen (isoliert) | Modell | `exception_only`, nur Ausnahme + Stichprobe |

**Achsen-Matrix** (exakt wie `gradbuild/schema.py::ALLOWED_AXES`); Grad =
autonomster *wirkungsvoller* Weg; reine Recherche ohne Wirkung zählt nicht):

```
Grad 0 : (human, full_control)
Grad 1 : (human, full_control) (human, per_action)
Grad 2 : (human, per_action) (model, per_action)
Grad 3 : (fixed_chain, per_gate) (model, per_gate)
         (fixed_chain, mandate) (fixed_chain, exception_only)
Grad 4 : (model, mandate) (model, exception_only)
Grad 5 : (model, exception_only)
```

**Übergangs-Logik (bewusste Designentscheidung, GB-08/GB-12):**
Der Mensch darf strenger greifen, aber nicht weiter weg. D. h.:
- Zielarchitektur bauen, Freigabe strenger halten → legal (daher `(model, per_gate)`
  bei Grad 3 und `(fixed_chain, mandate)` als "Dunkel-Variante").
- Wer eine Grenze öffnet, übernimmt die Leitplanken der nächsthöheren Stufe:
  `exception_only` bei Grad 4 erfordert Grad-5-Kontrollen (Exception-Queue,
  Stichproben-Audit). Das meldet GB-08 als warn.
- Eine `fixed_chain` ist nie Grad 4/5.

---

## 3 · Regelwerk GB-01…GB-16 (1:1 mit `gradbuild/validate.py`)

Schweregrade: **error** = Blocker (Exit-Code 1) · **warn** = Hinweis · **info** = Kontext.

| Regel | Prüfung | Trigger |
|---|---|---|
| **GB-01** | Schema: Pflichtfelder, Typen, Wertemengen, `governance`-Objekt | immer |
| **GB-02** | Achsen-Kombination ist für den Grad erlaubt (`ALLOWED_AXES`) | immer |
| **GB-03** | **Rule of Two** (Meta-Runtime-Basis): alle drei Eigenschaften zugleich — [A] externe Eingaben, [B] sensible Daten, [C] Zustands-/Auswirkung auf Externes. Grad ≥ 4 → **error, auch nicht mit Mandat zu umgehen**; Grad ≤ 3 → warn (Kette wird durch menschliches Einwirken gebrochen). Zwei von drei sind erlaubt. | immer → Level-abhängig |
| **GB-04** | Deckel: `level > ceiling.max_level` → error. Der Deckel darf nur von der Stelle erhöht werden, die ihn verabschiedet hat | falls `ceiling` gesetzt |
| **GB-05** | `customer_text_in_decisions=true` + `customer_facing`/`foreign_input` → warn (isolierte Klassifikation ohne Tools!) | Level-agnostisch |
| **GB-06** | `safety_critical=true`: Grad > 3 → error (Schutzfunktionen bleiben ausserhalb der KI, Maschinenverordnung 2023/1230); Grad ≤ 3 → warn (Deckel 2) | Level-abhängig |
| **GB-07** | Grad 2: `adoption_rate_monitored=false` → error (Automation-Bias, Art. 21 DSG) | nur Grad 2 |
| **GB-08** | `human_role='mandate'`: `mandate.limits_in_system` ist Pflicht (Limiten im Zielsystem, nicht im Prompt). Plus warn: Grad-4 `exception_only` übernimmt Grad-5-Leitplanken | Level-abhängig |
| **GB-09** | `money_effect`: Grad ≥ 4 ohne `mandate.money_limit` → warn | Level-abhängig |
| **GB-10** | Grad 1 mit `external_action=true` → error: keine Aussenwirkung, damit keine Sende-Tools und keine externen Links | nur Grad 1 |
| **GB-11** | Identität & Beobachtbarkeit: Grad ≥ 4 ohne `agent_identity_min_privilege` oder `audit_log` → error; Grad 5 ohne `exception_queue` + `sampling_audit` → error | Level-abhängig |
| **GB-12** | `automatic_rollback=false` / `kill_switch_tested=false` (Grad ≥ 3 → error); `decides_new_on_model_prompt_tool_change=false` → warn | Grad ≥ 3 |
| **GB-13** | `shadow_run_first=false` oder `proposal_mode_first=false` (Grad ≥ 4) → error: erst Schattenbetrieb, dann Vorschlag, dann Mandat | Grad ≥ 4 |
| **GB-14** | `measurement`: Grad ≥ 3 ohne `method` → error; `method` muss `pass^k` oder `shadow` sein; inkonsistente Kombinationen → warn | Level-abhängig |
| **GB-15** | `sensitive_data=true` ohne `data_class` → error; `data_class='geheim'` bei Grad ≥ 4 → error (on-prem ohne Netz oder keine KI) | Level-abhängig |
| **GB-16** | Schritte-Definition: jede wirksame Schritt-Achsenkombination muss für den Grad erlaubt sein; Wirkung ohne `human_role` → warn (sicherstellen, dass `exception_queue`+`sampling_audit` greifen, GB-11) | falls `steps` gesetzt |

### Regel-Präzedenz pro Grad (A4-Korrektur: welche Regeln zwingend greifen)

| Regel | G0 | G1 | G2 | G3 | G4 | G5 |
|---|---|---|---|---|---|---|
| GB-01 Schema | E | E | E | E | E | E |
| GB-02 Achsen | E | E | E | E | E | E |
| GB-03 Rule of Two | | . | w | w | **E** | **E** |
| GB-04 Deckel | | . | | . | | (falls `ceiling` gesetzt) |
| GB-05 Kundentexte | w | w | w | w | w | w (falls `customer_text_in_decisions`) |
| GB-06 Schutzfunktionen | w | w | w | w | **E** | **E** |
| GB-07 Übernahmequote | | . | **E** | | . | |
| GB-08 Mandat-Limiten im System | | . | | w* | **E** | |
| GB-09 Geld-Limite | | . | | . | w | w |
| GB-10 Aussenwirkung | | **E** | | . | | . |
| GB-11 Identität/Audit | | . | | . | **E** | **E** |
| GB-12 Rollback/Notaus | | . | | **E** | **E** | **E** |
| GB-13 Schatten/Vorschlag-Erste | | . | | . | **E** | **E** |
| GB-14 Messung | | . | | **E** | **E** | **E** |
| GB-15 Datenklasse | E (falls `sensitive`) | E | E | E | **E** (geheim) | **E** (geheim) |
| GB-16 Schritt-Konsistenz | | . | | . | | (falls `steps` gesetzt) |

**Legende:** E = error (Blocker) · w = warn · leere Zelle = nicht anwendbar · * = Grad-3 `exception_only`
(Dunkel-Variante) übernimmt per Definition die Grad-5-Leitplanken.

**Zur "Rule-of-Two"-Entscheidung (GB-03):** Bei Grad ≥ 4 ist die Kombination
aller drei (A + B + C) ein *harter Fehler*, auch wenn `mandate.limits_in_system=true`.
Das ist bewusst hart: Ein Mandat kann die Kette aus fremden Eingaben +
sensible Daten + externer Wirkung nicht durch Limiten entschärfen. **Der einzige legale Ausweg:** eine der drei Kategorien *strukturell* auf
`false`, z. B. bei Grad 4 C-Teile nachbestellen: Bestellung läuft ausschliesslich über
vertrauenswürdige EDI/ERP-Quellen → `foreign_input=false`. Bei Grad 5 Standardretouren:
ein *isoliertes* Vision-/Klassifikationsmodell ohne Tools prüft Kundentexte; der
Entscheid läuft auf Strukturdaten → `foreign_input=false` für den Entscheid-Agenten.

---

## 4 · CLI & Programmatische API

```bash
# einzelne Datei
python -m gradbuild.cli examples/gw5-standardretouren.json

# mehrere Dateiin
python -m gradbuild.cli examples/gw4-c-teile-nachbestellen.json examples/counterexample.json

# stdin (JSON-Array oder JSONL, eine Zeile pro Case)
cat examples/gw5-standardretouren.json | python -m gradbuild.cli --stdin
```

**Exit-Codes:** `0` = ok (ggf. mit warn/info) · `1` = mind. 1 error · `2` = Schema-/Parsefehler.

```python
from gradbuild import evaluate_case, examples   # examples = {id: case}
rep = evaluate_case(examples["gw5-standardretouren"])
print(rep.ok, rep.errors(), rep.warnings())
```

`CaseReport`-API: `.ok`, `.errors()`, `.warnings()`, `.findings[]` mit `.rule`,
`.severity`, `.level`, `.message`, `.detail`.

---

## 5 · Beispiele im Repo (Single Source of Truth)

Die **JSON-Dateien** in `examples/` sind die einzige Quelle;
`gradbuild/examples.py` lädt sie (doppelte Definitionen sind ausgeschlossen).

| Datei | Grad | Status |
|---|---|---|
| `examples/gw0-marktforschung.json` | 0 | ok |
| `examples/gw1-produktwissen-innendienst.json` | 1 | ok |
| `examples/gw2-bewerbungsvorsortierung.json` | 2 | ok (Deckel 2, Übernahmequote überwacht) |
| `examples/gw3-predictive-maintenance.json` | 3 | ok (Schattenmessung, Deckel 3/ISO 5469) |
| `examples/gw4-c-teile-nachbestellen.json` | 4 | ok (Mandat mit `money_limit` im ERP, keine fremden Eingaben) |
| `examples/gw5-standardretouren.json` | 5 | ok (isoliertes Visionmodell, `foreign_input=false`) |
| `examples/counterexample.json` | 5 | **bewusst gescheitert**, 4 Error (GB-03, GB-11, GB-13, GB-14) |

Alle 6 `gw*`-Fälle laufen in `tests/test_gradbuild.py` durch; der Counterexample
muss fehlschlagen (Test ist bewusst auf die erwarteten Fehler-Regeln gemacht).

---

## 6 · Regulatorik, Kurzreferenz (Stand 09/2026)

| Quelle | Was wir daraus ziehen |
|---|---|
| **EU AI Act Annex III** (High-Risk-Liste), Inkraft ab 2. Dezember 2027 | `ceiling` bei Bewerbungsvorsortierung (Grad 2); Datenklassen-Pflicht (GB-15) |
| **DSG Art. 21 (CH)**, menschliche Aufsicht bei algorithmischen Entscheiden | Übernahmequote bei Grad 2 (GB-07), Deckel 1/2 |
| **EU Maschinenverordnung 2023/1230** + **ISO/IEC TR 5469** | Schutzfunktionen ausserhalb der KI (GB-06, Deckel 3) |
| **Rule of Two (Meta)** | GB-03: alle drei Kategorien → warn/error, kein Mandat-Override |
| **EchoLeak (M365 Copilot, 2025)** | Warum GB-03 bei Grad ≥ 4 hart bleibt: fremde Eingaben + Kontext + Aussenwirkung = Prompt-Injection-Kette |
| **METR-Horizonte** (16 h / 50 %, 3 h / 80 %) | Autonomie ist an die Aufgabenkomplexität gebunden → Reversibilität + Isolation (GB-11/12/13) |
| **τ-bench** (GPT-4o: retail 61 %, airline 35 %, pass^8 < 25 %) | selbst "gute" Modelle sinken in der Pass-Rate → strikte Kontrollen ab Grad 4 (GB-11) |
| **Feng/McDonald/Zhang** (arXiv 2506.12469) | Framework-Referenz für Autonomie-Grade in Agenten |
| **Singapur MGF 2026** | "Bound the risks upfront": `ceiling` + `mandate.limits_in_system` |

**Hinweis:** Dies ist kein Rechtsbeistand. Für jede konkrete Implementation:
Juristische und lokale Compliance-Freigabe sind Pflicht.

---

## 7 · Terminologie

| Begriff | Bedeutung in diesem Kontext |
|---|---|
| **fremde Eingabe** | Input, der ausserhalb des kontrollierten Systems entsteht (E-Mail, Web-Formular, externe API) |
| **sensible Daten** | personenbezogene, Geschäftsgeheimnisse, Finanzdaten, gesteuert durch `data_class` |
| **ausserhalb Wirkung** | eine Aktion, die ausserhalb des Systems sichtbar ist (E-Mail-Versand, Zahlung, API-Payload) |
| **Mandat** | eine schriftliche Eingrenzung (`limits_in_system: true`), *wer* der Agent *was* tun darf, *wo*: die Limiten müssen im Zielsystem leben (Berechtigung, Schnittstelle, Zahl-Limite), nicht im Prompt |
| **Leitplanken** | `whitelist`-Effekt, keine offenen Tool-Flows: die Grenze wirkt wie eine Leitplanke an der Strasse |
| **Strukturbruch** | eine der drei Rule-of-Two-Kategorien ist *nicht gegeben* → Kombination bricht auf → Grad 4/5 legal |
| **isoliert** | Modell hat keinen Tool-Zugriff, keine fremden Eingaben als Trigger, keine Kombination aus sensiblen Daten und Wirkung ausserhalb des Systems |
| **Übergangszustand** | Phase, in der die Zielarchitektur gebaut wird, aber die Freigabe bereits strenger ist als der Zielgrad (legal; GB-12/GB-13) |
| **Dunkel-Variante** | Grad 3 mit `fixed_chain` + `mandate`/`exception_only`), Kette ohne Gates, aber erweiterte Leitplanken der Zielstufe |

---

## 8 · Installation, Tests, CI

```bash
# keine Abhängigkeiten, nur Python-Standardbibliothek, Python 3.9+
pip install -e .
# oder uv: uv pip install -e .

# CLI
python -m gradbuild.cli Beispiele.json

# Tests
python -m unittest discover -s tests -v      # lokal, keine Extras
```

**CI:** GitHub Actions (`.github/workflows/ci.yml`), Matrix Python 3.9 und 3.12,
läuft bei jedem Push. Release: `git tag v0.1.0`.

Für Python-Versionen, die nicht über ein Package-Manager installiert sind
(Homebrew-Py 3.12 mit PEP 668), empfehlen wir ein venv:

```bash
python3 -m venv .venv && .venv/bin/pip install -e .
```

---

## 9 · Offene Punkte (kritischer Selbst-Check)

Diese Punkte sind *bewusst* noch nicht abgedeckt: sie werden im nächsten
Release angegangen (A1 bis A6 sind im Commit-Message des vorangehenden Commits
referenziert):

1. **Keine Release-Prozess-Definition**: kein `CHANGELOG.md`, kein Release-Notes-Format.
   Der v0.1.0 Tag existiert, aber das Changelog-Muster ist noch nicht etabliert.
2. **Keine JSON-Schema-Export**: das Case-Schema (docs/schema.md) ist nur
   menschenlesbar; eine `gradbuild/schema.json` (JSON-Schema 2020-12) würde
   Editors und andere Werkzeuge ermöglichen.
3. **Keine i18n**: alle Meldungen, Doku, Kommentare sind auf Deutsch.
   Für eine internationale Mandantengruppe wäre ein `--lang en`-Flag sinnvoll.
4. **Kein Audit-Trail-Export**: der Validator schreibt nur eine stdout-Zeile;
   für ein Audit-System wäre ein `--json`-Output sinnvoll.
5. **Keine Mandat-Engine**: `mandate.limits_in_system` wird nur gecheckt,
   ob true. Eine echte Validierung gegen ein Zielsystem (z. B. ERP-API)
   ist out-of-scope und explizit eine Mandantenaufgabe.
6. **Keine Versions-Kompatibilität**: `requires-python = ">=3.9"` ist
   deklariert, aber die CI-Matrix (A2) deckt 3.9 und 3.12 ab; 3.10/3.11
   sind nicht in der Matrix (bewusste Entscheidung: Endpoints zuerst).

---

## 10 · Lizenz

MIT, © 2026 GRADweight GmbH (s. `LICENSE` im Repo-Root)
