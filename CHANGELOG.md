# CHANGELOG — autonomy

Format: `## vX.Y.Z — Datum — Kurzfassung`, darunter was/warum.
SemVer: major = inkompatibler Bruch, minor = neue Inhalte, patch = Korrektur.
Release-Prozess: SemVer, Changelog, Tag.

---

## Unreleased

- Lizenz vereinheitlicht: MIT im Root und in allen Unterpaketen
  (`license = "MIT"`); interne Notizen entfernt.

## v1.0.0 — 2026-10-12 — Public-Readiness (Launch 25.10.2026)

- **Lizenz MIT → Alle Rechte vorbehalten** (Entscheidung 12.10, Strategie
  «alles AR»): `LICENSE` (neu, GRADweight GmbH, Referenz-Nutzung +
  Attribution + Community-PR-Regel), `packages/gradbuild/LICENSE.md`
  (Verweis auf Repo-Root), `packages/{gradbuild,gw_core}/pyproject.toml`
  (`license`-Feld), `README.md` (§Lizenz).
- **Demo-Pfad** (neu): `packages/gw_core/gw_core/demo.py` —
  Vorschlag → Freigabe (Rollen-Policy `ai-lead`) → Zweitmodell-Prüfung
  → Audit-Trail in einem Durchlauf, deterministisch, `:memory:`, keine
  Datei-Rückstände. Launch: `python -m gw_core.demo --case examples/…`.
- **Tests (neu)**: `tests_gwcore/test_demo.py` (3 Tests: Datei existiert,
  Demo-Run → Exit 0, Policy verweigert unzulässige Rolle).
  Gesamtsuite: **87 Tests** (bisher 84).
- **CI (erweitert)**: Demo-Schritt in `.github/workflows/ci.yml`.
- **README**: Badges (CI, Py 3.11/3.12, zero-deps, Lizenz), Quickstart mit
  Demo-Befehl, Testzahl 84 → 87.
- **`docs/umsetzung/README.md`**: Stand-Zeile (Entscheidung 25.10).
- **R1 (Technik-Eröffnung) erfüllt**: Release-Prozess = SemVer +
  Changelog + Tag.

**Zustand 12.10 (verifiziert, Py 3.11): 87/87 Tests grün. Demo → Exit 0
mit Audit-Trail (2 Einträge: `aktion_vorgeschlagen`, `aktion_freigegeben`).**
