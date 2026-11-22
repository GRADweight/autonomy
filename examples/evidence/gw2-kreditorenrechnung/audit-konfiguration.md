# Konfiguration Audit-Trail und Belegprüfung vor Buchung

Fiktives Beispiel für gradweight-autonomy, keine echten Daten.

- Jede Freigabe und jede Buchung landet im AuditTrail (HMAC).
- Vor der Buchung: invoice_checks.check_invoice (IBAN, QR-Referenz, MWST) als blockierende Vorprüfung.
