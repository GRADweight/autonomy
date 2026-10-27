# Sicherheitslücken melden

Bitte melden Sie Schwachstellen **nicht** über öffentliche Issues, sondern auf
einem dieser Wege:

- **GitHub Private Vulnerability Reporting:** im Repository unter
  «Security» → «Report a vulnerability»
- **E-Mail:** mail@gradweight.ch, Betreff `[security] autonomy: <Kurzbeschreibung>`

Hilfreich sind: betroffene Version (`gw-autonomy --version`), Schritte zur
Reproduktion, erwartetes und tatsächliches Verhalten. Bitte keine echten
Personendaten oder Zugangsdaten mitschicken.

## Was wir als Sicherheitsproblem behandeln

- Eine Freigabe lässt sich ohne berechtigte Rolle, unter Umgehung des
  Vier-Augen-Prinzips oder trotz fehlgeschlagener blockierender Vorprüfung
  erteilen (`approval`, `authz`).
- Eine Änderung, Löschung oder Umordnung im Audit-Trail bleibt bei
  `verify()` unentdeckt, obwohl die dokumentierten Voraussetzungen erfüllt
  sind (bei Kürzung: externer Kopf-Anker; bei Neuberechnung: HMAC-Schlüssel).
- Der bexio-Adapter bucht trotz fehlender Belegprüfung oder über den
  konfigurierten Limiten.
- Der Validator lässt einen Fall durch, den eine dokumentierte Regel als
  Fehler einstufen müsste (Umgehung des Policy-Gates).
- Geheimnisse oder Personendaten im Code, in Tests oder Beispielen.

## Was kein Sicherheitsproblem ist

- Grenzen, die in [docs/grenzen.md](docs/grenzen.md) beschrieben sind, z. B.
  dass Selbstauskünfte in einer Use-Case-Beschreibung falsch sein können oder
  dass jemand mit Schreibzugriff ohne HMAC-Schlüssel die ganze Kette neu
  berechnen kann.
- Fehlentscheide eines Sprachmodells an sich.

## Ablauf

Wir bestätigen den Eingang in der Regel innert fünf Arbeitstagen, prüfen den
Befund und stimmen Behebung und Veröffentlichung mit Ihnen ab. Behobene
Lücken erscheinen im [CHANGELOG](CHANGELOG.md); auf Wunsch nennen wir Sie dort.

## Unterstützte Versionen

| Version | Sicherheitskorrekturen |
|---|---|
| 2.x | ja |
| 1.x | nein |
