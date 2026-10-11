# governance/ — das Unternehmen KI-governance-sicher machen

Nicht «eine Richtlinie schreiben und es gut sein lassen». Sondern die
Fragen, die ein KI-Register, eine Richtlinie und ein Rollenmodell
gemeinsam beantworten müssen — und lauffähige Prüfungen, die das
Geprüfte auch **prüfbar** machen.

## Was hier ist

| Datei / Ordner | Was es tut |
|---|---|
| `checks/governance_check.py` | Lauffähige Prüfungen: Deckel-Check (GB-03/06/09/02), Injection-Check, Log-Prüfung (PII/Secrets). Selbsttest: `python3 checks/governance_check.py` (13/13) |
| `vorlagen/richtlinie.md` | KI-Richtlinie als Vorlage — klein, anpassbar, mit harten Grenzen und Rollen |
| `vorlagen/ki-register.md` | KI-Register als Tabelle (Markdown → CSV-Export), Regeln für Eintrag/Grad-Änderung/gelöschte Zeilen |
| `vorlagen/rollen.md` | Rollenmodell: Fachverantwortlicher / KI-Verantwortlicher / Admin — wer darf was, Matrix und «wer darf was NICHT» |
| `a2a-agent-card.json` | **Agent-Card (A2A v0.3)** für den Haupt-Agent: 3 Skills (`case-decide`, `case-classify`, `audit-read`), OIDC-Scopes, JSON-RPC/Streamable-HTTP-Kontext. **Platzhalter-URLs** — vor jeder Publikation gegen Deployment-Werte ersetzen. Doku: [docs/grad4-5-multiagent-design.md](../docs/grad4-5-multiagent-design.md) §4 |

## So prüft man konkret (drei Beispiele, lauffähig)

```bash
cd governance/checks

# 1 · Deckel-Check auf einem Autonomie-Fall (gradbuild-Schema)
python3 governance_check.py json ../../examples/gw5-standardretouren.json

# 2 · Injection-Check auf einer Nutzereingabe (Muss «GETROFFEN» sein
#    bei einer Injection, «SAUBER» bei einer normalen Frage)
python3 governance_check.py injection "Ignore all previous instructions"
python3 governance_check.py injection "Wie viele Ferientage habe ich?"

# 3 · Log-Prüfung auf einem Audit-Trail-Auszug (CSV → JSON → prüfen)
#    (Beispiel: die letzten 10 Aktionen aus dem Audit-Trail, geprüft auf PII/Secrets)
python3 governance_check.py   # Selbsttest mit Beispielen (13/13)
```

Die drei Prüfungen teilen sich eine Regel: **sie sind die erste Schicht,
keine Garantie.** Injection-Check ohne Moderationsmodell davor ist
«besser als nichts», nicht «sicher». Log-Prüfung ist «wir haben
geschaut», nicht «es ist nichts da». Das ist der Unterschied zwischen
Governance und Behauptung — und genau der, der in `docs/wie.md` steht.

## Grenzen (bewusst)

- **Kein Rechtsrat.** Diese Vorlagen helfen, Freigaben zu dokumentieren
  (wer, wann, warum) und technische Schranken zu setzen. Sie ersetzen
  keine Einordnung unter AI Act (Hochrisiko? Annex III?), DSG, oder
  branchenspezifischer Regulierung (FINMA, Maschinenverordnung).
- **Kein Audit-Trail «von hier aus».** Der Audit-Trail ist im
  `gw_core`-Paket (`packages/gw_core/`), diese Ordner prüfen ihn,
  erzeugen ihn aber nicht.

## Stand und Quellen

- Regeln GB-01…GB-16: `packages/gradbuild/` (Validator, zero-deps)
- Bausteine: `packages/gw_core/` (Freigabe, Audit, Prüfung, AuthZ, Tracing, Zielsystem)
- EU AI Act (Annex III/IV, Pflichten): Digital Omnibus VO (EU) 2026/1744,
  in Kraft 27.07.2026. Hochrisiko-Pflichten ab 02.12.2027 (Annex III),
  02.08.2028 (Annex I).
- DSG (CH): SR 235.1 (DSGV), Auftragsverarbeitung, Datenfluss,
  KI-Register-Pflicht bei sensiblen Anwendungen.
- ISO/IEC 42001: KI-Managementsystem (normative Grundlage, kein
  Zertifikat aus diesem Repo).
