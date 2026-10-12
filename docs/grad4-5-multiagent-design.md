# Design: Multi-Agent-System — Grad 4 (Agent) und 5 (Multi-Agent)

> **Stand:** 2026-10-11 · **Repo:** `GRADweight/gradautonomy`
>
> **Status: Entwurf (Soll), nicht Code.**
> Diese Seite definiert den Entwurf eines Grad-4/5-Systems: das Agenten-Team,
> die Kontrolllogik, das Monitoring und die Interoperabilität (A2A/MCP).
> Was als «geliefert» markiert ist, steht in `packages/gw_core/` mit Tests;
> die Deployment-Bausteine (Orchestrator, Klassifikator, MCP-Server) sind in
> diesem Repo bewusst nicht Code — siehe die Zuordnung in §5. Das ist die
> ehrliche Grenze aus `docs/roadmap-grad-03-05.md` §2.3.
>
> **Referenzfälle:** `examples/gw4-c-teile-nachbestellen.json` (Grad 4),
> `examples/gw5-standardretouren.json` (Grad 5). Ein Team, zwei Grade:
> Grad 4 ist die reduzierte Form desselben Systems.

---

## 0 · Welche autonomen Aktionen muss das System können

Bevor es ein Team gibt: die Liste dessen, was das System **autonom** tut.
Jede Aktion wird einer GB-Regel und einem Zustand zugeordnet — wer die
Aktion trägt, steht in §1.

| # | Autonome Aktion | Was sie technisch heisst | GB-Referenz | State |
|---|---|---|---|---|
| **A1** | Fall annehmen und strukturieren | Eingangs-Daten gegen das Grad-Schema prüfen, Mandats-Limits aus `governance`-Feld laden | — (Grundlage) | geliefert (Schema + Validator) |
| **A2** | Fremdtext klassifizieren (Grad 5) | Kundentext → striktes strukturiertes Schema; **tool-freies** Modell, das Ergebnis darf kein Freitext sein | GB-05 (Kundentexte isoliert) | Entwurf (diese Doku) |
| **A3** | Entscheid vorschlagen | Eine konkrete Aktion: Ziel-System, Parameter, Betrag, Währung — nie «kann» oder «vielleicht» | GB-08 (Mandat-Limits im System) / GB-09 (money_limit) | Entwurf (diese Doku) |
| **A4** | Vorschlag validieren | zuerst deterministische Regeln (Limits, Währung, Pflichtfelder), dann Zweitmodell-Plausibilität | — (Design-Prinzip; die Qualität misst GB-14) | `pruefe_antwort` geliefert (G1/2), Critic = Entwurf |
| **A5** | Ausführen (kontrolliert) | Schattenlauf zuerst; nur bei PASS + Limits greifen Snapshot + Write | GB-13 (shadow_run_first + proposal_mode_first) | `RollbackManager` geliefert, Adapter = Deployment |
| **A6** | Ausnahmen gliedern | Schwellenriss, Limit verletzt, nicht-reversibel → deterministisch ausgliedern an einen Menschen | GB-11 (exception_queue + audit_log) | `ExceptionQueue` geliefert (13 Tests) |
| **A7** | Rückrollen | Vorher/Nachher-Snapshot, deterministischer Reversal-Befehl, append-only Ausführen | GB-12 (automatic_rollback + kill_switch_tested) | `RollbackManager` geliefert (14 Tests) |
| **A8** | Belegen und messen | Sampling, KPI, Eskalation — ohne Content-Entscheid | `sampling_audit` | `SamplingAudit` geliefert (8 Tests) |

**Faustregel:** A2 und A3 sind die zwei Bausteine, die noch nicht existieren
(Roadmap §2.3). A1, A4 (Teil), A5 (Teil), A6, A7, A8 sind schon Code. Der
Rest dieser Doku ist die Architektur **um** diese zwei Lücken herum.

---

## 1 · Das Team

> Zuordnung zu den Standard-Rollen: *Evaluator* = Klassifikator + Critic,
> *Executor* = Executor, *Planner* = Entscheider. «System-Prompt-Fokus»
> heisst: was dieser Agent im Prompt **darf und muss** — nicht das, was er
> sein «könnte».

| Rolle | Grad 4 | Grad 5 | Kernkompetenz & System-Prompt-Fokus | Benötigte Tools & APIs |
|---|---|---|---|---|
| **Orchestrator** (Koordinator) | ja | ja | Deterministische Phasen-Kontrolle, Budget-Checks, Ausnahmepfad-Verdrahtung. **Keine Content-Entscheide.** Prompt-Fokus: «Du routest Fälle. Du bewertest nichts. Du gibst nichts frei.» | Keine fremden APIs — nur `gw_core`-Bausteine (Queues, State, Budget) |
| **Klassifikator** (Evaluator, Text) | — | ja | Kundentext → ein striktes Structured-Schema (Retour-Typ, Zustand, beantragter Betrag, fehlende Felder markieren statt raten). **Null Tools** — das ist keine Einschränkung, sondern die Kontrolle (GB-05). Null Freitext-Output: jedes Feld gefüllt oder als `fehlt` markiert. | **Keine** (tool-frei ist der GB-Zwang) |
| **Entscheider** (Planner) | ja | ja | Aus strukturierten Daten **einen** Vorschlag: Aktion, Zielsystem, Parameter, Betrag, Währung — und explizit, welches systemseitige Limit er sich zu eigen macht. Prompt-Fokus: «Nenne immer das Limit, das deinen Betrag deckt. Kein Vorschlag ohne.» | ERP-Lesezugriff (Aufträge, Retouren, Bestände, Preise), CRM-Lesezugriff (Fall-Historie) — je ein MCP-Server, **read-only** (§4.2) |
| **Critic** (Validator) | ja | ja | Vorschlag prüfen oder ablehnen — **deterministische Regeln zuerst** (Limit, Währung, Pflichtfelder, Reversibilität), Zweitmodell-Plausibilität danach. Output ist immer ein strukturiertes Urteil mit Gründen, nie Prosa. Prompt-Fokus: «Du bist das einzige Tor. Ein PASS ohne Regelterminierung ist ein Fehler.» | Validierung (gradbuild CLI), Regel-/Referenzdaten (Schemas, Limits) — via MCP, read-only |
| **Executor** | ja | ja | Den **genau validierten** Vorschlag über die Zielsystem-Schnittstelle ausführen; Snapshot vorher/nachher; Schattmodus = garantiert kein Write. Prompt-Fokus: «Du führst aus, was VALID war. Nicht mehr, nichts anderes.» | Zielsystem-APIs (ERP/EDI, Buchhaltung: Bexio-/Sage50-Muster) — ein MCP-Server **pro Zielsystem**, mit `pre_check` und Modus-Parameter (shadow/production) |
| **Observer** (Betrieb) | ja | ja | Sampling ziehen, KPI berechnen, Schwellenüberschreitungen an Menschen eskalieren. **Kein Content-Entscheid, kein Neustart-Entscheid.** | Audit-DB (SQLite, `AuditTrail`), KPI-Export |

Notizen:

- **L4 vs L5:** Der Klassifikator existiert nur, wenn fremder Text in den
  Fall fliessen kann (gw5) — gw4 (`foreign_input=false`) hat ihn nicht.
  Der Rest des Teams ist identisch. Das ist der Punkt, den «wenn möglich
  auf 4» braucht: ein Entwurf, der für beide Grade gilt.
- **Geldentscheide laufen nie durch ein Prompt, sondern durch
  systemseitige Limits** (GB-08: `mandate.limits_in_system`; bei
  money_effect zusätzlich GB-09: `mandate.money_limit` — beide in
  gw4/gw5 gesetzt). Kein Agent «entscheidet über Geld» — er schlägt vor,
  das System deckelt.
- **Kein Agent sieht den Prompt eines anderen.** Kommunikation zwischen
  Rollen läuft über den State (§2.3) und strukturierte Übergabe-Objekte —
  nie via freiem Text (das ist dieselbe Grenze, die A2A in §4 zieht).

---

## 2 · Kontrolllogik

### 2.1 Zyklisch (LangGraph) oder rollen-basiert sequenziell (CrewAI)

**Entscheid: zyklischer State-Graph — das LangGraph-Muster.** Vier Gründe:

1. **Der Entscheid-Kreislauf ist ein Zyklus mit Abbruchbedingung.**
   Entscheider → Critic → (bei FAIL) zurück zum Entscheider. Bei einem
   Rollensequenzmodell (CrewAI-Crews, sequenziell oder hierarchisch) liegt
   die Zustandsübergabe in der LLM-Ausgabe zwischen den Rollen; ein
   Rücksetz-Zyklus mit deterministischer Runden- und Budgetzählung ist
   dort eine Umgebungs-Konstruktion, keine Kernabstraktion (CrewAI-Flows
   erlauben zwar eventgesteuerte Graphen — sie machen State und Guards
   aber nicht zum primären Konstrukt).
2. **Der Ausnahmepfad ist eine deterministische Kanten-Entscheidung**
   (Limit verletzt, nicht reversibel, Schwellenriss). State-Graphs haben
   *conditional edges* und Max-Iterationen als Kernkonstrukt; ein
   Rollen-Durchlauf hat beides weniger explizit. `ExceptionQueue`
   (geliefert) ist genau eine solche deterministische Kante (GB-11).
3. **Der State überlebt Agenten- und Neu-Läufe** (SQLite, auditierbar).
   Das explizite gemeinsame State-Objekt ist bei einem Graph die
   Architektur, bei Rollen-Hand-off nur die Übergabe-Nebeneffekt
   (GB-11/GB-12: Audit + Identität sind Pflicht).
4. **Repo-Prinzip:** kontrollierbare, deterministische Control-Flow,
   kein Framework-Fetisch (CONTRIBUTING, Roadmap §2.3).
   **Wichtig: entschieden ist das Kontrollmodell** (expliziter State,
   Conditional Edges, Max-Iterationen) — *nicht* die Bibliothek. Wer das
   Deployment baut, darf jede Runtime wählen, die dieses Modell klar
   abbildet; LangGraph tut das als Kernkonzept und ist deshalb genannt.

> Gegenargument, das man sich vorwerfen lassen muss: L4 (gw4) ist fast
> eine strikte Pipeline — dort würde ein Sequenzmodell auch durchlaufen.
> Aber dasselbe System soll L5 (gw5) tragen, und dort dominiert die
> Zyklus-Plus-Ausnahme-Struktur. Eine Kontrolllogik für beide Grade ist
> billiger als zwei.

### 2.2 Workflow-Graph (textbasiert)

```
START (Fall; modus ∈ {shadow, production} — unveränderlich, pro Fall)
 │
 ├─[L5] KLASSIFIKATOR: Fremdtext → strukturierte Felder
 │         (fehlende Pflichtfelder → AUSNAHME)
 ├─[L4] übersprungen (gw4: foreign_input = false)
 ▼
 ┌────────── LOOP  ·  Guard: critic_rounds ≤ 2, sonst AUSNAHME ──────────┐
 │   ENTSCHEIDER ─► Vorschlag {aktion, zielsystem, parameter, betrag}     │
 │        │                                                              │
 │        ▼                                                              │
 │   CRITIC: 1) deterministische Regeln   2) Zweitmodell                 │
 │        │                                                             │
 │        ▼ PASS                                                        │
 │   PRE-CHECK: Mandats-Limits · Währung · Pflichtfelder                │
 └────┬───────────────────────────────────────────────────────────────────┘
      │ PRE-CHECK OK
      ▼
   EXECUTOR: Snapshot (vorher/nachher) → Write      (modus=shadow ⇒ kein Write)
      │
      ▼
   OBSERVER: Sampling · KPI · Eskalation
      │
      ▼
   ENDE (status · audit-refs · fingerprint)
```

Jede Kante, deterministisch (die Graph-Logik in Worte):

| # | Von | Bedingung | Nach | GB-Hintergrund |
|---|---|---|---|---|
| 1 | START | `level=5` | Klassifikator | — |
| 2 | START | `level=4` | Entscheider (Klassifikator übersprungen) | — |
| 3 | Klassifikator | Pflichtfelder fehlen | **AUSNAHME** | GB-05 (strukturiert, keine Raten) |
| 4 | Entscheider | — | Critic | GB-08/GB-09 (Vorschlag trägt Limit) |
| 5 | Critic | `PASS` | Pre-Check | — |
| 6 | Critic | `FAIL` **und** `critic_rounds < 2` | **Entscheider** (neuer Vorschlag) | Loop-Guard |
| 7 | Critic | `FAIL` **und** `critic_rounds = 2` | **AUSNAHME** | Loop-Guard, GB-11 |
| 8 | Pre-Check | Limits/Währung/Pflichtfelder OK | **Executor** | GB-08 (Limits im System) |
| 9 | Pre-Check | verletzt | **AUSNAHME** | GB-08/GB-09 |
| 10 | Executor | `modus=production` | Zielsystem-Write + Snapshot | GB-12 (Reversalität, `RollbackManager`) |
| 11 | Executor | `modus=shadow` | *kein* Write, Ergebnis nur protokolliert | GB-13 (`shadow_run_first`) |
| 12 | Observer | KPI-Schwelle verletzt | **AUSNAHME** (Eskalation) | GB-11/GB-14 |
| 13 | AUSNAHME | `mensch_entscheide ≤ 2` | Mensch entscheidet | GB-11 (`exception_queue`) |
| 14 | AUSNAHME | `mensch_entscheide > 2` | `status=abgebrochen` | Loop-Guard |

**Konsistenz:** `modus` ist der eine Begriff durch die ganze Doku — im
State-Objekt, im Graph und in der Card (`"modus": "shadow"`).

### 2.3 State-Objekt

Welche Daten müssen für die ganze Lebensdauer gemessen werden? Genau die,
die den fünf Audit-Fragen antworten: *was wurde entschieden, von wem, mit
welcher Autorität, mit welcher Wirkung, und hat es ins Budget gepasst?*

```python
@dataclass
class FallZustand:            # Pseudocode — nicht Repo-Code
    # Identität
    fall_id: str              # uuid4, stabil über die ganze Lebensdauer
    level: int                # 4 | 5
    use_case: str             # "c-teile" | "standardretouren" | …
    # Phase & Status
    phase: str                # intakt|klassifiziert|vorschlag|geprueft|freigegeben|
                              # ausgefuehrt|ausnahme|zurueckgerollt|erledigt
    status: str               # laufend|abgeschlossen|abgebrochen|ausnahme
    modus: str                # shadow | production   (unveränderlich pro Fall)
    # Inhalt (nur strukturiert — roher Fremdtext bleibt im Audit-Store)
    strukturierte_falle: dict
    text_hash: str            # Hash über den klassifizierten Input (Spur, kein Volltext)
    vorschlag: dict | None    # {aktion, zielsystem, parameter, betrag, waehrung}
    pruefung: list[dict]      # [{runde, resultat, grund}]  — ein Eintrag je Critic-Runde
    # Autorität (systemseitig, NIEMALS im Prompt)
    mandats_limits: dict      # {money_limit, erlaubte_systeme, waehrung}
    freigaben: list[dict]     # FreigabeEntscheid / ExceptionEntscheid (aus gw_core)
    # Sicherheit & Budget
    zähler: dict              # {llm_calls, tokens, critic_rounds, mensch_entscheide}
    budget: dict              # {max_llm_calls: 8, max_tokens: 150_000,
                              #  zeit_s: 600, critic_rounds_max: 2,
                              #  mensch_entscheide_max: 2}
    kill_state: bool          # True wenn Kill-Switch ausgelöst (GB-12)
                              # — systemseitig, nicht im Prompt
    # Beleg
    snapshots: dict           # {vorher: ref, nachher: ref}   (RollbackManager)
    audit_refs: list[str]     # ID in der AuditTrail (append-only)
    fingerprint: dict         # {model_id, prompt_hash, tool_list_hash} → Re-Validierungs-Trigger
```

Zwei bewusste Abwesenheiten: kein roher Kundentext (bleibt im Audit-Store
mit Access-Level, im State steht `text_hash`), und keine «freien»
Freigabe-Bemerkungen (stehende Entscheidungs-Objekte aus `gw_core`). Alles
andere ist eine Antwort auf eine der fünf Fragen.

---

## 3 · Monitoring (das System handelt autonom)

### 3.1 Striktes Tracing: welche Schritte, was wird protokolliert

Grundlage ist geliefert: `Tracer` (Ereignisreihenfolge) und `AuditTrail`
(append-only, exportierbar). Die Tabelle sagt, was in L4/5 strikt ist und
warum strikt:

| Schritt | Warum striktes Tracing | Was protokolliert wird | Baustein (State) |
|---|---|---|---|
| **Klassifikator** | Einziger Eingangspunkt für fremden Content — die klassische Injektionsfläche (GB-05) | Volle Eingabe (Fremdtext), Modell-ID + Version, voller Output (Strukturfelder), Hashes beider Seiten | `Tracer` + `AuditTrail` (geliefert) |
| **Entscheider** | Vorschlag mit Geld- und Auswirkung (GB-08/GB-09) | Kontext (die strukturierten Daten, nicht der volle Prompt), voller Output (Aktion, Parameter, Betrag), Loop-Counter bei der Übergabe | `Tracer` + `AuditTrail` (geliefert) |
| **Critic** | Das Urteil ist das einzige Tor — ein falscher PASS ist das hauptsächliche Risiko | Regelergebnisse **je Regelseparat**, Zweitmodell-Output, finales Urteil + Runde | `pruefe_antwort` (geliefert, G1/2), Critic (Entwurf) |
| **Executor** | Einziger Punkt mit **fremder Wirkung** | Pre-Check-Ergebnis, Snapshot vorher/nachher (Ref), Zielsystem-Anteil (maskiert), Modus (shadow/production) | `RollbackManager` (geliefert), Adapter (Deployment) |
| **Orchestrator-Transitionen** | Jede Phasen-Übergang ist eine Entscheidung | von → nach, Grund, alle Zähler, Rest-Budget | `Tracer` (geliefert) |

Regel: **Kein Übergang ohne Audit-Eintrag** — append-only, derselbe
Charakter wie `audit.py`.

### 3.2 Endschleifen: wo sie lauern, und die numerischen Limits

| Risiko | Wie es passiert | Limit (numerisch) | Durchgesetzt durch |
|---|---|---|---|
| **Entscheider ↔ Critic Loop** | Critic verweigert, Entscheider schlägt fast dasselbe erneut vor | `critic_rounds ≤ 2`, dann → AUSNAHME | Counter im State, geprüfter bei jeder Kante (§2.2) |
| **Token-Breakout** | Jede Loop-Iteration verbrennt einen LLM-Call + langen Kontext | `llm_calls ≤ 8` **und** `tokens ≤ 150'000` pro Fall | Budget-Check in jeder Übergang (§2.2) |
| **Wall-Clock-Loop** | Langsames Modell + Retries → Fall läuft stundenlang | `zeit ≤ 600 s` pro Fall, `≤ 120 s` pro Schritt | Timeout → `status=abgebrochen` |
| **Menschen-Feedback-Loop** | Mensch verweigert, System schlägt erneut vor | `mensch_entscheide ≤ 2` pro Fall, danach `status=abgebrochen` | `ExceptionQueue` (geliefert) |
| **Schatten/Produktion-Flattern** | Modus während einem laufenden Fall wechseln | `modus` unveränderlich, pro Fall | State-Feld, kein Rewrite |
| **Kreuz-Fall-Kopplung** | Sampling-Ergebnis ändert automatische Policy | Kein Selbst-Optimieren — Policy-Change braucht immer einen menschlichen Entscheid + Re-Validierung (`decides_new`) | Entwurfsregel (§3.3) |

Alle Limits sind **systemseitig** im State — nicht im Prompt. Dieselbe
Logik wie GB-08 (Limits wohnen im Zielsystem, nicht im Prompt) und GB-12
(Rückstufung greift technisch). Die Ziffern sind Kalibrierwerte für die
Use-Case gesetzt und sind keine universellen Konstanten.

### 3.3 KPIs: was gemessen wird

| KPI | Definition | Beispiel-Schwelle (Kalibrierung) | Wer alarmiert wird |
|---|---|---|---|
| **Latenz** | p50/p95 je Schritt + gesamt pro Fall | p95 ≤ 600 s | Observer → Incident-Log |
| **Token-Menge** | Prompts + Completion pro Fall (Kosten hängen am Deployment — deshalb Tokens, nicht CHF) | ≤ 150'000 | Budget-Alarm (→ AUSNAHME) |
| **Tool-Erfolgsrate** | MCP- / Tool-Calls OK im ersten Versuch / gesamt | ≥ 95 % (Trend) | Observer |
| **Erstvalidierungsrate** | Vorschläge, die in der ersten Critic-Runde PASS | ≥ 80 % (abfallend = Drift beim Entscheider oder bei der Regelsetzung) | Observer |
| **Ausnahmequote** | Fälle → `ExceptionQueue` / alle Fälle | abnehmender Trend; plötzliches Ansteigen = Abbruch + Analyse | Observer → Mensch |
| **`adoption_rate`** | (GB-Feld in allen L4/5-Fällen: `adoption_rate_monitored=true`) | überwacht, je Fall kalibriert | KPI-Report |
| **Rollback** | Anzahl, erfolgreich/fehlgeschlagen | 0 Fehl | Incident-Log |
| **Sampling-Compliance** | geprüfte Entscheidungen ≥ gesetzte Sample-Rate | 100 % der gesetzten Rate | `SamplingAudit`-Report |

Jede KPI-Schwelle überschreitet zu einem **Menschen** (ExceptionQueue),
niemals zu einem Modell. KPI- und Sampling-Logik sind bereits der
gelieferte `SamplingAudit` + die KPI-Counter der `ExceptionQueue`.

---

## 4 · Interoperabilität — A2A (Agent↔Agent) und MCP (Agent↔Tool)

**Stand (verifiziert am 2026-10-11):** A2A und MCP sind *komplementäre*
Standard — beide unter der Linux Foundation (Agentic AI Foundation):
MCP = Agent-zu-Tool, A2A = Agent-zu-Agent.
(Quelle: `a2a-protocol.org`, `modelcontextprotocol.io`; Zugriff 2026-10-11.)

- **A2A**: erste stabile Spezifikation **v1.0 (12.03.2026)** mit
  Signed Agent Cards, Multi-Protocol; davor **v0.3** (JWS-Signierung der
  Cards, gRPC). (Quelle: LF/AAIF-Ankündigung 04/2026 + a2a-protocol.org.)
- **MCP**: Spezifikation **2026-07-28** (stateless Kern,
  `InputRequiredResult`), Transport stdio (lokal) und Streamable HTTP
  (remot). (Quelle: modelcontextprotocol.io.)

### 4.1 Die Agent-Card (Haupt-Agent)

Die Card liegt als maschinenlesbares Artefakt im Repo:
[`governance/a2a-agent-card.json`](../governance/a2a-agent-card.json)
(Schema v0.3; die v1.0-Äquivalenz über `supportedInterfaces` gilt für die
Registry-Integration, §6 Punkt 4).

```json
{
  "protocolVersion": "0.3",
  "name": "gradautonomy-entscheider",
  "description": "Kontrollierte Entscheide für Grad-4/5 Prozessfälle (z. B. C-Teile-Nachbestellungen, Standard-Retouren): strukturierter Vorschlag, Validierung durch deterministische Regeln und Zweit-Modell, limit-geprüfte kontrollierte Ausführung (Schattenlauf zuerst). Fremder Kundentext gelangt nicht in den Entscheid — er wird von einem tool-freien Modell vorklassifiziert (GB-05). Geldentscheide nur innerhalb systemseitiger Mandats-Limits (GB-08/GB-09).",
  "url": "https://agent.example.com/a2a/v1",
  "provider": {
    "organization": "GRADweight GmbH",
    "url": "https://gradweight.ch"
  },
  "version": "1.0.0",
  "documentationUrl": "https://github.com/GRADweight/gradautonomy/blob/main/docs/grad4-5-multiagent-design.md",
  "capabilities": {
    "streaming": false,
    "pushNotifications": true,
    "stateTransitionHistory": true
  },
  "securitySchemes": {
    "oidc": {
      "type": "openIdConnect",
      "openIdConnectUrl": "https://auth.example.com/.well-known/openid-configuration"
    }
  },
  "security": [
    { "oidc": ["case:decide", "case:classify", "audit:read"] }
  ],
  "defaultInputModes": ["application/json"],
  "defaultOutputModes": ["application/json"],
  "skills": [
    {
      "id": "case-decide",
      "name": "Fall entscheiden (Grad 4/5)",
      "description": "Nimmt einen strukturierten Fall (gradbuild-Schema Grad 4/5) an, erzeugt einen validierten Aktions-Vorschlag und führt aus, sofern die systemseitigen Limits greifen — Modus `shadow` (kein Write) oder `production`. Kein Freitext für den Entscheid.",
      "tags": ["autonomy", "governance", "kmu", "gb-09"],
      "examples": [
        "{\"fall_id\": \"ct-2026-0117\", \"level\": 4, \"use_case\": \"c-teile-nachbestellen\", \"strukturiert\": {\"artikel\": \"C-0042\", \"menge\": 200, \"betrag\": \"CHF 1'480.00\"}, \"modus\": \"shadow\"}"
      ],
      "inputModes": ["application/json"],
      "outputModes": ["application/json"]
    },
    {
      "id": "case-classify",
      "name": "Kundentext vorklassifizieren (GB-05)",
      "description": "Klassifiziert einen freien Kundentext in ein striktes strukturiertes Schema (Retour-Typ, Zustand, beantragter Betrag, fehlende Felder). Tool-freies Modell: der Text selbst erreicht den Entscheid nie, nur das strukturierte Ergebnis.",
      "tags": ["classification", "gb-05", "foreign-input"],
      "examples": [
        "Kundentext: 'Bei der Rücksendung war alles beschädigt. Ich erwarte eine Gutschrift.' → {\"retour_typ\": \"beschädigt\", \"antrag\": \"gutschrift\", \"betrag\": null, \"fehlt\": [\"betrag\"]}"
      ],
      "inputModes": ["text/plain", "application/json"],
      "outputModes": ["application/json"]
    },
    {
      "id": "audit-read",
      "name": "Audit-Beweiskette abfragen",
      "description": "Lese-Zugriff auf den Beweiskette eines Falls: Entscheide, Freigaben, Snapshot-Vorher/Nachher, Ausnahmen, KPI-Counter. Append-only, keine Änderungen.",
      "tags": ["audit", "governance", "read-only"],
      "examples": [
        "Beweiskette für Fall ct-2026-0117, inklusive Exception-Ereignisse"
      ],
      "inputModes": ["application/json"],
      "outputModes": ["application/json"]
    }
  ]
}
```

**Lesart — die drei expliziten Fragen aus dem Entwurf:**

- **Capabilities (Fähigkeiten):** `streaming=false` (ein Batch-Entscheid
  genügt, kein Token-Stream), `pushNotifications=true` (Status-Änderungen
  eines Tasks an einen registrierten Webhook — das ist der
  Observation-Kanal), `stateTransitionHistory=true` (wir haben einen
  Audit-Trail und geben ihn).
- **Input-Erfordernisse:** Default ist `application/json` — ein
  Grad-4/5-Entscheid nimmt einen *strukturierten Fall* (Schema: gradbuild).
  Freitext ist **genau eine dedizierte Skill** (`case-classify`), und
  dort gilt GB-05: Ergebnis ist Structured Data, nie der Entscheid.
  `text/plain` taucht deshalb nur bei `case-classify` in `inputModes`
  auf, nicht im Default.
- **Authentifizierung:** OIDC mit Scopes pro Aktion
  (`case:decide`, `case:classify`, `audit:read`) — least privilege
  auf der API-Ebene. Vertrauen in die Card selbst: **Signed Agent Card**
  (JWS, RFC 8785-Canonicalisierung) — eine v0.3/v1.0-Funktion;
  ohne Signatur wird eine Card nicht angenommen.
  **Zuordnung ins Repo:** dies ist die Deployment-Form von
  `agent_identity_min_privilege` (Roadmap §2.2, offen als Code-Baustein) —
  die Card deklariert öffentlich, was die Identität darf; die
  `FreigabePolicy` erzwingt es intern.
- **`url` und `openIdConnectUrl`** sind Platzhalter (Konvention der
  A2A-Spezifikation) und müssen vor jeder Veröffentlichung gegen
  Deployment-Werte ausgetauscht werden. Die Card im Repo enthält bewusst
  **kein** `signature`-Feld: die Signatur (JWS über die canonicalisierte
  Card, RFC 8785) wird im Deployment erzeugt und kann hier nicht
  vorweggenommen werden. Ein Client, der Cards ohne Signaturprüfung
  konsumiert, ist nicht produktionsreif.

### 4.2 MCP: wie Datenquellen und Sandboxes angebunden werden

Prinzip: **Jedem Agent-Rolle ein eigener, enger MCP-Server** — es gibt
keinen «alles-Tools»-Server. Das ist `agent_identity_min_privilege` in
der Tool-Ebene:

| Agent | MCP-Server | Tools (min.) | Transport |
|---|---|---|---|
| Klassifikator | **keiner** (GB-05) | — | — |
| Entscheider | `erp-lesen`, `crm-lesen` | `auftrag_lesen`, `retoure_lesen`, `preis_lesen`, `fall_lesen` (nur lesen) | stdio (lokal) · Streamable HTTP (remot) |
| Critic | `regelwerk` | `fall_validieren` (gradbuild-CLI), `regel_holen` | stdio |
| Executor | `zielsystem` (einer je Zielsystem) | `vorher_snapshot`, `ausfuehren(modus)`, `nachher_snapshot` — `ausfuehren` hat `modus`-Parameter: `shadow` = garantiert kein Write | lokal, hinter `pre_check` |
| Observer | `audit` | `events_lesen`, `kpi_berechnen` (read-only) | stdio |

**Sicherheitsregeln (Reihenfolge):**

1. **Credentials wohnen in der MCP-Server-Schicht** (OAuth2-Token-Broker)
   — nie im Agent-Kontext, nie im LLM-Prompt. Das Modell sieht nur die
   Tool-Schemas, nie ein Token.
2. **Schattmodus ist strukturell:** im Schattmodus sind Write-Tools im
   `zielsystem`-Server nicht exponiert — keine externe Wirkung, nicht
   «das Modell hat zugesagt, es würde keine».
3. **Sandbox:** der Executor läuft in einer isolierten Umgebung ohne
   direkten DB-Zugriff — sein einziger Weg nach aussen ist der
   `zielsystem`-MCP-Server. Ein kompromittierter Agent erreicht das ERP
   nicht über einen zweiten Weg.
4. **Jeder Tool-Call = ein Audit-Eintrag** (actor = Agent-Rolle, Tool,
   Input-Hash, Output-Hash, Modus) — `AuditTrail` (geliefert),
   append-only.
5. **Kein Secret in der Tool-Beschreibung:** MCP-Server können Input
   *anfragen* (Spec 2026-07-28: `InputRequiredResult`) — das Secret wird
   vom Deployment geliefert, nicht aus dem Gespräch.

```
Entscheider ──MCP──► erp-lesen  ─►  ERP (read)
Critic      ──MCP──► regelwerk  ─►  gradbuild-CLI
Executor    ──MCP──► zielsystem ─►  ERP/EDI/Buchhaltung (write, nach pre_check, schatten-fähig)
Observer    ──MCP──► audit      ─►  SQLite (AuditTrail)
Klassifikator: keine MCP (tool-frei = die Kontrolle)
```

---

## 5 · Zuordnung auf die gelieferten Bausteine (die ehrliche Tabelle)

| Entwurfselement (diese Seite) | Im Repo (geliefert) | Im Deployment zu stellen |
|---|---|---|
| Ausnahmepfad (§2.2, §3.2) | `ExceptionQueue` + `ExceptionPolicy` (13 Tests) | — |
| Sampling & Reporting (§3.1, §3.3) | `SamplingAudit` (8 Tests) | — |
| Rollback (§2.2, §3.1) | `RollbackManager` (14 Tests) | Host-Adapter (Zielsystem-Call) |
| Audit & Tracing (§3.1) | `AuditTrail`, `Tracer` | — |
| Authorization (Grundlage) | `FreigabePolicy`, `ApprovalQueue` (L1/2-Freigabe) | OIDC/Entra-Identität (Roadmap §2.2) |
| Zweitmodell-Prüfung (L1/L2) | `pruefe_antwort` | — |
| **Orchestrator** (§1, §2) | ❌ Entwurf (diese Seite) | Graph-Runtime (LangGraph oder Äquivalent) |
| **Text-Klassifikator** (GB-05) | ❌ Entwurf (diese Seite) | Tool-freies Modell |
| **MCP-Server** (§4.2) | ❌ Entwurf (diese Seite) | Zielsystem-APIs + Server |
| **A2A-Endpunkt** (§4.1) | ✅ Card (`governance/a2a-agent-card.json`) | A2A-Server + Card-Signierung |
| **Agent-Identität** (Service-Konto) | ⬜ Roadmap §2.2 (offen) | Entra Agent ID / Service-Konto |

---

## 6 · Offene Punkte (mit Quelle)

1. **Orchestrator-Runtime-Wahl** — das Muster ist hier festgelegt
   (§2.1), die Bibliothek ist nicht. Kandidat: LangGraph (passt
   State + Conditional Edges + Max-Iterationen). Vor dem Bauen zu
   entscheiden. (Quelle: §2.1, Roadmap §2.3)
2. **Text-Klassifikator: welches Modell?** — die tool-freie-Erfordernis
   ist fix (GB-05), das Modell (lokal Ollama oder Cloud) hängt an der
   Souveränität des Deployments (Quelle: §1, `technologie-stack.md` §3).
3. **Budget & Schwellen** — die Ziffern in §3.2/3.3 sind Kalibrierwerte;
   sie müssen pro Referenzfall mit Golden-Sets gesetzt werden
   (Roadmap §2.3: pass^k-Testsatz 30–50 echte Fälle).
4. **A2A-v1.0-Migration** — die Card im Repo ist v0.3; die Registry
   unterstützt beide (v1.0: `supportedInterfaces`). Vor Produktion:
   Version pinnen + Migrationspfad dokumentieren. (LF-Ankündigung 04/2026)
5. **Card-Signatur** — v0.3 erlaubt `signature`, v1.0 erwartet sie;
   ein Client ohne Signaturprüfung ist nicht produktionsreif. (Doku §4.1)
6. **Agent-Identität / Service-Konto** — noch offen als Code (Roadmap
   §2.2); die Card (§4.1) ist nur die öffentliche Deklaration.
7. **`kill_switch_tested`** — das Flag steht in den JSONs (gw4/gw5); ein
   *getesteter* Kill-Switch ist im Deployment noch ausstehend
   (Roadmap §2.3 Grad 03: «heute nur ein Flag im JSON»).

---

*Stand: 2026-10-11 · Quellen: `examples/gw4-c-teile-nachbestellen.json`,
`examples/gw5-standardretouren.json`, `docs/roadmap-grad-03-05.md`
(§2.2/2.3), `docs/technologie-stack.md`, `packages/gw_core/`,
A2A-Spezifikation (a2a-protocol.org, v0.3/v1.0), LF/AAIF-Ankündigung
(04/2026), MCP-Spezifikation (2026-07-28, modelcontextprotocol.io) —
Zugriff 2026-10-11. Kein Rechtsrat.*
