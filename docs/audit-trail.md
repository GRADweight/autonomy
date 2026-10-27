# Audit-Trail mit Hash-Kette

`gradweight_autonomy.audit.AuditTrail` speichert Einträge in SQLite. Jeder
Eintrag ist mit seinem Vorgänger verkettet; nachträgliche Änderungen werden
bei der Prüfung sichtbar.

## Aufbau eines Eintrags

| Feld | Inhalt |
|---|---|
| `seq` | Laufnummer ab 1, lückenlos |
| `ts` | Zeitstempel UTC (ISO 8601, Mikrosekunden) aus der Systemuhr |
| `tenant`, `use_case` | Mandant und Anwendungsfall |
| `actor`, `action` | wer was getan hat |
| `details` | JSON-Objekt mit den nötigen Angaben (keine Prompts, keine ganzen Datensätze) |
| `prev_hash` | Hash des Vorgängers; beim ersten Eintrag 64 Nullen |
| `entry_hash` | Hash dieses Eintrags |

`entry_hash` = SHA-256 (ohne Schlüssel) bzw. HMAC-SHA-256 (mit Schlüssel)
über das kanonische JSON von

```text
{"action", "actor", "details", "prev", "seq", "tenant", "ts", "use_case", "v": "gw-audit-v1"}
```

Kanonisch heisst: UTF-8, Schlüssel sortiert, keine Leerzeichen, kein NaN.
Für Strings, Ganzzahlen, Booleans und `null` entspricht das RFC 8785;
Fliesskommazahlen werden in Pythons `repr`-Form geschrieben. Beträge deshalb
als String oder in Rappen ablegen. Die Funktion
`gradweight_autonomy.audit.entry_payload` erzeugt genau diese Bytes und kann
für eine unabhängige Prüfung nachgebaut werden.

## Prüfen

```python
from gradweight_autonomy.audit import AuditTrail

with AuditTrail("audit.db", hmac_key=key) as trail:
    result = trail.verify(expected_head=(1842, "9f3c..."))
    print(result.summary())
```

oder auf der Kommandozeile:

```bash
gw-autonomy audit verify audit.db --hmac-key-env GW_AUDIT_KEY --expect-head 1842:9f3c...
gw-autonomy audit export audit.db -o audit.jsonl
gw-autonomy audit verify-export audit.jsonl --expect-head 1842:9f3c...
```

`verify()` meldet je Befund Laufnummer und Art: `gap` (Lücke), `order`
(Laufnummer zu klein), `link` (Vorgänger passt nicht), `hash` (Inhalt
verändert), `anchor` (verankerter Kopf weicht ab oder fehlt).

## Was erkannt wird – und was nicht

| Eingriff | erkannt? | Voraussetzung |
|---|---|---|
| Feld eines Eintrags ändern | ja | – |
| Eintrag in der Mitte oder am Anfang löschen | ja | – |
| Einträge umordnen oder einschieben | ja | – |
| letzte Einträge abschneiden | ja | externer Kopf-Anker (`expected_head`) |
| ganze Kette ab einem Punkt neu berechnen | ja | HMAC-Schlüssel, den der Angreifer nicht hat, **oder** externer Anker |
| Eingriff verhindern | nein | – |
| falsche Angaben beim Schreiben | nein | – |

SQLite-Trigger blockieren `UPDATE` und `DELETE` über die normale Verbindung;
das schützt vor Versehen, nicht vor jemandem mit Dateizugriff. Die Tests in
`tests/test_audit.py` entfernen die Trigger und manipulieren die Datei direkt,
um genau diese Fälle zu belegen.

## Betrieb

- **Kopf verankern.** `trail.head()` liefert `(seq, hash)`. Diesen Wert
  regelmässig ausserhalb der Datenbank ablegen: unveränderbarer Speicher
  (WORM), Ticket-System, signierter Git-Commit oder ein qualifizierter
  Zeitstempel nach RFC 3161.
- **HMAC-Schlüssel** mindestens 16 Bytes, besser 32, zufällig erzeugt, aus
  einem Secret-Store; nicht auf demselben System wie die Datenbank ablegen.
  Die Datenbank speichert nur eine Schlüssel-ID; ein falscher oder fehlender
  Schlüssel führt zu einem Fehler statt zu einer stillen Prüfung ohne HMAC.
- **Zeitstempel** stammen aus der lokalen Uhr und sind keine vertrauenswürdige
  Zeitquelle.
- **Mehrere Prozesse** dürfen in dieselbe Datei schreiben; `BEGIN IMMEDIATE`
  serialisiert das Anhängen.
- **Datenminimierung.** Personendaten nur, soweit für die Nachvollziehbarkeit
  nötig; die Kette lässt sich nicht nachträglich bereinigen, ohne sie zu brechen.
