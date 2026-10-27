# Grenzen

Was dieses Repo **nicht** leistet. Diese Liste ist Teil der Dokumentation, kein
Kleingedrucktes.

## Validator

- **Selbstauskunft bleibt Selbstauskunft.** Der Validator prüft
  Widerspruchsfreiheit, Pflichtkontrollen und Nachweise (Typ, Datum, Datei,
  Hash). Er prüft nicht, ob ein Nachweis inhaltlich stimmt oder ob das System
  sich so verhält, wie beschrieben. Eine falsche Beschreibung mit plausiblen
  Nachweisen besteht. Der Validator ist ein Gate und eine Arbeitsliste, keine
  Revision.
- **Das Modell ist eine Setzung.** Grade, Achsen, Deckel und die maximalen
  Nachweisalter (180 bzw. 365 Tage) sind begründete Annahmen von GRADweight,
  keine Normen. Wer andere Schwellen braucht, passt `model.py` an.
- **Kein Rechtsrat.** Die Regeln verweisen auf Vorschriften
  ([Regulatorik](regulatorik.md)), ersetzen aber keine rechtliche Beurteilung.

## Bausteine

- **Keine Laufzeitumgebung für Agenten.** Orchestrierung, Werkzeuganbindung,
  Bereitstellung von Agenten-Identitäten und der Notaus selbst sind nicht Teil
  des Repos. Die Bausteine decken Freigabe, Protokoll, Vorprüfung, Ausnahmen,
  Stichproben und Rollback-Register ab.
- **Keine Authentisierung.** `approval` und `authz` prüfen die übergebene
  Rolle. Wer diese Rolle tragen darf, entscheidet das umgebende System.
- **Audit-Trail erkennt, verhindert nicht.** Kürzungen am Ende werden nur mit
  externem Kopf-Anker erkannt, eine vollständige Neuberechnung nur mit
  HMAC-Schlüssel oder Anker. Zeitstempel stammen aus der lokalen Uhr. Details:
  [Audit-Trail](audit-trail.md).
- **Zustandstabellen sind nicht verkettet.** Queue, Ausnahme- und
  Rollback-Tabellen werden aktualisiert; nachvollziehbar sind ihre Übergänge
  über die Audit-Einträge, die bei jedem Schritt geschrieben werden.
- **Stichproben sind systematisch.** Wer die Schrittweite kennt, kann sie
  umgehen. In adversarialen Umgebungen eine zufällige Auswahl ergänzen.

## Zahlenabgleich und Zweitmodell

- Nur Zahlen, Daten und Kennungen werden geprüft; Aussagen ohne Zahl und
  falsche Zuordnungen bleiben unerkannt.
- Bekannte Fehlalarme: Zahlen ohne Beleg wie «in 2 Schritten», Satztrennung
  an Abkürzungen bei Zitierpflicht. Bekannte Lücke: Tausendertrennung mit
  gewöhnlichem Leerzeichen.
- Das optionale Zweitmodell ist fehlbar und manipulierbar; es blockiert bei
  Ausfall.

## Belegprüfung und bexio

- Plausibilität, nicht Echtheit einer Rechnung; nur CH/LI-IBAN, MWST-Sätze ab
  2018, keine Sondertatbestände.
- Die bexio-Feldzuordnung folgt der öffentlichen API-Dokumentation (Stand
  Oktober 2026). Gegen ein echtes bexio-Konto wurde im Repo **nicht** getestet;
  die Tests nutzen einen simulierten Transport. `tax_id` und
  `booking_account_id` stammen aus der jeweiligen bexio-Instanz.
- Die Limiten des Adapters sind clientseitig. Als Grenze «im Zielsystem»
  zählen sie nur, wenn der Adapter in einem eigenen Dienst läuft, der das
  Token hält und den der Agent nicht umgehen kann.
- Kein automatischer Retry bei Buchungen; ein unklarer Ausgang muss manuell
  abgeglichen werden.
