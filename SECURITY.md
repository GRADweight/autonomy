# Sicherheitsmeldungen

Falls du eine Schwachstelle in diesem Repo findest, melde Sie bitte
öffentlich **nicht** über die Issues, sondern direkt:

- **E-Mail:** hallo@gradweight.ch
- **Thema:** `[security] <kurze Beschreibung>`

## Was wir als Sicherheitsmeldung ansehen

- Eine Möglichkeit, eine Freigabe zu umgehen ohne die befohlene Rolle
  (AuthZ-Break)
- Eine Möglichkeit, den Audit-Trail zu löschen oder zurückzusetzen
  (append-only-Break)
- Eine Schwachstelle in der Zielsystem-Adapter-Limits-Logik
  (Betrag-/Tagesvolumen-Blockade wird nicht erzwungen)
- Ein Leck von Secrets oder PII in den Code, Tests oder Beispielen

## Was wir NICHT als Sicherheitsmeldung ansehen

- «Der Injection-Check hat Lücken» — das ist dokumentiert
  (governance/README.md, «erste Schicht, keine Garantie»). Lücken sind
  nicht Fehler, und wir arbeiten daran.
- «Das Modell kann gehackt werden» — das ist ein Modell-Problem, nicht
  ein Governance-Problem in diesem Repo.

## Unser Prozess

1. **Eingang:** Wir bestätigen den Eingang innerhalb von 72h (Kalendertage).
2. **Prüfung:** 5–10 Arbeitstage, je nach Komplexität. (Keine
   SLA-Zusage von 24h — das wäre eine Lüge.)
3. **Fix:** Wenn der Befund korrekt ist: Fix im nächsten Release,
   mit Verweis auf den Issue-Referenz (keine Details öffentlich,
   nur die Tatsache, dass es einen Fix gab).
4. **Dank:** Kein öffentlicher «Hall of Fame» — die Person bleibt
   anonym, die Arbeit wird im Changelog genannt.

*Kein Rechtsrat.* Diese Seite ist der Meldeprozess, nicht eine
Haftungsregel.
