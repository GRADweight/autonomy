# Level 0 — Keine Autonomie (Mensch steuert jeden Schritt)

> **Stand:** 2026-10-11 · **Repo:** `GRADweight/gradautonomy` · **Level 0**
>
> **Achsen** (`schema.py::ALLOWED_AXES[0]`): `(human, full_control)` — der
> **Mensch plant den Weg** und **führt jeden Schritt selbst aus/ausgelöst**.
> **Referenz-Case:** `examples/gw0-marktforschung.json` (valid, `exit 0`).
>
> Kurz: Das System **recherchiert oder entwirft** nur; **keine Wirkung nach
> aussen**, **kein Geld**, **keine fremde Eingabe** im Entscheidungsfluss.
> Der Mensch bleibt in jedem aktiven Schritt.

---

## 1 · Was Level 0 ist (und was nicht)

**Ja:** Recherche aus öffentlichen Quellen, Entwürfe, Zusammenfassungen,
Brainstorming, «kannst du mir das aufbereiten?». Der Mensch liest, trifft
die Entscheidung, startet jede Aktion.

**Nein:** keine ausgehenden Aktionen (Mail, Zahlung, Ticket), keine
automatische Auslösung, keine Mandate, keine autonomen Schleifen.

Level 0 ist der **Sichere Startpunkt** für alles, was noch nicht klar ist —
und der Grad für reine Recherche ohne Wirkung (Recherche ohne Wirkung
zählt nicht als Autonomie, README §2).

---

## 2 · GB-Pflichten auf Level 0 (hart vs. Kontext)

Quelle: `validate.py` + README §3 Präzedenz-Matrix. `E` = error (Blocker).

| Regel | Auswirkung bei Level 0 | Was es im JSON heisst |
|---|---|---|
| **GB-01** Schema | **E** — Pflichtfelder, Typen, `governance`-Objekt | Struktur immer geprüft |
| **GB-02** Achsen | **E** — `(human, full_control)` ist die **einzige** erlaubte | `who_plans=human`, `human_role=full_control` |
| **GB-03** Rule of Two | — (nur `warn`, wenn alle 3 zugleich; nicht das Ziel) | idealer Fall: [A]/[B]/[C] überwiegend `false` |
| **GB-06** Schutzfunktionen | `warn` bei `safety_critical=true` | Schutz bleibt ausserhalb der KI |
| **GB-15** Datenklasse | **E**, falls `sensitive_data=true` und `data_class` fehlt | bei sensiblen Daten muss `data_class` gesetzt sein |

**Keine** der harten Regeln GB-07/08/10/11/12/13/14 greift auf Level 0 —
diese entstehen erst mit höherer Autonomie. **Level 0 ist der Grad mit den
wenigsten harten Pflichten** im ganzen System.

---

## 3 · Referenz-Case `gw0-marktforschung.json` (aus den Beispielen)

```
level: 0
who_plans: human            human_role: full_control
foreign_input: false        sensitive_data: false
external_action: false      money_effect: false
customer_facing: false      customer_text_in_decisions: false
safety_critical: false      data_class: frei     data_residency: ch
ceiling: (keine)            measurement: (keine)
governance: owner=AI-Lead, audit_log=true, incident_log=true,
  kill_switch_tested=true, shadow_run_first=FALSE, proposal_mode_first=FALSE, …
```

**Lesart:** `sensitive_data=false`, `data_class=frei` → GB-15 nicht
ausgelöst. `external_action=false` → keine Aussenwirkung. `shadow_run_first`
und `proposal_mode_first` sind `false`, weil Level 0 **keine**
Schattenlauf-/Vorschlags-Pflicht hat (die sind erst ab Level 4, GB-13).
Alle anderen `governance`-Flags sind `true` als gute Praxis, nicht als Pflicht.

---

## 4 · Technische Umsetzung im Unternehmen

### 4.1 Was stehen muss

- **Ein LLM-Endpunkt** — kann **lokal** (Ollama) oder **Schweizer Cloud** sein.
  Für Level 0 mit `data_class=frei` gibt es **keinen harten Standort-Zwang**.
  Für `sensitive_data` (z. B. interne Markt-Beobachtungen): Schweizer/EU
  bevorzugt (DSG), On-Prem bei `geheim`.
- **Eine Oberfläche**, in der der Mensch Frage stellt und Ergebnis liest
  (Web, CLI, E-Mail-Filter). Muss nicht hochverfügbar sein.
- **Ein Verantwortlicher** je Use-Case (`governance.owner`).
- **Beleg**, wenn eine Antwort in eine Entscheidung fliesst: `AuditTrail
  (gw_core)` mit wer/was/wann + Quellden.

### 4.2 Bausteine (`gw_core`) — bewusst schlank

- `verify.pruefe_antwort` — **empfohlen**: Zweitmodell prüft Antwort gegen
  Fundstellen (Halluzinations-Sicherung), besonders wenn Quellen zitiert
  werden werden.
- `audit.AuditTrail` — **empfohlen**: wer hat was wann gefragt, welche Quelle.
- `authz.FreigabePolicy` — **optional**: wer darf zugreifen (z. B. nur das
  Marktteam), `Leak-Prävention`.
- `tracing` / `approval` / `rollback` / `exception_queue` / `sampling_audit`
  / `bexio` — **nicht nötig** (keine Aussenwirkung, kein Geld, kein Mandat).

### 4.3 Hardware / Infrastruktur (Minimum)

| Schicht | Option |
|---|---|
| Inferenz | 7B–14B, Ollama, auf jedem PC oder einer VM. Kein GPU-Zwang. |
| RAG (optional, wenn Firmenkatalog/Offerten) | Vektorspeicher (SQLite-Vector / Chroma), lokal. |
| Control-Plane | `gw_core` (zero-Dep, SQLite) — lokal, kein Standort-Risiko. |
| Zielsystem | **Keine** (keine Aussenwirkung, Level 0-Definition). |

Level 0 läuft also praktisch **auf einer lokalen Maschine** — das ist der
Pragmatik-Vorteil des ersten Grades.

---

## 5 · Absicherung & Grenzen

- **GB-06** (Schutzfunktionen): selbst auf Level 0 — **nie** eine
  sicherheitsrelevante Funktion der KI überlassen
  (Maschinenverordnung 2023/1230, ISO/IEC TR 5469).
- **GB-15** (Datenklasse): ab dem Moment, wo **sensible** Daten ins
  Prompt-Fluss kommen, ist `data_class` Pflicht — und der Standort
  entsprechend (Schweiz/On-Prem bei `vertraulich`/`geheim`).
- **Prompt-Injection (GB-03, `warn`):** auch auf Level 0 — bei
  `customer_text_in_decisions`/`foreign_input` ein `warn`; bei externer
  Freitexteingabe die Antwort immer mit Quelle verifizieren
  (`verify.pruefe_antwort`).
- **Kein Rechtsrat:** DSG (SR 235.1), AI Act, NIS2 etc. sind **technische
  Grenzen** im Validator; die rechtliche Würdigung ist eine Rechtsfrage.

---

## 6 · Offene Punkte / Risiken

- `measurement`/`shadow`/`proposal` sind auf Level 0 **nicht** Pflicht
  (keine `error`-Triggers) — aber **empfohlen**, sobald die Antwort in
  eine operative Entscheidung fliesst (Dreh- und Angelpunkt: `governance.
  audit_log=true` + ein Verantwortlicher, der das liest).
- **Typischer Fehler:** Level 0 als «Level 1 ohne Freigabe» verkaufen.
  Entscheidend ist: **der Mensch führt jeden aktiven Schritt** aus. Wenn
  das System selbst eine `external_action` auslöst, ist das schon Level 2+
  (`per_action`) — `validate.py` prüft das über `external_action` + Achsen.
- **Kein Kill-Switch-Pflicht** auf Level 0 (GB-12 ist erst ab Level 3) —
  aber ein «abstellen-können» ist gut Praxis für den Betrieb.

---

*Grundlage: `validate.py` (GB-01…16), `schema.py::ALLOWED_AXES[0]`,
`examples/gw0-marktforschung.json`, `../unternehmens-implementierung.md` §3
(Infrastruktur/Hardware/Standort), `../technik-eroeffnung.md` (Möglichkeiten).
Keine Preise, kein Rechtsrat.*
