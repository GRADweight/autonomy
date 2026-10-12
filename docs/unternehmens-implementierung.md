# Unternehmens-Implementierung — alle Autonomiegrade, Infrastruktur, Hardware, Standort

> **Stand:** 2026-10-11 · **Repo:** `GRADweight/gradautonomy`
>
> **Status: Entwurf (Soll) für den Deployment-Betrieb — nicht Code.**
> Diese Seite beantwortet drei Fragen für **jeden** Autonomiegrad 01–05:
>
> 1. **Welche Gesichtspunkte** müssen im Unternehmen erfüllt sein
>    (Regel, Rolle, Daten, Audit, Limit)?
> 2. **Welche Infrastruktur & Hardware** braucht der Betrieb — und wo
>    läuft was?
> 3. **Wo (Standort)** — Schweiz, EU-Cloud, On-Prem, und warum.
>
> Abgrenzung: `docs/plan.md` – `docs/inbetriebnahme.md` behandeln die
> **Prozess-Phasen**,
> `docs/grad4-5-multiagent-design.md` (4) behandelt die
> **Software-Architektur** für Grad 4/5. Diese Seite behandelt die
> **Umgebung**: die Maschine, die Leitungen, den Ort, die Rollen im
> Unternehmen. Kein Rechtsrat — jede Regel-Referenz verweist auf
> `packages/gradbuild/gradbuild/validate.py` (GB-01…GB-16, dort
> kanonisch) oder auf die Doku mit Quelle und Datum.

---

## 1 · Die verpflichtenden Gesichtspunkte, je Grad (die vollständige Kreuztabelle)

Jede Zelle ist entweder: **Pflicht** (der Grad wird abgelehnt ohne sie —
`validate.py`), **empfohlen**, oder «—» (nicht relevant). Die Spalten
«01–05» folgen der Nummer der Beispiel-Fälle `examples/gw1…gw5.json`.

| Gesichtspunkt | GB-Regel | 01 Assistent | 02 Copilot | 03 Workflow | 04 Agent | 05 Multi-Agent |
|---|---|---|---|---|---|---|
| Menschlicher Plan & Rolle definiert | GB-02 | Pflicht | Pflicht | Pflicht | Pflicht | Pflicht |
| Rule of Two (fremde/sensibel/extern: max. 2 von 3) | GB-03 | info | warn | warn | **Error** | **Error** |
| Deckel-Nutzung (max. Grad nur durch den verabschiedendenden) | GB-04 | — | — | — | — | — |
| Kundentext isoliert klassifizieren (tool-frei) | GB-05 | — | warn | warn | Pflicht (falls `customer_text_in_decisions`) | Pflicht |
| Schutzfunktionen ausserhalb der KI | GB-06 | — | — | warn | **Error (grad >3)** | **Error** |
| Übernahmequote überwacht (Automation-Bias) | GB-07 | — | **Error** | empfohlen | empfohlen | empfohlen |
| Mandat-Limits **im** Zielsystem, nicht im Prompt | GB-08 | — | — | warn (Grad-4-`exception_only`) | **Error** | **Error** |
| Money: `money_effect` + `mandate.money_limit` | GB-09 | — | — | info | warn | warn |
| Grad 1: keine Aussenwirkung | GB-10 | **Error** | — | — | — | — |
| Agenten-Identität + Audit-Log | GB-11 | — | — | empfohlen | **Error** | **Error (+ ExceptionQueue+SamplingAudit)** |
| Automatik-Rollback + Kill-Switch-geprüft + Neu-Entscheid bei Modell-/Toolwechsel | GB-12 | — | — | **Error** | **Error** | **Error** |
| Schattenlauf + Vorschlagsmodus zuerst | GB-13 | — | — | — | **Error** | **Error** |
| Messung `pass^k` oder `shadow` | GB-14 | — | — | **Error** | **Error** | **Error** |
| Datenklasse + Residency | GB-15 | info | Pflicht (bei `sensitive`) | Pflicht | Pflicht (**`geheim` = Error**) | Pflicht (**`geheim` = Error**) |
| Schritt-Konsistenz (`steps`) | GB-16 | — | — | empfohlen | empfohlen | empfohlen |

**Zwei Dinge, die die ganze Tabelle beherrschen:**

1. **Der Mensch ist in jedem Grad ein Teil des Systems** — was ihn
   «entfernt», ist systemseitig dokumentiert und begrenzt (GB-02, GB-08).
   Ein Grad ohne menschliche Rolle im JSON existiert nicht.
2. **Geld und Daten bleiben systemseitig** (GB-08/GB-09/GB-15). «Das
   Modell ist gut genug» ist in keiner einzigen Zelle erlaubt.

---

## 2 · Umsetzung je Grad — was im Unternehmen konkret stehen muss

Die Spalte «im Repo» markiert, was als Code/Validierung schon existiert
(geliefert, siehe `docs/roadmap-grad-03-05.md` §2), und was
Deployment-Entscheidung ist.

### Grad 01 — Assistent

- **Pflicht im Unternehmen:** Definition der Rolle (GB-02), keine
  Aussenwirkung (GB-10), Datenklasse (GB-15 falls `sensitive`), ein
  Verantwortlicher pro Use-Case.
- **Im Unternehmen stehen:** ein LLM-Endpunkt (lokal oder Schweizer
  Cloud), ein Vektorspeicher falls RAG, eine einfache Oberfläche zum
  Fragen.
- **Im Repo (geliefert):** `validate.py` (GB-01…15), `AuditTrail` (Beweis),
  `pruefe_antwort` (Halluzination-Prüfung).
- **NICHT nötig:** Mandat, Rollback, ExceptionQueue, Sampling,
  Identitäten (diese Dinge zählen hier nur, wenn sie schon genutzt
  werden — kein Overkill).

### Grad 02 — Copilot

- **Pflicht im Unternehmen:** **Übernahmequote gemessen** (GB-07) — ein
  Dashboard, ein Zahlenset, ein Verantwortlicher, der sie liest;
  **Freigabe je Aktion** (GB-02/GB-05) — eine UI, die jede Aktion
  anzeigt, die das Modell vorschlägt, und eine Freigabe-Entscheidung
  einfordert.
- **Im Unternehmen stehen:** das oben + eine Freigabe-Warteschlange
  (kann ein Webform sein, muss nicht), ein Audit-Trail (SQLite reicht),
  ein Zweitmodell für die Antwortprüfung.
- **Im Repo (geliefert):** `ApprovalQueue`, `FreigabePolicy`,
  `pruefe_antwort`, `AuditTrail`, `Tracer`.
- **NICHT nötig (bewusst):** Geld-Limits, Rollback, Schattenlauf — für
  Grad 2 ist das Overkill und der Validator akzeptiert das Modell ohne
  diese Features.

### Grad 03 — Workflow

- **Pflicht im Unternehmen:** **Kill-Switch geprobt** + **Automatik
  Rollback** + **Neu-Entscheid bei Modell-/Prompt-/Toolwechsel**
  (GB-12) — das heißt: ein dokumentierter Ablauf, wie man ein
  laufendes Workflow-System innerhalb von Minuten **abschaltet**, und
  ein getesteter Rollback auf den vorherigen Zustand.
- **Im Unternehmen stehen:** die Grad-2-Bausteine + ein **Gate-System**
  (`per_gate`), ein **Stufen-Dashboard** (welcher Grad ist wo, welcher
  Mensch ist wo), eine **Change-Log**-Pflicht (Wer hat was wann
  umgestellt).
- **Im Repo (geliefert):** `validate.py` erzwingt `kill_switch_tested`,
  `automatic_rollback`, `decides_new_on_model_prompt_tool_change`
  (GB-12, Error-Prüfung). `ExceptionQueue` ist optional, aber empfohlen.
- **NICHT nötig:** Shadow-Modus (GB-13 ist Grad 4+), ExceptionQueue
  (Grad 4+), Identitäten (Grad 4+).

### Grad 04 — Agent

- **Pflicht im Unternehmen:** **Mandat mit Limits im Zielsystem**
  (GB-08, Error) + **Money-Limit** (GB-09, warn — aber ein Mandat ohne
  Betrag ist ein Versprechen, keine Grenze) + **Agenten-Identität**
  (GB-11, Error) + **Schattenlauf zuerst** (GB-13, Error) +
  **Vorschlagsmodus zuerst** (GB-13, Error).
- **Im Unternehmen stehen:** Grad-3-Bausteine + ein **dediziertes
  Servicekonto** (nicht «das allgemeine ERP-Konto» — `agent_identity`
  heisst: das Konto, das der Agent benutzt, darf *genau* die
  Endpunkte, die er braucht, und *nichts* mehr). + eine
  **Zielsystem-Schnittstelle** (ERP/EDI), die in Shadow-Modus
  «keine» Schreibzugriffe durchlässt, bis das Mandat freigegeben ist.
  + eine **Belegkette** (Audit-Trail + Snapshot vorher/nachher).
- **Im Repo (geliefert):** `RollbackManager` (GB-12, Snapshot, Befehl,
  Ausführung), `ExceptionQueue` (GB-11/12, deterministische
  Ausgliederung), `SamplingAudit` (GB-12/14, Stichprobenaudit). `gw_core/
  bexio.py` ist ein Referenz-Adapter für die Zielsystem-Schicht.
- **NICHT nötig:** Multi-Agent (Grad-5-Domain), aber die
  `ExceptionQueue` + `SamplingAudit`-Bausteine sind hier das Fundament.

### Grad 05 — Multi-Agent

- **Pflicht im Unternehmen:** alles aus Grad 4 + **deterministische
  Policy-Schicht für Geld und Daten** (GB-08/GB-09, als separate,
  prüfbare Komponente), **ExceptionQueue + SamplingAudit als
  System-Pflicht** (GB-11, Error), **Kundentext-Klassifikation**
  (GB-05, Pflicht, tool-frei), **Mandate und Freigaben als System,
  nicht als Prompt** (GB-08).
- **Im Unternehmen stehen:** Grad-4-Bausteine + ein **Isolations-Modell**
  (jeder Agent in seiner eigenen Sandbox, kein Agent sieht den Token
  eines anderen), ein **Klassifikator-Endpunkt** (tool-frei, GB-05),
  ein **Beleg-Export** (Audit-Trail als CSV/Parquet, für die Revision),
  ein **Killer-Schalter** (systemseitig, nicht promptseitig).
- **Im Repo (geliefert):** `ExceptionQueue` + `SamplingAudit` +
  `RollbackManager` als die drei Bausteine, die Grad 5 trägt; `validate.py`
  prüft die Pflichtfelder.
- **Deployment-Bausteine (Entwurf, nicht Code):** das Orchestrierungs-
  System, der Klassifikator, die MCP/Tool-Schicht — siehe
  `docs/grad4-5-multiagent-design.md` §4/§5.

---

## 3 · Infrastruktur, Hardware & Standort (das ist der Unterschied zwischen «kann» und «läuft»)

> **Die Grundregel:** `gw_core` und `gradbuild` (d.h. **dieses Repo**)
> sind **zero-Dep** und **SQLite-basiert** — sie laufen auf `any`
> Maschine, die Python 3.11 spricht, mit **keinem** externen Service.
> Das ist der Punkt: **die Control-Plane hat keinen Standort.**
> Was einen Standort braucht, ist die **RAG-Schicht** (Vektorspeicher),
> die **Inferschicht** (GPU), und die **Zielsystem-Schnittstelle**
> (ERP-Netz). Die drei haben wir separat entschieden.

### 3.1 Die drei Schichten, drei Entscheidungen

| Schicht | Was | Standort-Entscheidung |
|---|---|---|
| **Control-Plane** | `gw_core` + `gradbuild` + das Orchestrations-System | **Lokal.** SQLite läuft auf einem Server, einer VM, einem Container — wo auch immer. **Kein Standort-Risiko.** (GB-12/13/14-Logik bleibt lokal.) |
| **RAG-Schicht** | Vektorspeicher, Embeddings, Chunking | **Schweizer Cloud** oder **On-Prem** (falls `data_class=vertraulich` oder höher). Nicht US-Cloud. (GB-15, DSG.) |
| **Inferenz-Schicht** | LLM-Endpunkt (lokale Modelle, Cloud-LLMs) | **Einziger Standort-entscheid mit echtem Risiko.** Lokal (On-Prem) für `vertraulich`/`geheim`, Schweizer/EU-Cloud für `intern`/`frei`, **US-Cloud nur für `frei`** und dann mit AVV. (GB-15/DSG.) |
| **Zielsystem-Schnittstelle** | ERP, Buchhaltung, CRM | **Im Netzwerk des Zielsystems.** Kein Cloud-Durchsatz, wenn das ERP on-prem ist. (GB-08/GB-15.) |

### 3.2 Standortbestimmung (Standort) — warum diese Reihenfolge

**Schweiz zuerst** ist keine Marketing-Aussage, es ist eine Consequenz
der Datenklassen-Logik (GB-15 + DSG + ISO 42001):

1. **DSG (SR 235.1)** — der Schweizer Datenschutz verlangt, dass
   sensible Daten in einer Weise verarbeitet werden, die der Schweiz
   «vergleichbar» ist. Ein **Schweizer Anbieter** (Exoscale, Infomaniak)
   ist der niedrigste Nachweis-Kosten-Pfad.
2. **EU AI Act + Digital Omnibus** — die Pflichten sind EU, aber die
   Schweizer Umsetzung verlangt, dass die Daten **nicht** in einem Nicht-
   Angemessenheits-Land (USA) landen, es sei denn, es gibt einen AVV +
   Supplementary Measures. (Quelle: `docs/souverainetaet-schweiz.md`,
   Stand 10/2026, und `technologie-stack.md` §3.)
3. **GB-15** (in `validate.py`) — `data_class='geheim'` bei Grad ≥ 4
   ist **Error** ohne `on-prem ohne Netz` oder `keine KI`. Das ist die
   härteste Grenze im ganzen Repo: **Geheim-Daten bleiben entweder lokal
   oder es gibt keine KI.**

**Die vier Standort-Optionen, konkret:**

| Option | Was | Für welche `data_class`/Grad |
|---|---|---|
| **1 · On-Prem (Lokal)** | Eigene Maschine, Ollama/MLX, kein Internet für das Modell | `vertraulich`–`geheim`, alle Grade; der **einzige** Weg für `geheim` + Grad ≥ 4 (GB-15) |
| **2 · Schweizer-Sovereign-Cloud** | Exoscale (CH-ZH-1, CH-GVA-2, CH-DK-2) oder Infomaniak (Geneva) — «Swiss zones, exclusively operated in Switzerland» (Exoscale-Doku) | `intern`–`vertraulich`, alle Grade. Der Default-Pfad für `vertraulich`. |
| **3 · Schweizer/EU-On-Prem-MIX** | Control-Plane + Inferenz lokal, RAG in Schweizer Cloud (für Skalierung), Zielsystem lokal | die typische **Mittelstandslösung**: sensible Daten lokal, Skalierbarkeit in der Cloud |
| **4 · US/EU-Cloud-LLM (API)** | OpenAI/Azure/Anthropic-Endpunkt, nur für `frei`/`intern` mit AVV | `frei`–`intern`, Grad 1–3 nur. **Nicht** für `vertraulich`/`geheim`. |

> **Keines der vier** ist «alles kann überall» — das ist der Punkt.
> **Der Standort** ist eine *Datenklassen*-Entscheidung, nicht eine
> *Budget*-Entscheidung. Wer `vertraulich` in eine US-Cloud steckt,
> hat nicht «gespart», er hat einen GB-15/DSG-Verstoß gebaut.

### 3.3 Die Inferenz-Schicht (die einzige mit echtem Hardware-Entscheid)

**Die Größe des Modells bestimmt die GPU, die Größe der GPU bestimmt
den Standort.** Die Tabelle ist ein **Minimum**, nicht ein Maximum —
`quantized` (Q4/Q5) ist der Standard für Inferenz, keine
«Reduktion».

| Modell (Beispiel) | VRAM (Q4) | VRAM (Q8) | GPU-Option | Standort |
|---|---|---|---|---|
| **7B** (Llama-3.1-8B-Instruct) | ~8 GB | ~16 GB | RTX 4090 (24 GB), A30 (24 GB), M3-Ultra (96 GB) | überall |
| **14B** (Llama-3.1-14B, Mistral-14B) | ~10 GB | ~20 GB | RTX 4090 (24 GB), A5000 (24 GB) | überall |
| **32B** (Llama-3.3-70B Instruct, Qwen2.5-32B) | ~20 GB | ~40 GB | **RTX 4090 (24 GB) grenzwertig**, A6000 (48 GB), M3-Ultra 128+ | **on-prem bevorzug**, CH-GVA-2 (Exoscale A30) |
| **70B** (Llama-3.3-70B) | ~40 GB | ~80 GB | A6000 (48 GB), H100 (80 GB), M3-Ultra 192+ | **on-prem oder CH-GVA-2/CH-DK-2** |
| **MoE (Qwen3-35B-A3B)** | ~24 GB (Q4) | ~48 GB (Q8) | RTX 4090 (24 GB) **genau**, A5000 (24 GB) **genau**, A30 (24 GB) **genau** | **das ist der sweet-spot**: schnelle Inferenz auf 24-GB-Karten, MoE-Aktivierung nur 3B |

> **Die praktische Regel:** Für **KMU-Standardfälle** ist
> **7B–14B + Ollama** (Lokal oder CH-GVA-2) der pragmatische Standard.
> Für **`vertraulich`/`geheim`** ist **On-Prem + lokale Modelle** der
> Pfad. Für **`frei`** ist **US/EU-Cloud-LLM (API)** akzeptabel, aber
> nur wenn die Datenklasse das erlaubt (GB-15/DSG).

**Ein Beispiel-Hardware-Set je Grad (konkret, nicht Marketing):**

| Grad | Inferenz | Control-Plane | Zielsystem-Schnittstelle |
|---|---|---|---|
| **01** | 7B–14B, Ollama, auf jedem PC | Python 3.11, SQLite (lokal) | — |
| **02** | 7B–14B, + Zweitmodell (lokal oder CH-GVA-2 A30) | dito + Audit-DB (SQLite, CH-GVA-2) | Freigabe-UI (lokal) |
| **03** | 14B–32B, MoE bevorzugt (Qwen3-35B-A3B) | dito + Gate-Queue (lokal) | ERP-lesend (lokal) |
| **04** | 32B–70B (oder MoE), CH-GVA-2/On-Prem | dito + Dediziertes Servicekonto + Shadow-Modus | ERP-schreibend (Shadow + Prod) |
| **05** | 70B oder MoE, + getrennter Klassifikator (7B tool-frei) | dito + Sandbox-Isolation + Beleg-Export | Multi-Ziel (Shadow + Prod) |

### 3.4 Netzwerk-Architektur (die drei Netze, keine Vermischung)

```
 ┌──────────────────────────────────────────────────────────────┐
 │  LAN (Büro)                                                  │
 │  ┌──────────────┐  ┌──────────────────────────────────────┐  │
 │  │ Freigabe-UI  │  │ ERP/CRM (Zielsystem)                 │  │
 │  │ (Grad 2+)    │  │ (Shadow-Modus + Prod-Modus)          │  │
 │  └──────────────┘  └──────────────────────────────────────┘  │
 ├──────────────────────────────────────────────────────────────┤
 │  MODEL-LAN (kein Internet)                                   │
 │  ┌────────────────────────────────────────────────────────┐  │
 │  │ Ollama / MLX / vLLM  (L4/L5)                           │  │
 │  │   + Klassifikator (tool-frei, L5)                      │  │
 │  └────────────────────────────────────────────────────────┘  │
 ├──────────────────────────────────────────────────────────────┤
 │  CONTROL-LAN (einziges mit Internet, nur für Updates)        │
 │  ┌────────────────────────────────────────────────────────┐  │
 │  │ gw_core (SQLite) + Orchestrator + Sampling/KPI         │  │
 │  └────────────────────────────────────────────────────────┘  │
 └──────────────────────────────────────────────────────────────┘
```

**Regel:** Das Model-LAN hat **keinen** Internet-Zugriff (DNS
blockiert, kein NTP ausserhalb). Ein kompromittiertes Modell kann
keine Daten exfiltrieren, weil es kein Netz hat. Und das ist möglich,
weil `gw_core` **keine** HTTP-Abhängigkeit im Kern hat: `bexio.py` ist
ein Adapter, kein Core-Modul. Control-Plane und Zielsystem-Adapter
laufen im selben LAN, das Modell-Netz bleibt abgetrennt.

### 3.5 Die harte Grenze (GB-15) — was «geheim» im Betrieb heisst

`validate.py` sagt es klar (GB-15, Error für Grad ≥ 4):

> `data_class='geheim'` bei Grad ≥ 4 — erlaubte Varianten:
> **on-prem ohne Netz**, oder **keine KI**.

Das ist nicht eine Empfehlung, das ist eine **Abbruch-Bedingung** im
Validator. Wenn ein KMU mit `geheim` (z.B. Patent-Daten,
M&A-Vorbereitung) einen Grad-4-Agent will, hat er zwei Optionen:

1. **On-Prem, kein Netz** (ein dedizierter Rechenraum, kein
   Internet, manuelles Medien-Transport für Updates).
2. **Keine KI** (der Prozess bleibt manuell, oder Grad 1–2 mit
   menschlicher Kontrolle).

Das ist der Punkt, an dem das System ehrlich bleibt.

---

## 4 · Was diese Doku NICHT ist

- **Kein Angebot.** Die Preise der Cloud-Anbieter sind auf deren
  Websites, und sie ändern sich — wir verlinken sie, nicht hier.
- **Kein Rechtsrat.** GB-15, DSG, ISO 42001 sind **technische
  Grenzen**, die wir im Code erzwingen oder prüfen. Die rechtliche
  Beurteilung («ist `intern` hier wirklich `intern`?») ist eine
  Rechtsfrage, nicht eine Validierungsfrage.
- **Kein Build-Plan.** `docs/plan.md` (5) ist der Build-Plan. Diese
  Seite ist die **Umgebung**, in der das gebaut wird.
- **Kein Ersatz für einen Architektur-Review.** Für `vertraulich`/
  `geheim` + Grad ≥ 4 ist ein unabhängiger Review der
  Netzwerk-Architektur Pflicht, nicht optional.

---

*Stand: 2026-10-11 · Quellen: `packages/gradbuild/gradbuild/validate.py`
(GB-01…16), `docs/technologie-stack.md` (Souveränität, Deployment),
`docs/grad4-5-multiagent-design.md` (Grad 4/5 Architektur),
`docs/souverainetaet-schweiz.md` (DSG, AI Act, Digital Omnibus),
Exoscale (CH-ZH-1/CH-GVA-2/CH-DK-2, GPU A30/A40/A5000),
Infomaniak (Genf/Lausanne, Swiss Cloud). Kein Rechtsrat.*
