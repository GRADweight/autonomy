# Regulatorische Einordnung

Dieses Dokument zeigt, welche Regeln und Bausteine welche Anforderungen
**unterstützen**. Es ist kein Rechtsrat und keine Konformitätsaussage: Ob ein
Anwendungsfall unter eine Vorschrift fällt und ob die Massnahmen genügen,
beurteilen Fachleute im Einzelfall. Stand der Angaben: Oktober 2026.

## Schweiz: Datenschutzgesetz (revDSG, SR 235.1)

In Kraft seit 1. September 2023.

| Bestimmung | Inhalt (verkürzt) | Unterstützung im Repo |
|---|---|---|
| Art. 5 lit. c | besonders schützenswerte Personendaten | Feld `data.special_categories`; GB-17 verlangt dann Datenklasse «vertraulich» oder «geheim» |
| Art. 8 | Datensicherheit | GB-15 (Datenklasse und Verarbeitungsort), Audit-Trail |
| Art. 16 | Bekanntgabe ins Ausland | GB-15 warnt bei vertraulichen Daten in beliebiger öffentlicher Cloud |
| Art. 21 | Information über automatisierte Einzelentscheide; auf Verlangen Überprüfung durch eine natürliche Person; Ausnahmen in Abs. 3 | GB-21 verlangt Kontrolle `human_review_on_request` oder eine begründete Ausnahme |

## EU: KI-Verordnung (AI Act, VO (EU) 2024/1689)

Für Schweizer Unternehmen relevant, wenn sie KI-Systeme in der EU anbieten
oder deren Ergebnisse in der EU verwendet werden (Art. 2). Die Pflichten für
Hochrisiko-Systeme nach Anhang III gelten gemäss der Änderungsverordnung
VO (EU) 2026/1744 («Digital Omnibus», Amtsblatt vom 24.07.2026, in Kraft seit
27.07.2026) ab 2. Dezember 2027, für Systeme nach Anhang I ab 2. August 2028.
Die Transparenzpflichten nach Art. 50 gelten seit 2. August 2026.

| Bestimmung | Inhalt (verkürzt) | Unterstützung im Repo |
|---|---|---|
| Art. 6, Anhang III | Einstufung als Hochrisiko (z. B. Anhang III Nr. 4 lit. a: Auswahl von Bewerbungen) | Felder `regulatory.*`; Beispiel `gw2-bewerbungsvorsortierung` mit Deckel Grad 2 |
| Art. 12 | automatische Protokollierung | GB-22 verlangt `audit_log`; Baustein `audit` |
| Art. 14 Abs. 4 lit. b | Bewusstsein für Automation Bias | GB-07 (Übernahmequote), `ApprovalSummary.human_override_rate` |
| Art. 14 Abs. 4 lit. d | Ausgaben übersteuern oder rückgängig machen | Freigabe-Queue (`amend`, `reject`), Baustein `rollback` |
| Art. 14 Abs. 4 lit. e | Eingreifen oder Anhalten über einen «Stopp» | GB-12 verlangt einen getesteten Notaus (`kill_switch`) |
| Art. 15 | Genauigkeit, Robustheit, Cybersicherheit | GB-03 und GB-18 (Prompt-Injection-Kette), GB-14 (Messung) |

## EU: Maschinenverordnung (VO (EU) 2023/1230)

In Kraft seit 19. Juli 2023, anwendbar ab 20. Januar 2027. Sicherheitsbauteile
mit vollständig oder teilweise selbstentwickelndem Verhalten (maschinelles
Lernen) gehören zu den Produkten in Anhang I Teil A. GB-06 hält
Schutzfunktionen deshalb ausserhalb des Modells und deckelt auf Grad 3.
Ergänzend: ISO/IEC TR 5469:2024 (Functional safety and AI systems).

## Finanzbranche: FINMA-Aufsichtsmitteilung 08/2024

«Governance und Risikomanagement beim Einsatz künstlicher Intelligenz» vom
18. Dezember 2024, für beaufsichtigte Institute. Sie behandelt unter anderem
Governance, Identifikation und Steuerung von KI-Risiken, Modellrisiken
(Robustheit, Korrektheit, Erklärbarkeit, Bias), Datenqualität sowie IT-,
Cyber- und Drittparteirisiken. Das Repo liefert dafür Bausteine (Register-
und Rollenvorlagen in `governance/`, Nachweispflicht, Audit-Trail), aber keine
Abdeckung der Aufsichtserwartungen.

## Normen und Rahmenwerke

| Quelle | Bezug |
|---|---|
| ISO/IEC 42001:2023 (KI-Managementsystem) | Die Nachweispflicht (GB-19, GB-20) erzeugt dokumentierte Information im Sinn von Abschnitt 7.5. Das Repo ersetzt kein Managementsystem und führt zu keiner Zertifizierung. |
| NIST AI Risk Management Framework 1.0 (Januar 2023) | Die Regeln betreffen vor allem die Funktion «Govern» (Verantwortung, Grenzen, Freigaben) und «Measure» (GB-14). |
| OWASP Top 10 for LLM Applications 2025, LLM06 «Excessive Agency» | Grenzen im Zielsystem statt im Prompt (GB-08, GB-09), minimale Rechte (GB-11) |
| Meta AI, «Agents Rule of Two» (31.10.2025) | GB-03: höchstens zwei von drei Eigenschaften ohne Mensch in der Kette |
| CVE-2025-32711 (EchoLeak, Microsoft 365 Copilot) | Beispiel für die Kette aus fremder Eingabe, sensiblen Daten und Aussenwirkung |
| Yao et al., «τ-bench», arXiv:2406.12045 | Metrik pass^k für GB-14 |

## Mehrwertsteuer und QR-Rechnung

Siehe [Belegprüfung](belegpruefung.md): MWST-Sätze der ESTV (massgebend ist
das Datum der Leistung) und die Swiss Implementation Guidelines QR-bill der SIX.
