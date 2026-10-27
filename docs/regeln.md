# Regel-Referenz GB-01 bis GB-22

<!-- Automatisch erzeugt mit `gw-autonomy rules --format markdown`. Nicht von Hand bearbeiten; ein Test vergleicht diese Datei mit dem Code. -->

Der Validator kennt 22 Regeln. Schweregrade: **F** = Fehler (Exit-Code 1), **W** = Warnung, **H** = Hinweis, **–** = greift auf diesem Grad nicht.

## Übersicht: höchster Schweregrad je Grad

| Regel | Titel | G0 | G1 | G2 | G3 | G4 | G5 | Greift |
|---|---|---|---|---|---|---|---|---|
| [GB-01](#gb-01) | Schema und Syntax | F | F | F | F | F | F | immer |
| [GB-02](#gb-02) | Achsen passen zum Grad | F | F | F | F | F | F | immer |
| [GB-03](#gb-03) | Rule of Two | W | W | W | W | F | F | fremde Eingaben, sensible Daten und Aussenwirkung zugleich |
| [GB-04](#gb-04) | Deckel eingehalten | F | F | F | F | F | F | falls ceiling gesetzt |
| [GB-05](#gb-05) | Fremde Texte in Entscheiden | W | W | W | W | W | W | customer_text_in_decisions und foreign_input |
| [GB-06](#gb-06) | Schutzfunktionen ausserhalb des Modells | W | W | W | W | F | F | safety_critical |
| [GB-07](#gb-07) | Übernahmequote überwacht | – | – | F | F | – | – | human_role per_action oder per_gate |
| [GB-08](#gb-08) | Mandat im Zielsystem durchgesetzt | – | – | – | F | F | – | human_role mandate |
| [GB-09](#gb-09) | Geldwirkung mit Betragsgrenze | – | – | – | F | F | F | money_effect ohne Freigabe je Aktion (mandate, exception_only) |
| [GB-10](#gb-10) | Assistent ohne Aussenwirkung | – | F | – | – | – | – | Grad 1 |
| [GB-11](#gb-11) | Identität und Beobachtbarkeit | – | – | – | F | F | F | ab Grad 4; Ausnahme-Kontrollen bei human_role exception_only |
| [GB-12](#gb-12) | Rückfallebene bereit | – | – | – | F | F | F | ab Grad 3 |
| [GB-13](#gb-13) | Schattenbetrieb und Vorschlagsmodus zuerst | – | – | – | – | F | F | ab Grad 4 |
| [GB-14](#gb-14) | Messung definiert | F | F | F | F | F | F | ab Grad 3 Pflicht; falls angegeben immer vollständig |
| [GB-15](#gb-15) | Datenklasse und Verarbeitungsort | F | F | F | F | F | F | immer |
| [GB-16](#gb-16) | Schritte passen zum Grad | F | F | F | F | F | F | falls steps angegeben |
| [GB-17](#gb-17) | Risikomerkmale widerspruchsfrei | F | F | F | F | F | F | immer |
| [GB-18](#gb-18) | Belegter Strukturbruch | F | F | F | F | F | F | customer_text_in_decisions ohne foreign_input |
| [GB-19](#gb-19) | Nachweispflicht | F | F | F | F | F | F | immer |
| [GB-20](#gb-20) | Nachweisqualität | F | F | F | F | F | F | immer; Dateiprüfung mit --check-evidence |
| [GB-21](#gb-21) | Automatisierte Einzelentscheide (revDSG) | F | F | F | F | F | F | automated_individual_decisions |
| [GB-22](#gb-22) | Hochrisiko nach EU AI Act | F | F | F | F | F | F | regulatory.eu_ai_act_high_risk |

Grade: 0 = Keine KI-Autonomie; 1 = Assistent; 2 = Copilot; 3 = Workflow; 4 = Agent mit Mandat; 5 = Autonom mit Ausnahmesteuerung.

## Zulässige Achsen je Grad (GB-02)

| Grad | Name | Zulässige Kombinationen `who_plans` / `human_role` |
|---|---|---|
| 0 | Keine KI-Autonomie | `human` / `full_control` |
| 1 | Assistent | `human` / `full_control`, `human` / `per_action` |
| 2 | Copilot | `human` / `per_action`, `model` / `per_action` |
| 3 | Workflow | `fixed_chain` / `exception_only`, `fixed_chain` / `mandate`, `fixed_chain` / `per_gate`, `model` / `per_gate` |
| 4 | Agent mit Mandat | `model` / `exception_only`, `model` / `mandate` |
| 5 | Autonom mit Ausnahmesteuerung | `model` / `exception_only` |

## Regeln im Detail

### GB-01

**Schema und Syntax** (`SchemaConformance`, Standard-Schweregrad: Fehler)

- **Greift:** immer
- **Prüft:** Die Datei ist gültiges JSON ohne doppelte Schlüssel und erfüllt das Use-Case-Schema 2.0.
- **Warum:** Nur eine eindeutige, vollständige Beschreibung lässt sich fachlich prüfen. Bei Schemafehlern werden die übrigen Regeln nicht ausgewertet.
- **Behebung:** Fehlende Pflichtfelder ergänzen, Tippfehler in Feldnamen und Werten korrigieren.
- **Referenzen:** JSON Schema Draft 2020-12; usecase-2.0.schema.json (dieses Repo)

### GB-02

**Achsen passen zum Grad** (`AxesMatchLevel`, Standard-Schweregrad: Fehler)

- **Greift:** immer
- **Prüft:** Die Kombination aus who_plans und human_role ist für den deklarierten Grad zulässig.
- **Warum:** Der Grad folgt aus zwei Fragen: Wer plant den Weg, und wo greift der Mensch ein? Ein Grad, der nicht zu den Achsen passt, verschleiert die tatsächliche Autonomie.
- **Behebung:** Grad an die Achsen anpassen oder die Freigabe strenger gestalten.
- **Referenzen:** GRADweight-Autonomiemodell (docs/autonomiegrade.md)

### GB-03

**Rule of Two** (`RuleOfTwo`, Standard-Schweregrad: Fehler)

- **Greift:** fremde Eingaben, sensible Daten und Aussenwirkung zugleich
- **Prüft:** Nicht alle drei Eigenschaften [A] fremde Eingaben, [B] sensible Daten und [C] Aussenwirkung treffen gleichzeitig zu.
- **Warum:** Solange Prompt-Injection nicht zuverlässig erkannt wird, kann ein Agent mit allen drei Eigenschaften zur Datenabfluss- oder Fehlhandlungskette werden. Bis Grad 3 bricht ein Mensch die Kette; ab Grad 4 muss eine Eigenschaft strukturell wegfallen.
- **Behebung:** Eine Eigenschaft strukturell entfernen: nur vertrauenswürdige Quellen (EDI/ERP statt Freitext), fremde Texte isoliert vorklassifizieren oder ohne Aussenwirkung arbeiten.
- **Referenzen:** Meta AI, «Agents Rule of Two» (31.10.2025), ai.meta.com/blog/practical-ai-agent-security; CVE-2025-32711 (EchoLeak, Microsoft 365 Copilot, 2025)

### GB-04

**Deckel eingehalten** (`CeilingRespected`, Standard-Schweregrad: Fehler)

- **Greift:** falls ceiling gesetzt
- **Prüft:** Der Grad liegt nicht über einem beschlossenen Deckel (ceiling.max_level).
- **Warum:** Deckel halten fest, welche Autonomie eine Organisation für einen Anwendungsfall zulässt, etwa wegen Regulierung. Aufheben darf ihn nur das Gremium, das ihn beschlossen hat.
- **Behebung:** Grad senken oder den Deckel formell durch das zuständige Gremium ändern lassen.
- **Referenzen:** EU AI Act (VO (EU) 2024/1689) Art. 6 und Anhang III, als typischer Anlass

### GB-05

**Fremde Texte in Entscheiden** (`ForeignTextInDecisions`, Standard-Schweregrad: Warnung)

- **Greift:** customer_text_in_decisions und foreign_input
- **Prüft:** Fliessen fremde Freitexte in Entscheide ein, werden sie isoliert vorklassifiziert.
- **Warum:** Freitext ist der Hauptkanal für Prompt-Injection. Ein Modell ohne Werkzeuge, das Text in ein festes Schema überführt, begrenzt den Schaden.
- **Behebung:** Kontrolle input_isolation umsetzen und belegen.
- **Referenzen:** Meta AI, «Agents Rule of Two» (31.10.2025), ai.meta.com/blog/practical-ai-agent-security; OWASP Top 10 for LLM Applications 2025, LLM06 «Excessive Agency»

### GB-06

**Schutzfunktionen ausserhalb des Modells** (`SafetyFunctionsOutsideModel`, Standard-Schweregrad: Fehler)

- **Greift:** safety_critical
- **Prüft:** Bei Schutzfunktionen bleibt der Grad höchstens 3.
- **Warum:** Schutzfunktionen müssen deterministisch und nachweisbar bleiben. Die Maschinenverordnung führt Sicherheitsbauteile mit selbstlernendem Verhalten als Maschinen mit erhöhtem Risiko (Anhang I Teil A, Konformitätsbewertung mit Stelle).
- **Behebung:** Die KI berät (Wartungsvorschlag, Ticket), die Schutzfunktion bleibt klassische Sicherheitstechnik.
- **Referenzen:** Verordnung (EU) 2023/1230 (Maschinenverordnung), in Kraft seit 19.07.2023, anwendbar ab 20.01.2027; ISO/IEC TR 5469:2024 (Functional safety and AI systems)

### GB-07

**Übernahmequote überwacht** (`AdoptionRateMonitored`, Standard-Schweregrad: Fehler)

- **Greift:** human_role per_action oder per_gate
- **Prüft:** Wo Menschen KI-Vorschläge freigeben, wird die Übernahmequote gemessen.
- **Warum:** Werden Vorschläge fast immer unverändert bestätigt, ist die menschliche Prüfung nur noch Durchklicken (Automation Bias).
- **Behebung:** Kontrolle adoption_rate_monitoring umsetzen (z. B. Kennzahl aus der Freigabe-Queue) und regelmässig Stichproben ziehen.
- **Referenzen:** EU AI Act Art. 14 Abs. 4 lit. b (Automation Bias)

### GB-08

**Mandat im Zielsystem durchgesetzt** (`MandateEnforcedInSystem`, Standard-Schweregrad: Fehler)

- **Greift:** human_role mandate
- **Prüft:** Ein Mandat existiert und seine Grenzen wirken im Zielsystem (limits_in_system).
- **Warum:** Grenzen im Prompt sind Bitten an das Modell. Wirksam sind nur Grenzen, die das Zielsystem oder ein vorgeschalteter Dienst technisch erzwingt.
- **Behebung:** Limiten als Berechtigung, Freigabestrategie oder Gateway-Regel umsetzen und mit Konfiguration oder Test belegen.
- **Referenzen:** OWASP Top 10 for LLM Applications 2025, LLM06 «Excessive Agency»

### GB-09

**Geldwirkung mit Betragsgrenze** (`MoneyLimitDefined`, Standard-Schweregrad: Fehler)

- **Greift:** money_effect ohne Freigabe je Aktion (mandate, exception_only)
- **Prüft:** Geldwirkung ohne menschliche Freigabe je Aktion hat eine bezifferte, im Zielsystem durchgesetzte Betragsgrenze.
- **Warum:** Ohne Betragsgrenze ist der mögliche Schaden eines Fehlentscheids unbegrenzt.
- **Behebung:** mandate.money_limit (Betrag, Währung, Bezugsgrösse) setzen und im Zielsystem erzwingen.
- **Referenzen:** OWASP Top 10 for LLM Applications 2025, LLM06 «Excessive Agency»

### GB-10

**Assistent ohne Aussenwirkung** (`AssistantWithoutExternalEffect`, Standard-Schweregrad: Fehler)

- **Greift:** Grad 1
- **Prüft:** Grad 1 hat keine Aussenwirkung.
- **Warum:** Ein Assistent unterstützt Menschen; schreibt oder sendet er selbst, ist es mindestens ein Copilot mit Freigabe je Aktion.
- **Behebung:** Aussenwirkung entfernen oder Grad 2 mit Freigabe-Queue wählen.
- **Referenzen:** GRADweight-Autonomiemodell (docs/autonomiegrade.md)

### GB-11

**Identität und Beobachtbarkeit** (`IdentityAndObservability`, Standard-Schweregrad: Fehler)

- **Greift:** ab Grad 4; Ausnahme-Kontrollen bei human_role exception_only
- **Prüft:** Ab Grad 4 sind Audit-Trail und eigene Agenten-Identität umgesetzt; wer nur Ausnahmen sieht, hat Ausnahme-Queue und Stichproben-Audit.
- **Warum:** Ohne Menschen in jeder Aktion braucht es Nachvollziehbarkeit, minimale Rechte und eine feste Schwelle, ab der ein Mensch übernimmt.
- **Behebung:** Bausteine audit, exception_queue und sampling_audit einsetzen; Agenten-Konto mit minimalen Rechten einrichten und belegen.
- **Referenzen:** EU AI Act Art. 12 (Aufzeichnungspflichten); OWASP Top 10 for LLM Applications 2025, LLM06 «Excessive Agency»

### GB-12

**Rückfallebene bereit** (`FallbackReady`, Standard-Schweregrad: Fehler)

- **Greift:** ab Grad 3
- **Prüft:** Incident-Prozess, automatische Rückstufung und ein getesteter Notaus sind umgesetzt; Wechsel von Modell, Prompt oder Werkzeug lösen eine Neubeurteilung aus.
- **Warum:** Je weniger Menschen im Takt eingreifen, desto schneller muss ein Fehler technisch gestoppt und rückgängig gemacht werden können.
- **Behebung:** Notaus testen und protokollieren, Rollback-Pfad je Aktion definieren (Baustein rollback), Änderungsprozess festlegen.
- **Referenzen:** EU AI Act Art. 14 Abs. 4 lit. d und e (Übersteuern, Anhalten)

### GB-13

**Schattenbetrieb und Vorschlagsmodus zuerst** (`ShadowAndProposalFirst`, Standard-Schweregrad: Fehler)

- **Greift:** ab Grad 4
- **Prüft:** Vor dem Mandat lief der Fall im Schattenbetrieb und im Vorschlagsmodus.
- **Warum:** Autonomie wird verdient, nicht eingeschaltet: Erst messen, was das System täte, dann mit Freigabe, dann mit Mandat.
- **Behebung:** Schattenbetrieb und Vorschlagsphase durchführen und Messberichte ablegen.
- **Referenzen:** GRADweight-Autonomiemodell (docs/autonomiegrade.md)

### GB-14

**Messung definiert** (`MeasurementDefined`, Standard-Schweregrad: Fehler)

- **Greift:** ab Grad 3 Pflicht; falls angegeben immer vollständig
- **Prüft:** Ab Grad 3 ist eine Messmethode (pass^k oder Schattenbetrieb) festgelegt und vollständig (bei pass^k mit k).
- **Warum:** Eine einmalig korrekte Antwort sagt wenig über Zuverlässigkeit. pass^k misst, ob eine Aufgabe in k Wiederholungen jedes Mal gelingt.
- **Behebung:** measurement mit Methode, k (bei pass^k) und Messbericht ergänzen.
- **Referenzen:** Yao et al., «τ-bench», arXiv:2406.12045 (2024), Metrik pass^k

### GB-15

**Datenklasse und Verarbeitungsort** (`DataClassAndResidency`, Standard-Schweregrad: Fehler)

- **Greift:** immer
- **Prüft:** Sensible Daten sind klassifiziert; 'geheim' nur auf eigener Infrastruktur und höchstens Grad 3; 'vertraulich' nicht in beliebiger öffentlicher Cloud.
- **Warum:** Datenklasse und Verarbeitungsort bestimmen, welche Infrastruktur und welche Autonomie vertretbar sind.
- **Behebung:** Datenklasse korrekt setzen; Verarbeitungsort oder Grad anpassen.
- **Referenzen:** revDSG (SR 235.1) Art. 8 (Datensicherheit) und Art. 16 (Bekanntgabe ins Ausland)

### GB-16

**Schritte passen zum Grad** (`StepsConsistent`, Standard-Schweregrad: Fehler)

- **Greift:** falls steps angegeben
- **Prüft:** Jeder wirksame Schritt hat eine menschliche Rolle und eine für den Grad zulässige Achsenkombination.
- **Warum:** Der Grad eines Prozesses ist der Grad seines autonomsten wirksamen Schritts. Ein einzelner Schritt mit Mandat macht aus einem Copilot einen Agenten.
- **Behebung:** Grad erhöhen (mit den Kontrollen des Grads) oder den Schritt strenger freigeben.
- **Referenzen:** GRADweight-Autonomiemodell (docs/autonomiegrade.md)

### GB-17

**Risikomerkmale widerspruchsfrei** (`RiskAttributesConsistent`, Standard-Schweregrad: Fehler)

- **Greift:** immer
- **Prüft:** Risikomerkmale und Datenangaben widersprechen sich nicht (z. B. Geldwirkung ohne Aussenwirkung, vertrauliche Daten ohne sensitive_data).
- **Warum:** Die Rule of Two zählt deklarierte Merkmale. Widersprüchliche Angaben würden sie aushebeln.
- **Behebung:** Merkmale ehrlich setzen; die Regel zeigt das betroffene Feld.
- **Referenzen:** Meta AI, «Agents Rule of Two» (31.10.2025), ai.meta.com/blog/practical-ai-agent-security; revDSG Art. 5 lit. c (besonders schützenswerte Personendaten)

### GB-18

**Belegter Strukturbruch** (`IsolationEvidenced`, Standard-Schweregrad: Fehler)

- **Greift:** customer_text_in_decisions ohne foreign_input
- **Prüft:** Wer fremde Kundentexte verarbeitet und trotzdem foreign_input=false deklariert, belegt die isolierte Vorklassifikation.
- **Warum:** foreign_input=false ist der häufigste Weg, die Rule of Two auf dem Papier zu erfüllen. Zulässig ist das nur, wenn der Entscheid nachweislich nur strukturierte Daten sieht.
- **Behebung:** Kontrolle input_isolation mit Architekturbeschreibung oder Test belegen, sonst foreign_input=true setzen.
- **Referenzen:** Meta AI, «Agents Rule of Two» (31.10.2025), ai.meta.com/blog/practical-ai-agent-security

### GB-19

**Nachweispflicht** (`EvidenceRequired`, Standard-Schweregrad: Fehler)

- **Greift:** immer
- **Prüft:** Jede als umgesetzt deklarierte Kontrolle, jedes Mandat und jede Messung verweist auf mindestens einen Nachweis passenden Typs; nicht anwendbare Kontrollen sind begründet.
- **Warum:** Ein Häkchen ist eine Behauptung. Erst der Verweis auf Testprotokoll, Konfiguration oder Freigabe macht die Angabe prüfbar.
- **Behebung:** Nachweis in 'evidence' erfassen (Typ, Ablageort, Datum) und referenzieren.
- **Referenzen:** ISO/IEC 42001:2023, Abschnitt 7.5 (dokumentierte Information)

### GB-20

**Nachweisqualität** (`EvidenceQuality`, Standard-Schweregrad: Fehler)

- **Greift:** immer; Dateiprüfung mit --check-evidence
- **Prüft:** Nachweise sind gültig datiert, nicht aus der Zukunft und nicht veraltet; mit --check-evidence existieren lokale Dateien und stimmen mit dem SHA-256 überein.
- **Warum:** Ein Notaus-Test von vor drei Jahren belegt den heutigen Zustand nicht. Ein Hash bindet den Fall an genau die geprüfte Fassung des Nachweises.
- **Behebung:** Test wiederholen und Nachweis aktualisieren; Hash nach Änderung neu setzen.
- **Referenzen:** ISO/IEC 42001:2023, Abschnitt 7.5 (dokumentierte Information)

### GB-21

**Automatisierte Einzelentscheide (revDSG)** (`AutomatedDecisionRights`, Standard-Schweregrad: Fehler)

- **Greift:** automated_individual_decisions
- **Prüft:** Bei ausschliesslich automatisierten Einzelentscheiden ist die Überprüfung durch eine Person auf Verlangen umgesetzt oder eine Ausnahme begründet.
- **Warum:** Betroffene sind über automatisierte Einzelentscheide zu informieren und können eine Überprüfung durch eine natürliche Person verlangen, ausser bei den Ausnahmen nach Abs. 3 (Vertrag mit gewährtem Begehren, ausdrückliche Einwilligung).
- **Behebung:** Prozess für Information und menschliche Überprüfung einrichten oder die Ausnahme als not_applicable mit Begründung dokumentieren.
- **Referenzen:** revDSG (SR 235.1) Art. 21, in Kraft seit 01.09.2023

### GB-22

**Hochrisiko nach EU AI Act** (`HighRiskOversight`, Standard-Schweregrad: Fehler)

- **Greift:** regulatory.eu_ai_act_high_risk
- **Prüft:** Hochrisiko-Systeme belegen menschliche Aufsicht und Protokollierung; hohe Grade werden markiert.
- **Warum:** Art. 14 verlangt, dass Menschen das System verstehen, Automation Bias erkennen, übersteuern und anhalten können; Art. 12 verlangt automatische Protokolle.
- **Behebung:** Kontrollen human_oversight und audit_log umsetzen und belegen; Fundstelle der Einstufung angeben.
- **Referenzen:** EU AI Act (VO (EU) 2024/1689) Art. 12 und Art. 14; Pflichten für Anhang-III-Systeme gelten nach VO (EU) 2026/1744 ab 02.12.2027

## Kontrollen und zulässige Nachweise

Eine Kontrolle gilt nur als umgesetzt, wenn `status` = `implemented` ist und mindestens ein Nachweis eines zulässigen Typs referenziert wird (GB-19).

| Kontrolle | Titel | Pflicht | Zulässige Nachweistypen | Höchstalter |
|---|---|---|---|---|
| `audit_log` | Audit-Trail | ab Grad 4 (Fehler) | `config`, `log_extract`, `test_report` | – |
| `agent_identity` | Eigene Agenten-Identität mit minimalen Rechten | ab Grad 4 (Fehler) | `config`, `approval_record` | – |
| `exception_queue` | Ausnahme-Queue | bei human_role exception_only (Fehler) | `config`, `test_report`, `runbook` | – |
| `sampling_audit` | Stichproben-Audit | bei human_role exception_only (Fehler) | `measurement`, `runbook`, `log_extract` | 180 Tage |
| `incident_process` | Incident-Prozess | ab Grad 3 (Fehler) | `runbook`, `policy` | – |
| `automatic_rollback` | Automatische Rückstufung und Rollback | ab Grad 3 (Fehler) | `test_report`, `runbook` | 365 Tage |
| `kill_switch` | Notaus (getestet) | ab Grad 3 (Fehler) | `test_report` | 365 Tage |
| `change_management` | Neubeurteilung bei Modell-, Prompt- oder Toolwechsel | ab Grad 3 (Warnung) | `policy`, `approval_record` | – |
| `shadow_run` | Schattenbetrieb vor Inbetriebnahme | ab Grad 4 (Fehler) | `measurement` | – |
| `proposal_mode_first` | Vorschlagsmodus vor Mandat | ab Grad 4 (Fehler) | `measurement`, `approval_record` | – |
| `adoption_rate_monitoring` | Überwachung der Übernahmequote | bedingt, siehe GB-07 | `measurement`, `config` | 180 Tage |
| `input_isolation` | Isolierte Vorklassifikation fremder Texte | bedingt, siehe GB-18 | `architecture`, `test_report` | – |
| `human_oversight` | Menschliche Aufsicht (EU AI Act Art. 14) | bedingt, siehe GB-22 | `runbook`, `policy`, `test_report` | – |
| `human_review_on_request` | Überprüfung durch eine natürliche Person auf Verlangen (revDSG Art. 21) | bedingt, siehe GB-21 | `runbook`, `policy` | – |

Mandat (`mandate.evidence`): `config`, `test_report`. Messung (`measurement.evidence`): `measurement`, `test_report`.

## Nachweistypen

| Typ | Bedeutung |
|---|---|
| `test_report` | Testprotokoll (z. B. Notaus- oder Rollback-Test) |
| `approval_record` | Freigabe- oder Entscheidprotokoll |
| `config` | Konfiguration (Datei, Berechtigung, Limite im Zielsystem) |
| `runbook` | Betriebsanleitung / Runbook |
| `policy` | Richtlinie oder Weisung |
| `measurement` | Messbericht (pass^k, Schattenbetrieb, Übernahmequote) |
| `log_extract` | Auszug aus Protokoll oder Audit-Trail |
| `architecture` | Architektur- oder Datenflussbeschreibung |
