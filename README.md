# grad-autonomy — Autonomiegrade für KI in KMU-Prozessen

> **[CI](https://github.com/GRADweight/grad-autonomy/actions/workflows/ci.yml)** · Python 3.11 / 3.12 · **zero runtime dependencies** (outgoing httpx für den Bexio-Adapter) · Alle Rechte vorbehalten (Referenz-Nutzung + Attribution s. [LICENSE](LICENSE))

**Ein Modell, ein Validator und neun getestete Bausteine, die festhalten:
welcher Mensch greift bei welchem Schritt einer KI-Aktion ein — und was es
kostet, eine Stufe mehr Autonomie zu geben.**

Kein Framework-Pitch. Kein «KI-Plattform». Es ist ein maschinenlesbares Modell
(Grad 01–05), ein CLI-Validator, der dieses Modell gegen 16 Regeln prüft
(GB-01…GB-16), und getesteter Code für die Freigabe-Ebenen, auf denen
Grade 01 und 02 laufen.

> **Grad 01 und 02 sind hier implementiert und getestet.**
> **Grad 03, 04 und 05 sind als validierte Referenzfälle enthalten** —
> mit den Regeln, die sie verlangen, und einer ehrlichen «was fehlt»-Liste.
> Mehr Autonomie ist Custom Engineering, kein Produkt.

## Die fünf Autonomiegrade

| Grad | Name | Wer plant | Mensch-Rolle | Typische Beispiele |
|---|---|---|---|---|
| **01** | Assistent | Mensch | volle Kontrolle (`full_control`) | RAG-Antwortsuche, Entwürfe, Analysen |
| **02** | Copilot | Mensch | Freigabe je Aktion (`per_action`) | Freigabe-Queue, Zweitmodell-Prüfung, Audit |
| **03** | Workflow | Feste Kette | Freigabe je Gate (`per_gate` / `fixed_chain`) | Playbooks, systemseitige Limiten, KPI-Beobachtung |
| **04** | Agent | Modell | Mandat mit Limits (`mandate`) | Nachbestellen, Retouren — nur mit systemseitigen Limits, Rollback, Schattenbetrieb |
| **05** | Multi-Agent | Modell | Ausnahmen nur (`exception_only`) | Orchestrierung über mehrere Systeme — nur mit Sampling-Audit, Kill-Switch, getesteten Grenzen |

Wie der Grad erkannt wird (3 Fragen, in dieser Reihenfolge):

1. Greift ein Mensch bei **jeder** schreibenden Aktion? → ja: **Grad 02**.
2. Gibt es eine **Freigabe-Queue** mit Audit-Trail (wer/was/wann)? → nein: **Grad 01**.
3. Sind schreibende Aktionen auf **bestimmte Freigabepersonen** begrenzt
   und gibt es einen **KPI-Report** (Adoption-Rate)? → ja: **Grad 03**.
   Alles darüber (Grad 04/05) braucht systemseitige Mandats-Limits, Rollback,
   Schattenbetrieb und Messung. Das ist der Punkt, ab dem es keine Schublade
   mehr ist.

## Die drei harten Grenzen (gelten bei jedem Grad)

| Grenze | Regel | Wirkung |
|---|---|---|
| **Rule of Two** (GB-03) | fremde Eingaben + sensible Daten + Aussenwirkung | Grad ≥ 04: **mindestens eine** der drei muss strukturell weg. Ein Mandat ersetzt das nicht. |
| **Schutzfunktionen** (GB-06) | Qualität, Maintenance, Sicherheit | max. **Grad 03**, nie in der kritischen Kette |
| **Money-Effects** (GB-09) | Zahlung, Bestellung, Umbuchung | Grad ≥ 04: systemseitige Limits (ERP/SBuchhaltung), **nicht** im Prompt |

## Repo-Struktur

```
packages/
  gradbuild/     → Das Modell: GB-01…GB-16, JSON-Schema, CLI-Validator (zero-deps)
  gw_core/       → Neun getestete Governance-Bausteine (Freigabe, Audit, Prüfung, AuthZ, Tracing, Zielsystem, **ExceptionQueue, SamplingAudit, RollbackManager** — die letzten drei für Grad ≥ 4)
examples/        → Validierte Referenzfälle: gw0 (Grad 0) … gw5 (Grad 05) + ein bewusst
                   abgelehnter Fall (counterexample.json)
docs/            → Das Vorgehen je Phase (Plan → Inbetriebnahme), je Grad 01–05:
  plan.md        →    was vor dem Bau geklärt ist (Tore, Risiken, Rollen)
  umsetzen.md    →    was gebaut wird, je Grad (Bausteine, Tests, Evals)
  wie.md         →    wie der Code greift (Freigabe-Queue, Audit, Prüfung)
  abschluss.md   →    Kill-Kriterien und Abnahme, je Grad
  inbetriebnahme.md → Rollout, Betrieb, Rollback, Ausserbetriebnahme
  roadmap-grad-03-05.md → was «geliefert», was «valides Modell», was noch nicht gebaut ist
  technologie-stack.md  → für jeden Baustein: Technik, Alternativen, Begründung
  grad4-5-multiagent-design.md → Entwurf Grad 4/5: Team, Kontrolllogik, State, Monitoring, A2A/MCP
  unternehmens-implementierung.md → Umsetzung im Unternehmen: Gesichtspunkte je Grad, Infrastruktur & Hardware, Standort
  umsetzung/         → JE LEVEL eine technische Umsetzungsdoku (0–5): Bausteine, GB-Pflichten, Infra/HW/Standort, was NICHT Overkill
    README.md        →    Überblick über die sechs Doku + gemeinsame Grundlage + gw_core-Mapping
    grad-0.md … grad-5.md → eine Doku je Level; Referenz-Cauch gw0…gw5 (valid)
  technik-eroeffnung.md → weitere technische Möglichkeiten (Mandat-Engine, Kill-Switch-Code, A2A-Validator, JSON-Schema, i18n) — Aufwand/Abhängigkeit/Repo-vs-Mandant
governance/      → Unternehmen KI-governance-sicher machen:
  checks/        →    lauffähige Prüf-Skripte (Grad-Deckel, Injection, PII, Kill-Switch)
  vorlagen/      →    Richtlinie, KI-Register, Rollen (Markdown, anpassbar)
  a2a-agent-card.json → Agent-Card (A2A v0.3) für den Haupt-Agent (Design §4.1)
.github/         → CI, Issue-Templates, Pull-Request-Vorlage
tests_*/         → Test-Suites beider Pakete (unittest, keine versteckten Dependencies)
```

## Schnellstart

```bash
# Umgebung (Python >= 3.11, gw_core nutzt datetime.UTC)
python3 -m venv .venv && source .venv/bin/activate
pip install -e packages/gradbuild -e packages/gw_core pytest

# Alle Tests (87)
python -m pytest tests_gradbuild tests_gwcore -v

# Der komplette Freigabe-Pfad in einem Durchlauf:
# Vorschlag → Freigabe → Zweitmodell-Prüfung → Audit-Trail
python -m gw_core.demo --case examples/gw1-produktwissen-innendienst.json

# Einen Autonomie-Prüffall validieren
python -m gradbuild.cli examples/gw3-predictive-maintenance.json

# Der bewusst gescheiterte Fall (muss scheitern — das ist der Punkt)
python -m gradbuild.cli examples/counterexample.json   # Exit 1, mit Gründen
```

## Die neun Bausteine (Grad 01 + 02, plus drei für Grad ≥ 4)

| Baustein | Was er tut | Tests |
|---|---|---|
| `ApprovalQueue` | Freigabe / Anpassen / Zurückstellen je Aktion, Rechte-Check pro Rolle | 12 |
| `AuditTrail` | append-only: wer/was/wann, CSV-Export für Revision | 4 |
| `pruefe_antwort` | Zweitmodell-Prüfung: Antwort gegen Fundstellen, VETO bei Abweichung | 5 |
| `FreigabePolicy` | Rolle × Kontext, Least Privilege, admin-VETO landet im Log | 6 |
| `Tracer` | LLM-Request-Protokoll (Dauer, Status, Mandant) | 2 |
| `ZielsystemAdapter` | systemseitige Limits (Betrag, Tagesvolumen), Dry-Run und Produktionsmodus | 3 |
| `ExceptionQueue` **†** | deterministische Policy-Schwelle (Geld/sensibel/Fehlerhäufung); jeder Treffer in die Menschen-Queue, Append-only | 13 |
| `SamplingAudit` **†** | reproduzierbare systematische Stichprobentechnik über Audit-Trail, Kriterien + Evidenz | 8 |
| `RollbackManager` **†** | Snapshot-Registry (Vorher/Nachher), deterministischer Reversal-Befehl, Append-only Ausführung, KPI | 14 |

**†** = für Grad ≥ 4; schliessen die Lücke aus `docs/roadmap-grad-03-05.md` 2.2.

Zusammen ergeben diese Bausteine den Unterschied zwischen
«Das Modell hat geantwortet» und «Eine freigegebene, geprüfte und protokollierte
Aktion hat einen Zustand verändert». Details in
[packages/gw_core/README.md](packages/gw_core/README.md).

> **Wo endet «geliefert» und wo fängt «liefern» an?** Die
> [Roadmap Grad 03–05](docs/roadmap-grad-03-05.md)
> zieht diese Linie: was im Code ist (Grad 01–02), was ein valides
> Modell ist (Grad 03–05 in `examples/`), und welche Kontrollen
> noch nicht gebaut sind.
>
> **Wie ein Grad-4/5-System aufgebaut wird, wenn es gebaut wird** —
> Team, Kontrolllogik, State, Monitoring, A2A/MCP — steht im
> [Design-Entwurf](docs/grad4-5-multiagent-design.md).
> **Wie alle fünf Grade im Unternehmen umgesetzt werden** —
> Gesichtspunkte, Infrastruktur, Hardware, Standort — steht in der
> [Unternehmens-Implementierung](docs/unternehmens-implementierung.md).
> **Je eine technische Umsetzungsdoku pro Autonomielevel (Level 0–5)** —
> welche `gw_core`-Bausteine tragen, welche GB-Regeln hart greifen (Error),
> was infrastrukturell/Hardware-seitig stehen muss, und was bewusst
> **kein Overkill** ist — steht in [docs/umsetzung/](docs/umsetzung/README.md).
> **Weitere technische Möglichkeiten** (Mandat-Engine, Kill-Switch-Code,
> A2A-Card-Validator, JSON-Schema-Export, i18n) sind in
> [docs/technik-eroeffnung.md](docs/technik-eroeffnung.md) bewertet
> (Aufwand, Abhängigkeit, **Repo-vs-Mandant**).
> Status beider Seiten: Entwurf (Soll), nicht Code; die gelieferten
> Bausteine (ExceptionQueue, SamplingAudit, RollbackManager) sind in
> den Zuordnungstabellen verankert.

## Was dieses Repo NICHT ist

- **Kein LLM-Framework.** Es gibt bewusst keine Abhängigkeit von OpenAI,
  Anthropic, Ollama oder anderen Modellanbietern. Die Modell-Schicht ist
  ein anderes Projekt; hier endet sie an der Grenze «Antwort wurde erzeugt»
  und beginnt neu an «Aktion wurde freigegeben».
- **Kein Rechtsrat.** Das Modell dokumentiert, was für jeden Grad an
  Governance verlangt wird (DSG, EU AI Act, ISO/IEC 42001, Branchenregeln).
  Ob Ihr Fall Hochrisiko ist, klärt Ihre Rechtsberatung — nicht wir.
- **Kein Produkt-Katalog.** Die Beispiele in `examples/` sind Referenzfälle
  für den Validator, nicht Angebotspositionen.

## Regeln (GB-01…GB-16) in Kürze

16 Regeln, die ein Autonomie-Fall erfüllen muss, je nach Grad. Beispiele:
GB-03 (Rule of Two), GB-05 (Kundentexte in Entscheidungen nur isoliert),
GB-07 (KPI / Adoption-Rate ab Grad 03), GB-08 (AuthZ ab Grad 03),
GB-09 (systemseitige Money-Limits ab Grad 04), GB-13 (Schattenbetrieb
ab Grad 04/05), GB-16 (Messung und Rollback ab Grad 04).

Vollständige Definition: [packages/gradbuild/README.md](packages/gradbuild/README.md)
und das JSON-Schema in [packages/gradbuild/gradbuild/schema.py](packages/gradbuild/gradbuild/schema.py).

## Lizenz

Alle Rechte vorbehalten (GRADweight GmbH) — Referenz-Nutzung mit Attribution
und Community-PRs: s. [LICENSE](LICENSE).

**Kein Rechtsrat.** Stand der Doku: 2026-10. Regulierung (Digital Omnibus
VO (EU) 2026/1744 in Kraft 27.07.2026, DSG SR 235.1, ISO/IEC 42001) wird
in den Doku-Seiten mit Quellen und Datum zitiert — bitte vor Verwendung
prüfen, ob sie aktuell sind.
