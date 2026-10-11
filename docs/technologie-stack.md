# Technologie-Stack — was wir brauchen, was die Alternativen sind, warum

> **Stand:** 2026-10-11 · **Repo:** `GRADweight/gradautonomy`
>
> Diese Seite beantwortet drei Fragen für jeden Baustein, der noch fehlt
> (und die zwei, die es jetzt schon gibt):
>
> 1. **Welche Technik wird verwendet?**
> 2. **Welche Alternativen gab es?**
> 3. **Warum diese Wahl — und wieso nicht die anderen?**
>
Kein "wir nutzen X, weil es geläufig ist." Jede Entscheidung ist eine
bewusste Wahl mit Abwägung.

---

## 0 · Der aktuelle Stack im Repo (Grundlage)

| Technologie | Wo | Warum drin |
|---|---|---|
| **Python ≥ 3.11** | Alle Pakete | `datetime.UTC` in `gw_core`; 3.11 ist die Untergrenze |
| **`sqlite3`** (stdlib) | `audit.py`, neu: `rollback.py` | Append-only, ACID, null neue Dependencies |
| **`httpx`** (optional) | `bexio.py` nur | HTTP-Adapter für Zielsystem — KEINE Kern-Debatie |
| **`pytest` + `ruff`** | CI + Tests | Tests + Lint, beide in der Stack schon |

**Prinzip:** Null neue Dependencies für die Kern-Governance-Bausteine.
Jeder Baustein ist offline-testbar ohne Netzwerk.

---

## 1 · `automatic_rollback` — der nächste Schritt

### Das, was der Baustein technisch kann müssen

1. **Vorher-Snapshot** erfassen: Was war im Zielsystem, bevor die Aktion
   ausgelöst wurde? (z. B. "keine Rechnung vorhanden" oder
   "Buchung #4512 mit Betrag 1,240 CHF")
2. **Nachher-Snapshot** erfassen: Was hat das Zielsystem zurückgegeben
   (ID, Status, Änderungen)?
3. **Rollback-Befehl** generieren: Die **konkrete** Reversal-Operation
   (DELETE / UPDATE / NEUTRALSCHEN), die das Zielsystem ausführen muss,
   um auf den vorher-Snapshot zurückzukehren.

Das ist die Definition. Nicht "irgendwie rückgängig machen."
Sondern: **welcher HTTP-Call mit welchen Parametern**, aus dem
konkreten vorher/nachher-Snapshot abgeleitet und in den Audit-Trail
geschrieben.

### Technik-Wahl: State-Store

| Option | Warum ja | Warum nein |
|---|---|---|
| **SQLite** ✅ | Bereits in Stack (`audit.py`); ACID-Transaktionen; lokale Datei; null neue Dependencies; atomare Lese-/Schreibzugriffe | |
| In-Memory (dict) | Einfach | **Verlust bei Neustart** — genau der Moment, in dem man rollen muss, ist weg |
| Redis | Schnell, clustergerecht | Externer Server; für Airplane-Modus und KMU-Deployment unpassend; kein ACID |
| Postgres | Robust | Externe Instanz; Single-Tenant Tool braucht das nicht; Betrieb overhead |
| JSON-Datei | Einfach | Keine Atomarität (Crash → korruptes Snapshot); keine Concurrent-Lese-Sicherheit |

**Entscheid: SQLite.** Gleiche Storage-Schicht wie `audit.py`,
gleiche Thread-Sicherheit, gleicher `threading.Lock`-Muster.
Ein Kunde, der das System deployt, braucht eine `.db`-Datei.

### Technik-Wahl: Rollback-Ausführung

| Option | Warum ja | Warum nein |
|---|---|---|
| **Spekulation only** ✅ | `RollbackManager` liefert den Befehl; der **Host** führt ihn aus. Gleiche Architektur wie `bexio.py` (Adapter macht HTTP, Core macht Logik) | |
| Direktes HTTP im Core | "Einfacher" | Vermischt Schicht-Aufgaben; Core wird HTTP-Abhängigkeit; nicht portabel zwischen Zielsystemen (Bexio vs. Sage50 vs. DATEV) |

**Entscheid: Spekulation.** `RollbackManager.rollback_befehl(id)`
liefert ein `RollbackBefehl`-Objekt (Methode, Endpoint, Parameter,
Begründung). Der Host-Code (Kunden-Deployment) ruft die Zielsystem-
API mit diesem Befehl auf. Das ist der gleiche Layering-Grundsatz
wie die Freigabe-Queue: Core = Logik, Adapter = Transport.

### Technik-Wahl: Reversalität je Aktionstyp

Nicht jede Aktion ist reversibel. Das Modell muss es wissen:

```
reversibel  = False → kein Rollback möglich; nur manuelle Korrektur
reversibel  = True  → vorher/nachher-Snapshot wird erfasst;
                      RollbackBefehl ist generierbar
```

Das wird in der `register()`-Aufruf gesetzt. Der Baustein **erzwingt**
nicht, dass jede Aktion reversibel ist — er **erkennt** es, wenn es
nicht ist, und gibt eine klare, lesbare Fehlermeldung zurück.

---

## 2 · `shadow_run_first` — als Betriebs-Konfiguration

### Warum kein separater Baustein

Die Roadmap 2.2 kennzeichnet `shadow_run_first` als "indirekt /
Betriebs-Konfiguration." Das ist korrekt und hier begründet:

**Shadow-Run** = "das Modell trifft den gleichen Entscheid, aber das
Zielsystem wird NICHT geschrieben." Technische Umsetzung:

```python
# Vorher (Production-Modus):
result = bexio_adapter.lieferrechnung_buchen(...)

# Shadow-Modus:
shadow_result = bexio_adapter.lieferrechnung_buchen_shadow(...)  # kein POST
```

Das ist **kein neuer Baustein in `gw_core`** — es ist eine
**Betriebs-Konfiguration**: der Host schaltet den Adapter in Shadow-
Modus um, liest den Entscheid, vergleicht mit dem erwarteten, und
erst nach `n` konsequenten Läufen schaltet er Production frei.

Die `sampling_audit`-Stichprobe (geliefert) misst genau das:
"Wie viele Entscheide stimmen, bevor wir Production schalten?"

### Technik-Wahl: Messung

| Option | Warum ja | Warum nein |
|---|---|---|
| **`sampling_audit` + `ApprovalQueue`** ✅ (beides geliefert) | Beide Bausteine decken die Logik ab: Approval = "was wurde entschieden", Sampling = "wie stimmen die Entscheide" | |
| Separate `ShadowRunner`-Klasse | Explizit | Redundant; die Kombination aus bestehenden Bausteinen genügt und ist leichter zu testen |

---

## 3 · `agent_identity_min_privilege` — der einzige externe Stack-Bestandteil

### Was "Agent-ID" technisch bedeutet

Jeder Agent, der eine Aktion im Zielsystem ausführt, braucht eine
**Identität mit definierten Rechten**. Nicht "ein Servicekonto, das alles
kann." Sondern: "dieser Agent darf genau diese Endpunkte mit genau
diesen Scopes, und NICHTS mehr."

### Technik-Wahl: Identitäts-Rahmen

| Option | Warum ja | Warum nein |
|---|---|---|
| **`FreigabePolicy`** (im Repo, geliefert) | Rollen × Kontext → Rechte; Least Privilege ohne externes System; offline-testbar | Für **KMU ohne IdP**: reicht (die meisten KMU haben keinen Entra) |
| **OIDC / Entra Agent ID** (extern) | Industriestandard; pro-Agent-Identität; Audit-Log bei Microsoft; "Entra Agent ID" ist der MS-Standard für genau diesen Use-Case | **Neue Dependencies**: `PyJWT` + `httpx` (letztes ist schon optional da); erfordert ein Entra-Abonnement |
| **Keycloak** (selbst gehostet) | Offen, kein Abo; volle Kontrolle | Betrieb + Sicherheit + Updates — für einen Einzelunternehmer ein zu großes Projekt |

**Entscheid im Repo: `FreigabePolicy`** (geliefert).
**Entscheid im Deployment: OIDC/Entra** — der Host integriert `PyJWT`
und `httpx` bereits für die Zielsystem-API; die Agent-Identität wird
als `actor`-Feld im `AuditTrail`-Eintrag geführt (das ist das
`FreigabePolicy.authz_decision`-Ergebnis).

Die `gw_core`-Bausteine müssen für `agent_identity=true` **nichts
neues** einbauen — sie müssen nur `actor` als ein nicht-aufgelöste
Rolle statt als freie Text-String verstanden. Das ist der
`FreigabePolicy`-Pflichtfall, der schon implementiert ist.

---

## 4 · `decides_new_on_model_prompt_tool_change` — Change-Detection

### Was der Baustein technisch kann müssen

1. **Fingerprint** des aktuellen Modells + Prompt + Tool-Set
   berechnen (deterministisch).
2. **Vorher-Fingerprint** vergleichen (aus dem Audit-Trail).
3. **Neu-Entscheid anfordern**: Wenn die Fingerprints abweichen →
   der `FreigabePolicy`-Pflichtfall muss **neu** laufen.

### Technik-Wahl: Fingerprint

| Option | Warum ja | Warum nein |
|---|---|---|
| **`hashlib.sha256(model_id + "\x00" + prompt_template + "\x00" + sorted_tool_list)`** ✅ | stdlib; deterministisch; `""` als Separator verhindert Kollisionen; sortierte Tool-Liste → Reihenfolge-unabhängig | |
| Semantik-Versionierung des Modells | Elegant | Nicht alle Anbieter geben SemVer; Hash ist immer verfügbar |
| Prompt-Baum (AST) | Präzise | Überkill; Hash reicht für "ist etwas anders als letztes Mal" |

### Technik-Wahl: Wo der Fingerprint gespeichert wird

Im `AuditTrail` (sqlite) — `details={"model_id": ..., "prompt_hash": ...,
"tool_list": [...]}`. Kein neuer Storage.

**Keine neue Dependency.**

---

## 5 · Zusammenfassung als Entscheidungstabelle

| Baustein | Neue Dependencies? | Storage | Externes System? |
|---|---|---|---|
| `automatic_rollback` | Nichts (stdlib + `sqlite3`) | SQLite (gleiche DB wie `audit.py`) | Nein — Host ruft Zielsystem auf |
| `shadow_run_first` | Nichts | — | Betriebs-Konfiguration, kein Code |
| `agent_identity` | `PyJWT` + `httpx` (beides optional, im Deployment) | — | Entra / OIDC-IdP (Kunde) |
| `decides_new_on_model...` | Nichts (`hashlib` ist stdlib) | Audit-Trail (sqlite) | Nein |
| `Orchestrator` (Grad 5) | Nichts (stdlib) | — | Nein |
| **Text-Klassifikator** (Grad 5) | **Modell-API** (z. B. `httpx` + Ollama / Azure OpenAI) | — | Ollama lokal oder Cloud LLM |

**Fazit:** Für die beiden nächsten konkreten Schritte
(`automatic_rollback` + `decides_new_on_model_prompt_tool_change`)
braucht es **null neue Dependencies**. Das ist das Wichtigste, was
diese Doku sagt.

> **Weiter in die Architektur:** Wie ein Grad-4/5-System um diese
> Bausteine herum aufgebaut wird — das Orchestrator-Muster (Entscheid:
> zyklischer State-Graph, begründet), das State-Objekt, die
> Endlosschleifen-Limits und die A2A/MCP-Anbindung — steht im
> [Design-Entwurf](grad4-5-multiagent-design.md). Dort ist auch die
> ehrliche Trennung: was im Repo Code ist, was Deployment-Baustein ist.

---

## 6 · Warum nicht [verfehlte Alternativen]

Zu den drei häufigsten Vorschlägen, die bei diesem Stack typischerweise
kommen, und warum wir sie nicht gewählt haben:

**"Warum nicht `SQLAlchemy` oder `Django ORM` für den State?"**
→ Der Datenmodell ist ein einzelnes, schmales, append-only Schema mit
zwei Tabellen. `SQLAlchemy` bringt eine Abstraktionsschicht, die
dafür nicht existiert. `sqlite3` direkt ist 20 Zeilen Code, null
Dependencies, volle Kontrolle, kein Lock-In.

**"Warum nicht eine Message Queue (RabbitMQ, Kafka) für async Rollback?"**
→ Rollback muss **deterministisch und synchron** sein. Eine Queue
führt zu "wann ist der Rollback eigentlich fertig?" — genau die
Unschärfe, die GB-08/GB-10 vermeiden soll. Synchron + auditierbar
= SQLite + Return-Wert.

**"Warum kein `Celery` oder `APScheduler` für die Re-Evaluations-Trigger?"**
→ Der Trigger ist ein **Vergleich zweier Fingerprints**. Das ist eine
einzelne `if`-Bedingung im Code, kein Scheduler. Wer das in einen
Scheduler-Auftrag auslagert, hat ein Problem, das er nicht hatte.
