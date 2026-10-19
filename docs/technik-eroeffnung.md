# Weitere technische Möglichkeiten (Technik-Eröffnung)

> **Stand:** 2026-10-11 · **Repo:** `GRADweight/autonomy`
>
> **Status: Entwurf — diese Doku listet keine TODOs, sondern
> bewertete technische Weiterentwicklungen** mit konkretem Aufwand,
> Abhängigkeiten, und dem entscheidenden Punkt: **Repo vs. Mandant**.
>
> Grundlage: `packages/gradbuild/gradbuild/validate.py` (GB-01…GB-16),
> `README.md § 9` (6 bewusst offene Punkte), `packages/gw_core/` (9
> Bausteine), `docs/grad4-5-multiagent-design.md §4/§5` (A2A/MCP-Entwurf),
> `governance/a2a-agent-card.json` (v0.3-Card als Artefakt).

---

## 1 · Was ist hier und was nicht

**Hier:** technische Weiterentwicklungen, die **in diesem Repo**
passieren können, mit geschätztem Aufwand (Personen-Tage, PD),
Abhängigkeiten, und einem klaren «Repo vs. Mandant»-Label.
**Nicht hier:** Preise, Kalkulationen, Kunden-Names.

**Reihenfolge-Grundprinzip:** erst die Punkte, die **existierende
Repos-Punkte** (README §9) direkt abdecken, dann die Punkte, die
**Level 4/5-Deployment** vorbereiten (A2A/MCP, Mandat-Engine), dann
die Punkte, die **neue Repo-Kapazitäten** eröffnen.

---

## 2 · Offene Punkte aus README §9 — jetzt bewertet

| # | Punkt (README §9) | Aufwand (PD) | Abhängigkeiten | Repo vs. Mandant |
|---|---|---|---|---|
| **R1** | **Release-Prozess-Definition**: `CHANGELOG.md`, Release-Notes-Format, `vX.Y.Z`-Tag | 1 PD | — | **Repo** (direkt, kein Mandanten-Kopplung) |
| **R2** | **JSON-Schema-Export**: `gradbuild/schema.json` (JSON-Schema 2020-12), Editor-Validierung | 2 PD | `schema.py` ist **single Source of Truth** (wichtig, nicht doppelte Definition) | **Repo** (`gradbuild/schema.json`), Mandant nutzt es in VS Code |
| **R3** | **i18n**: `--lang en`-Flag, alle Meldungen, Doku, Kommentare zweisprachig | 3–5 PD (je nach Umfang) | `validate.py` ist der Kern (alle Meldungen dort) | **Repo** (Meldungen im Code), **Mandant** (Doku/Übersetzung im Einsatz) |
| **R4** | **Audit-Trail-Export `--json`**: `validate.py` schreibt JSON-Report (statt nur stdout) | 1 PD | `validate.py` (CaseReport-Struktur ist ** schon JSON-ready**) | **Repo** (CLI-Flag), **Mandant** (nutzt es im Audit-System) |
| **R5** | **Mandat-Engine**: echte Validierung gegen Zielsystem (ERP-API), nicht nur `limits_in_system=true` | 5–10 PD | `bexio.py` ist die **Referenz** (httpx-Client, Dry-Run); `mandate.money_limit` ist **String** im JSON → **typisierte** Mandat-Struktur nötig | **Repo** (Validierungs-API), **Mandant** (ERP-Anbindung, Limits) |
| **R6** | **CI-Matrix 3.10/3.11**: `requires-python >= 3.9` deklariert, CI testet nur 3.11/3.12 | 0.5 PD | — | **Repo** (CI-Geschärft, kein Mandanten-Kopplung) |

**Aufwands-Summe (R1–R6):** ~12.5–17.5 PD, davon **alle im Repo**
(keiner davon ist reine Mandanten-Aufgabe).

---

## 3 · Neue Kapazitäten — Level 4/5-Deployment vorbereiten

### 3.1 Mandat-Engine (R5, aus README §9) — die **eigentliche** Level-4/5-Schicht

**Was fehlt heute:**
- `mandate.limits_in_system=true` wird **nur** auf `true` geprüft (GB-08),
  nicht auf **korrekte Implementation**.
- `mandate.money_limit` ist ein **String** im JSON (z. B.
  `"CHF 2000 pro Bestellung"`), nicht eine **typisierte Struktur**.
- Es gibt **keine** API, die die Mandat-Limits gegen ein Zielsystem
  (ERP/EDI) **praktisch validiert** — die `bexio.py`-Referenz zeigt
  den Pfad, aber es ist **kein generischer** Mandat-Validator.

**Was gebaut werden sollte (im Repo):**
1. **Typisierte Mandat-Struktur** — `mandate` wird ein **Dict mit
   festen Schlüsseln** (`money_limit: Decimal`, `recipient_scope: list[str]`,
   `time_window: str`, `limits_in_system: bool`), nicht ein freier String.
   `schema.py` prüft die Struktur, `validate.py` prüft die **Werte**.
2. **Mandat-Validator** — eine `gw_core.mandate.MandateValidator`:
   - **Punkt 1:** `limits_in_system=true` → **Pflicht** (GB-08, `error`).
   - **Punkt 2:** `money_limit` → `Decimal` (nicht String), `> 0`.
   - **Punkt 3:** `recipient_scope` → nicht leer, **whitelist** (Leitplanke).
   - **Punkt 4:** `time_window` → z. B. `ISO 8601` oder `daily/weekly`.
   - **Punkt 5:** **Zielsystem-Konnectivität** — `bexio.py` (httpx-Client)
     validiert: «kann das Zielsystem diese Limits durchsetzen?»
     (Dry-Run, **keine** echte Aktion).
3. **Mandat-API im CLI** — `python -m gradbuild.cli --mandate-validate
   <case.json> --system bexio` → validiert die Mandat-Limits gegen
   das Zielsystem (Dry-Run) und meldet `ok` oder `fail` (mit
   **grund**).

**Aufwand:** 5–10 PD (je nach Anzahl Zielsysteme, die unterstützt
werden — `bexio` ist die Referenz, weitere (z. B. SAP, Shopify)
sind **Mandanten-Kopplung**).

**Label:** **Repo** (Validator + Mandat-Struktur), **Mandant**
(Zielsystem-Anbindung, Limits, Scopes).

### 3.2 Kill-Switch-Code (GB-12 «praktisch» umsetzen)

**Was fehlt heute:**
- `kill_switch_tested=true` im JSON wurde **nur** auf `true` geprüft
  (GB-12, `error` bei `false`).
- Es gibt **keinen** implementierten Kill-Schalter im Repo — kein
  Befehl, der ein laufendes Workflow-System **innerhalb von Minuten**
  abschaltet.

**Was gebaut werden sollte (im Repo):**
- **`gw_core.kill_switch.KillSwitch`** — ein **minimaler**,
  **getesteter** Kill-Schalter:
  - `activate()` → setzt einen **Flag** (z. B. in SQLite), der alle
    laufenden Workflows **sofort** stoppt.
  - `deactivate()` → hebt den Flag auf.
  - `status()` → meldt aktiv/inaktiv + Zeitstempel.
  - **Kill-Schalter-Test:** ein Test, der den Kill-Schalter
    **simuliert** (ein laufendes Workflow wird aktiviert, Kill-
    Schalter wird ausgetriggert, Workflow wird **innerhalb von
    10 ms** gestoppt).
- **`gw_core.rollback.RollbackManager`** ist **schon** da (GB-12 «Rollback»);
  die **Verbindung** Kill-Schalter → Rollback ist noch **nicht** im
  Code (Kill-Schalter triggert **automatisch** Rollback, wenn ein
  Schwellenwert verletzt wird).

**Aufwand:** 2–3 PD (Kill-Schalter-Modul + 1 Test + Verbindung zu
RollbackManager).

**Label:** **Repo** (Code + Tests), **Mandant** (Deployment: wer
triggert den Kill-Schalter, in welcher UI).

### 3.3 A2A Agent-Card als **validiertes** Artefakt

**Was fehlt heute:**
- `governance/a2a-agent-card.json` (v0.3) ist ein **statisches**
  JSON Artefakt — es ist **nicht** validiert (kein Schema-Check,
  kein Signatur-Test, kein URL-Placeholder-Check).
- `docs/grad4-5-multiagent-design.md §4` beschreibt die **Anforderungen**
  (OIDC-Scopes, Signed-Card, v1.0-Migration), aber es ist **kein Code**
  im Repo, der das prüft.

**Was gebaut werden sollte (im Repo):**
- **`governance/checks/a2a_card_check.py`** — ein **einfacher**
  Validator für die Agent-Card:
  - `url` + `openIdConnectUrl` → **nicht** `example.com` (Release-Gate).
  - `skills` → nicht leer, jede mit `name` + `description`.
  - `preferredTransport` → `JSONRPC` (v0.3) oder `gRPC` (v1.0).
  - **Signatur:** `signature`-Feld vorhanden, Format `JWS` (v1.0
    Pflicht, v0.3 optional).
- **CI-Integration:** `a2a_card_check.py` in `.github/workflows/ci.yml`
  (neuer Job `gov/a2a-card`).
- **URL-Platzhalter-Check:** `grep -r "example.com" governance/` →
  muss **leer** sein (Release-Gate, `PROJEKT.md` §7).

**Aufwand:** 2–3 PD (Validator + CI-Integration + Doku-Update in
`grad4-5-multiagent-design.md §4`/`§6`).

**Label:** **Repo** (Validator + CI), **Mandant** (Deployment: echte
URLs, OIDC-Provider, Signatur).

### 3.4 Mandant-Deployment-Referenzen (Level 4/5)

**Was fehlt heute (nicht im Repo, aber **wichtig**):**
- Die **praktische** Mandat-Enforcement (ERP/Limits/Scopes) ist **eine
  Mandanten-Aufgabe** (README §9 Punkt 5) — das ist **nicht** ein
  «Schwachpunkt» im Repo, sondern **die Grenze** zwischen Repo und Mandant.
- `gw_core.bexio.BexioZielsystemAdapter` ist die **Referenz** für diese
  Schicht — ein **konkreter Beispiel-Client** (httpx, Dry-Run) für
  Bexio. Andere Zielsysteme (SAP, Shopify, QuickBooks) sind **Mandanten-Kopplung**.

**Empfehlung (Repo):**
- Ein **neues Repo** `gw-zielsysteme` (oder `gw_core`-Erweiterung):
  Mandant-spezifische Adapter (SAP, Shopify, QuickBooks, …) als
  **separate Pakete**, nicht im Core (wie `bexio` ein Adapter ist,
  aber **nicht** im Core).
- `gw_core` bleibt **Zero-Dep** (keine neuen HTTP-Abhängigkeiten im
  Kern — `bexio.py` ist ein Adapter, kein Core-Modul, README §2).

**Aufwand:** 0 PD im `gw_core`-Repo (die Grenze bleibt), ~5–15 PD
je Zielsystem im **neuen** `gw-zielsysteme`-Repo (Mandanten-spezifisch).

**Label:** **Repo** (Grenze + Referenz `bexio.py`), **Mandant**
(eigene Adapter).

---

## 4 · Priorisierung (wenn es eilt)

| Priorität | Punkt | Warum |
|---|---|---|
| **P0** | **R1** (Release-Prozess) + **R6** (CI 3.10/3.11) | 1.5 PD, sofort, alle Repo-Grenzen sauber. |
| **P1** | **R2** (JSON-Schema-Export) + **R4** (`--json`-Audit-Export) | 3 PD, verbessert die **Nutzbarkeit** (Editor-Validierung, Audit-System), kein Mandanten-Kopplung. |
| **P2** | **R5** (Mandat-Engine) + **3.2** (Kill-Switch-Code) | 7–13 PD, **Level 4/5-Vorbereitung** (GB-08/GB-12 praktisch umsetzbar), **wichtig** vor Level 4/5-Deployment. |
| **P3** | **3.3** (A2A-Card-Validator) + **R3** (i18n) | 5–8 PD, **Level 5-Vorbereitung** (Multi-Agent) + **internationale Nutzung**. |
| **P4** | **3.4** (Mandant-Deployment-Referenzen) | **Mandanten-Kopplung**, kein Repo-Punkt (Grenze bleibt). |

---

## 5 · Was bewusst NICHT hier steht (und warum)

- **Preise / Kalkulationen** — gehören in die Mandanten-Kalkulation,
  nicht in das Repo (README §2, `PROJEKT.md` §4 Regel 3: «Preise/
  Kalkulation/Kunden/Secrets: nie ins Repo»).
- **Rechtsrat** — GB-15, DSG, AI Act, Maschinenverordnung sind
  **technische Grenzen** im Validator; die rechtliche Würdigung ist
  eine **Rechtsfrage**, nicht eine Code-Frage.
- **Mandanten-spezifische Deployments** — die **praktische** Mandat-
  Enforcement (ERP/Limits/Scopes) ist **eine Mandanten-Aufgabe**
  (README §9 Punkt 5); `gw_core` ist die **Referenz**
  (Bausteine, Tests, GB-Prüfung), nicht das **Deployment**.

---

*Grundlage: `validate.py` (GB-01…16), `README.md §9` (6 offene Punkte),
`schema.py` (Mandat-Struktur), `bexio.py` (Zielsystem-Referenz),
`gw_core/__init__.py` (9 Bausteine), `docs/grad4-5-multiagent-design.md`
§4/§5 (A2A/MCP-Entwurf), `governance/a2a-agent-card.json` (v0.3-Card).
Keine Preise, kein Rechtsrat.*
