# Feldreferenz Use-Case-Schema 2.0

<!-- Automatisch erzeugt mit `gw-autonomy schema --format markdown`. Nicht von Hand bearbeiten; ein Test vergleicht diese Datei mit dem Schema. -->

Schema: `src/gradweight_autonomy/validator/schemas/usecase-2.0.schema.json` (`$id` `urn:gradweight:autonomy:usecase:2.0`). Unbekannte Felder sind nicht erlaubt.

| Feld | Typ | Pflicht | Beschreibung |
|---|---|---|---|
| `schema_version` | `"2.0"` | ja | Version dieses Schemas. |
| `id` | string (Muster) | ja | Stabile ID des Anwendungsfalls (Kleinbuchstaben, Ziffern, . _ -). |
| `title` | string | ja | Kurzbeschreibung des Anwendungsfalls. |
| `description` | string | nein | Optionale ausführliche Beschreibung. |
| `level` | integer (>= 0, <= 5) | ja | Deklarierter Autonomiegrad 0 bis 5. |
| `who_plans` | `human` \| `fixed_chain` \| `model` | ja | Achse 1: Wer bestimmt den Weg? |
| `human_role` | `full_control` \| `per_action` \| `per_gate` \| `mandate` \| `exception_only` | ja | Achse 2: Wo greift der Mensch ein? |
| `owner` | string | ja | Verantwortliche Rolle (Funktion, keine Personennamen). |
| `risk` | Objekt | ja | Risikomerkmale; [A], [B] und [C] sind die drei Eigenschaften der Rule of Two. |
| `risk.foreign_input` | boolean | ja | [A] Verarbeitet Eingaben ausserhalb des kontrollierten Systems (E-Mail, Formular, externe API). |
| `risk.sensitive_data` | boolean | ja | [B] Zugriff auf sensible Daten oder Systeme. |
| `risk.external_action` | boolean | ja | [C] Ändert Zustände oder kommuniziert nach aussen. |
| `risk.money_effect` | boolean | ja | Löst Zahlungen, Gutschriften, Bestellungen oder Buchungen aus. |
| `risk.customer_facing` | boolean | ja | Ergebnisse erreichen Kundinnen und Kunden direkt. |
| `risk.customer_text_in_decisions` | boolean | ja | Freitexte von Kundinnen und Kunden fliessen in Entscheide ein. |
| `risk.safety_critical` | boolean | ja | Berührt Schutzfunktionen (Maschinen, Anlagen, Personensicherheit). |
| `data` | Objekt | ja | Datenklasse, Verarbeitungsort und Personendaten. |
| `data.classification` | `frei` \| `intern` \| `vertraulich` \| `geheim` | ja | Datenklasse: frei, intern, vertraulich oder geheim. |
| `data.residency` | `on_prem` \| `ch` \| `eu` \| `public` | ja | Wo die Daten verarbeitet werden: eigene Infrastruktur, Schweiz, EU/EWR oder beliebige öffentliche Cloud. |
| `data.personal_data` | boolean | ja | Es werden Personendaten bearbeitet (revDSG). |
| `data.special_categories` | boolean | nein | Besonders schützenswerte Personendaten (revDSG Art. 5 lit. c). |
| `data.automated_individual_decisions` | boolean | nein | Ausschliesslich automatisierte Entscheide mit Rechtsfolge oder erheblicher Beeinträchtigung (revDSG Art. 21). |
| `regulatory` | Objekt | nein | Optionale regulatorische Einstufung. |
| `regulatory.eu_ai_act_high_risk` | boolean | nein | Hochrisiko-KI-System nach EU AI Act (Art. 6, Anhang III oder Anhang I). |
| `regulatory.eu_ai_act_category` | string | nein | Fundstelle der Einstufung, z. B. 'Anhang III Nr. 4 lit. a'. |
| `regulatory.notes` | string | nein | Freie Anmerkungen zur Einstufung. |
| `mandate` | Objekt | nein | Mandat: Grenzen, innerhalb derer ein Modell ohne Freigabe je Aktion handeln darf. |
| `mandate.limits_in_system` | boolean | ja | Die Grenzen werden im Zielsystem durchgesetzt, nicht im Prompt. |
| `mandate.enforced_by` | string | ja | Wo die Grenze technisch wirkt (z. B. 'ERP-Freigabestrategie Einkauf'). |
| `mandate.money_limit` | Objekt | nein | Bezifferte Betragsgrenze (Pflicht bei Geldwirkung ohne Freigabe je Aktion). |
| `mandate.money_limit.amount` | number (> 0) | ja | Betragsgrenze. |
| `mandate.money_limit.currency` | string (Muster) | ja | Währung nach ISO 4217, z. B. CHF. |
| `mandate.money_limit.per` | `transaction` \| `day` \| `week` \| `month` | ja | Bezugsgrösse der Grenze: je Transaktion, Tag, Woche oder Monat. |
| `mandate.scope` | string | nein | Empfängerkreis, Artikel, Zeitraum. |
| `mandate.evidence[]` | Liste: string (Muster) | ja | Nachweise für die Durchsetzung im Zielsystem (config, test_report). |
| `ceiling` | Objekt | nein | Deckel: höchster zulässiger Grad für diesen Anwendungsfall. |
| `ceiling.max_level` | integer (>= 0, <= 5) | ja | Höchster zulässiger Grad. |
| `ceiling.reason` | string | ja | Begründung des Deckels. |
| `ceiling.regulation` | string | ja | Rechtliche oder interne Grundlage. |
| `ceiling.decided_by` | string | nein | Gremium oder Rolle, die den Deckel beschlossen hat. |
| `measurement` | Objekt | nein | Wie die Zuverlässigkeit gemessen wird. |
| `measurement.method` | `pass^k` \| `shadow` | ja | pass^k (wiederholte Testaufgaben) oder shadow (Schattenbetrieb). |
| `measurement.k` | integer (>= 1) | nein | Anzahl Wiederholungen je Aufgabe bei pass^k. |
| `measurement.tasks` | integer (>= 1) | nein | Anzahl Testaufgaben. |
| `measurement.threshold` | number (>= 0, <= 1) | nein | Zielwert der Messung zwischen 0 und 1. |
| `measurement.evidence[]` | Liste: string (Muster) | ja | Messberichte (measurement, test_report). |
| `steps[]` | Liste von Objekten | nein | Optionale Schritte des Prozesses; wirksame Schritte bestimmen den Grad mit (GB-16). |
| `steps[].name` | string | ja | Bezeichnung des Schritts. |
| `steps[].planned_by` | `human` \| `fixed_chain` \| `model` | ja | Wer den Schritt plant. |
| `steps[].human_role` | `full_control` \| `per_action` \| `per_gate` \| `mandate` \| `exception_only` \| `none` | ja | Wo der Mensch in diesem Schritt eingreift; 'none' nur für Schritte ohne Wirkung. |
| `steps[].state_change` | boolean | nein | Der Schritt ändert einen Zustand. |
| `steps[].external` | boolean | nein | Der Schritt wirkt nach aussen. |
| `steps[].money` | boolean | nein | Der Schritt hat Geldwirkung. |
| `controls.<kontrolle>` | Objekt | nein | Eine von: `audit_log`, `agent_identity`, `exception_queue`, `sampling_audit`, `incident_process`, `automatic_rollback`, `kill_switch`, `change_management`, `shadow_run`, `proposal_mode_first`, `adoption_rate_monitoring`, `input_isolation`, `human_oversight`, `human_review_on_request` |
| `controls.<kontrolle>.status` | `implemented` \| `planned` \| `not_applicable` | ja | implemented (mit Nachweis), planned oder not_applicable (mit Begründung). |
| `controls.<kontrolle>.evidence[]` | Liste: string (Muster) | nein | IDs der Nachweise; bei implemented Pflicht. |
| `controls.<kontrolle>.rationale` | string | nein | Pflicht bei not_applicable. |
| `controls.<kontrolle>.note` | string | nein | Freie Anmerkung. |
| `evidence[]` | Liste von Objekten | ja | Nachweise, auf die Kontrollen, Mandat und Messung verweisen. |
| `evidence[].id` | string (Muster) | ja | Eindeutige ID des Nachweises. |
| `evidence[].type` | `test_report` \| `approval_record` \| `config` \| `runbook` \| `policy` \| `measurement` \| `log_extract` \| `architecture` | ja | Art des Nachweises. |
| `evidence[].ref` | string (Muster) | ja | Relativer Pfad (ohne '..'), https-URL oder URN eines Dokumentensystems. |
| `evidence[].date` | string (Muster) | ja | Datum des Nachweises (JJJJ-MM-TT). |
| `evidence[].description` | string | ja | Was der Nachweis belegt. |
| `evidence[].sha256` | string (Muster) | nein | Optionaler Hash der Datei; wird mit --check-evidence geprüft. |
| `evidence[].approved_by` | string | nein | Rolle, die den Nachweis abgenommen hat. |
