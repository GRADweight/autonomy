# PROJEKT.md — gradautonomy (GRADweight Org, private bis Release)

Single Source of Truth. Jede Sitzung: diese Datei lesen + `git log -10` +
`git status` → Einschätzung an Edin (Ist, offene Punkte, nächste 3 Schritte,
Risiken). Jeder abgeschlossene Schritt SOFORT hier + Commit, vor jeder
Kontextbereinigung.

Stand: 2026-10-11 · Branch-Modell: `feature/<thema>` → Squash nach `main`

---

## 1 · Mandat (entschieden, 2026-10-11)

- **Scope:** AI Governance + AI Engineering, Plan bis Inbetriebnahme, über ALLE
  Autonomiegrade 01–05 (01 Assistent, 02 Copilot, 03 Workflow, 04 Agent,
  05 Multi-Agent). Training bleibt privat, kommt NICHT hierhin.
- **Geliefert:** Grad 01 + 02 nachweisbar (Code + Tests). **Aufgezeigt:**
  Grad 03, 04, 05 als lauffähige, etablierte Beispiele (JSON, validiert mit
  dem gradBuild-Validator inkl. Grenzen und "was fehlt"-Markierung).
- **Lizenz:** MIT.
- **Ort:** `GRADweight/gradautonomy` (Org-Pfad), **private während des Baus**,
  **publiziert nach dem Bau** (Release-Gate in §7).
- **Kern:** Original-Code (`gw_core` 8 Governance-Bausteine + Tests) +
  `gradbuild` (GB-01…16, Validator) — nicht verlinkt, sondern hier drin,
  mit einem lauffähigen Referenzbeispiel (Rechnungs-Extraktion #02).
- **AI-Governance-Modul** (`governance/`): Unternehmen KI-governance-sicher
  machen — mit technischen Mitteln (Policy-as-Code, AuthZ, Audit,
  Injection-/PII-Tests, Grad-Deckel-Validator, Kill-Switch) UND Governance
  (Richtlinie, Register, Rollen, KPI).

## 2 · Quellen (verifiziert am 2026-10-11)

| Quelle | Ort | Was |
|---|---|---|
| gw-core Bausteine | `~/code/gradweight/gw-prototypen/shared/src/gw_core/` | approval, audit, verify, authz, tracing, bexio + Tests; stdlib-basiert (bexio: httpx) |
| gw-core Tests | `~/code/gradweight/gw-prototypen/shared/tests/` | 26 Tests, grün (0.009s) |
| gradbuild | `~/code/gradweight/gradBuild/` | v0.2.0, zero-deps, MIT, 23 Tests+6 Subtests, CLI `gradbuild validate` |
| Autonomie-Mappe | `~/code/gradweight/gw-prototypen/docs/26-autonomie-mappe.md` | Grad 0–5, 3 Erkennungsfragen, harte Grenzen, IST/ZIEL 25 Prototypen, 8 Bausteine |
| 25 Autonomie-Fälle | `~/code/gradweight/gw-prototypen/autonomy/01.json…25.json` | maschinenlesbar, gradBuild-Schema |
| Rechnungs-Extraktion | `~/code/gradweight/gw-prototypen/prototypes/02-rechnungs-extraktion/` | lauffähig + Tests + Evaluierung |
| RAG + Guardrails | `~/code/gradweight/gw-shared-lib/gw_shared_lib/` | rag_core.py, guardrails.py (Injection, PII, Zitat) |
| Gate-Modell | `~/code/gradmap/doku/gate-modell.md` | Tore G0–G8, K.-o.-Kriterien |
| Architektur | `~/code/gradbuild/doku/architektur.md` | Multi-Agent, RAG, Guardrails, Deploy |
| Digital Omnibus | verifizierte URLs (eur-lex, ai-act-service-desk) | VO (EU) 2026/1744, in Kraft 27.07.2026; Anh. III → 02.12.2027, Anh. I → 02.08.2028 |
| DSG CH | fedlex.admin.ch/eli/cc/61/804900 (HTTP 200) | SR 235.1 |

## 3 · Plan (1–2 Wochen, Phasen)

| Phase | Inhalt | Abnahme |
|---|---|---|
| P1 | Repo-Setup: Struktur, MIT, CONTRIBUTING, .gitignore, CI-Gerüst | Repo created (private), first commit |
| P2 | OSS-Kern: `gw_core/` (8 Bausteine + Tests), `pyproject.toml`, Tests grün | `uv run pytest` grün auf main |
| P3 | gradbuild als Workspace-Mitglied (Validator CLI) | `gradbuild validate` läuft auf Beispielen |
| P4 | `examples/`: 01 Assistent, 02 Copilot (lauffähig inkl. #02), 03 Workflow, 04 Agent, 05 Multi-Agent — je JSON + Doku "was fehlt" | alle Beispiele validieren (Exit 0) |
| P5 | Doku `docs/`: plan.md, umsetzen.md, wie.md, abschluss.md, inbetriebnahme.md — je mit Grad-Spalte 01–05 + GB-Regeln + Baustein-Verweis | 5 Dateien, Grad-Spalte vollständig |
| P6 | `governance/`: Technical-Controls (AuthZ-Beispiel, Audit-Beispiel, injection/PII-Check-Script, kill-switch, grad-cek-validator) + Richtlinie/Register/Rollen-Vorlagen | Scripts laufen; Vorlagen vorhanden |
| P7 | Community: .github/ISSUE_TEMPLATE (vorschlag, bericht, doku), CODE_OF_CONDUCT, SECURITY, CI-Workflow mit Badges | PR-Mechanik sichtbar |
| P8 | Release-Gate: Secret/Preis-Scan, LICENSE-Review, Topics, Beschreibung, **public** (Edin-Green-Light) | public, alle Selftests grün in CI |

## 4 · Regeln (verbindend)

- Sprache: Deutsch (CH), «ss», keine Marketing-Begriffe (s. CONTRIBUTING).
- Jede Zahl/Behauptung mit Quelle (Datei/URL + Datum) belegt.
- Preise/Kalkulation/Kunden/Secrets: nie ins Repo.
- `gw_core` + `gradbuild`-Code: nur kopieren aus den verifizierten Quellen;
  keine "Verbesserungen" ohne Edin-OK (das sind andere Projekte).
- Neue Beispielfälle (Grad 3/4/5): nur, wenn der Validator sie annimmt (Exit 0);
  was fehlt, wird als "ZIEL-Grad" gekennzeichnet, nicht als erreicht verkauft.
- Commits: klein, deutsch, mit Beleg. Squash-Merge nach main.

## 5 · Offene Punkte / Entscheide

- [x] Lizenz = MIT (11.10)
- [x] Ort = `GRADweight/gradautonomy` (11.10)
- [x] Publish = nach Bau, nach Edin-Green-Light (11.10)
- [ ] Repo-Namen-Final: "gradautonomy" (Vorschlag) — Edin kann rename vor Public
- [ ] Bexio-Sandbox-Tokens für Live-Durchlauf (fremde Secrets — nie ins Repo)
- [ ] Golden-Set #02: 30–50 echte CH-Belege (heute: Platzhalter-3er)
- [ ] AI-Gov-Modul: FINMA 08/2024 miteinbeziehen? (nur wenn Regulierte)
- [ ] Release-Termin-Punkt: nach P7 oder nach P5?

## 6 · Protokoll

| Datum | Schritt | Verifiziert |
|---|---|---|
| 2026-10-11 | P1: Repo `GRADweight/gradautonomy` (private), Struktur, MIT, LICENSE, PROJEKT.md | gh api + git log |
| 2026-10-11 | P2+P3: OSS-Kern in `packages/` (gradbuild v0.2.0 + gw_core-Subset, 6 Bausteine), 49 Tests + 6 Subtests grün | pytest |
| 2026-10-11 | P4: Beispiele gw0–gw5 im Repo (Level 0–5), alle per `gradbuild.cli` validiert, counterexample korrekt abgelehnt | examples/ |
| 2026-10-11 | P5: Doku je Phase (plan, umsetzen, wie, abschluss, inbetriebnahme) — je Grad 01–05 mit GB-Regel-Matrix | docs/ |
| 2026-10-11 | P6: governance/ (checks + Vorlagen). governance_check.py: **13/13** Checks (Deckel GB-03/06/09/02, Injection DE+EN, Log-PII/Secrets inkl. Telefon-CH und Negativfall) | python3 governance/checks/governance_check.py |
| 2026-10-11 | P7: Community — CI (Tests + Gov-Checks + Validation + counter-example-Verweigerung), 3 Issue-Templates, PR-Vorlage, CODE_OF_CONDUCT, SECURITY, .gitignore | .github/ |
| 2026-10-11 | **Release-Gate abgenommen**: Gate 1/2 (nur Fachdaten, keine Preise/Secrets/echte Tokens), 3 (49+6 grün), 4 (6/6 validiert, counter abgelehnt), 5 (ruff clean nach 3 echten Fixes + ruff-Konfig, verifizierte Quellen via per-file-ignores), 6 (README: Rechtsrat/Grenzen/Stand) |pytest+gov-check+ruff |
| 2026-10-11 | **PUBLIK** (Edin-Green-Light): `gh repo edit --visibility public`, Description + 8 Topics, HTTP 200 auf Repo + raw README | gh api + curl |
| 2026-10-11 | CI-Fehler gefixt: `datetime.UTC` (Python 3.11+) → requires-python >=3.11, CI-Matrix 3.11/3.12 → **CI grün (both jobs)** | gh run (success) |
| 2026-10-11 | **Roadmap Grad 03–05** (`docs/roadmap-grad-03-05.md`): drei Kategorien (geliefert/valides Modell/nicht gebaut), 3 offene WARN-Befunde gw3/4/5 (GB-06/14/05), 7 ungebauten Kontrollen benannt, Beweis-Befehle verifiziert | gradbuild.cli + grep + CI grün |
| 2026-10-11 | **Two Lücken geschlossen**: `gw_core.exception_queue.ExceptionQueue` (deterministische Policy, GB-09/15/12, Append-only, KPI) + `gw_core.sampling_audit.SamplingAudit` (reproduzierbare systematische Stichprobe, Kriterien, Evidenz, Audit-von-Audit) — 21 neue Tests (Total 70). Roadmap 2.2/2.3/3/4 + README (acht Bausteine) + gw_core-README aktualisiert. Ruff-Konfig geschärft (nur unveränderte Quellen ausgenommen) | pytest (70) + ruff + Import-OK |
| 2026-10-11 | **Technologie-Stack-Doku** (`docs/technologie-stack.md`): je Baustein — Technik, Alternativen (SQLite vs In-Memory/Redis/Postgres/JSON, Spekulation vs HTTP-im-Core, FreigabePolicy vs OIDC/Keycloak, Fingerprint vs SemVer), Begründung; verfehlte Alternativen (SQLAlchemy, Queue, Scheduler) motiviert. **Fazit: Rollback + decides_new brauchen 0 neue Dependencies** | docs/technologie-stack.md |
| 2026-10-11 | **Dritte Lücke geschlossen**: `gw_core.rollback.RollbackManager` (GB-12): Snapshot-Registry (Vorher/Nachher), deterministischer Reversal-Befehl aus Template+Snapshot, Append-only Ausführung, KPI-Zähler. 14 neue Tests (Total **84**). RLock-Fix (Self-Deadlock). Roadmap 2.2/2.3/3/4 + README (neun Bausteine, ExQ 13 Tests korrigiert) + gw_core-README aktualisiert | pytest (84) + ruff + Import-OK |
| 2026-10-11 | **Design-Entwurf Grad 4/5** (`docs/grad4-5-multiagent-design.md`, Status: Entwurf nicht Code): §0 autonome Aktionen A1–A8 mit GB-Referenz; §1 Team (6 Rollen, je: Rolle/L4/L5/Kernkompetenz+Prompt-Fokus/Tools-APIs — Klassifikator tool-frei = GB-05); §2 Kontrolllogik (Entscheid: zyklischer State-Graph «LangGraph-Muster», 4 Begründungen + Gegenargument; ASCII-Workflow-Graph mit Loop-Guard ≤2 Runden + Budget-Kanten; `FallZustand`-State-Objekt: Identität, strukturierte Falle, Limits, Zähler, Snapshots, Audit-Refs); §3 Monitoring (5 Tracing-Strenge-Punkte, 6 Endlosschleifen-Risiken mit numerischen Limits — systemseitig nie prompt, 8 KPIs); §4 A2A (v0.3-Card-JSON inline, OIDC-Scopes, Signed-Card) + MCP (5 Server je Rolle, Credentials in Server-Layer, Shadow = Write-Tool nicht exponiert) | JSON valid, Querverweise (README/Roadmap/technologie-stack/governance) |
| 2026-10-11 | **A2A Agent-Card als Repo-Artefakt** (`governance/a2a-agent-card.json`): v0.3, 3 Skills, OIDC-Scopes, Platzhalter-URLs (vor Publish gegen Deployment austauschen) | `write_file`-Verifikation |

## 7 · Release-Gate (vor Public, jede mal)

1. `grep -rniE 'chf|franken|kalkulation|marge' .` — keine Verkaufspreise/
   Kalkulation. (Fachdaten wie Rechnungsbeträge in Code/Tests/Doku sind
   korrekt so — das ist Domäne, nicht Preis.)
2. `grep -rniE 'bexio.*token|api_key|password' .` — nur Doku-Verweise, keine Werte.
3. `uv run pytest -q` — alle grün.
4. `uv run gradbuild validate examples/*.json` — alle Exit 0.
5. `uv run ruff check .` — keine Errors.
6. README: "Kein Rechtsrat." + Grenzen-Section + Stand-Datum.
7. Edin-Green-Light → `gh repo edit --public` + Topics + Beschreibung.
