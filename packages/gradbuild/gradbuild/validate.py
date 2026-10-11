"""gradBuild-Validator: prüft Use-Case-Beschreibungen gegen die Regeln GB-01…GB-16.

Die Regeln sind 1:1 mit README, Abschnitt "Regeln" abgeleitet. jede Regel
läuft unabhängig; die Ausgabe ist deterministisch sortiert.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from . import schema

SEVERITIES = ("error", "warn", "info")


@dataclass
class Finding:
    rule: str          # z.B. "GB-05"
    severity: str      # error | warn | info
    level: int         # Grad, auf den die Prüfung angewandt wurde
    message: str
    detail: str = ""   # Begründung / Referenz (README-Abschnitt)


@dataclass
class CaseReport:
    case_id: str
    findings: List[Finding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(f.severity == "error" for f in self.findings)

    def errors(self) -> List[Finding]:
        return [f for f in self.findings if f.severity == "error"]

    def warnings(self) -> List[Finding]:
        return [f for f in self.findings if f.severity == "warn"]


def _find(rep: CaseReport, rule: str, severity: str, level: int, message: str, detail: str = "") -> None:
    rep.findings.append(Finding(rule, severity, level, message, detail))


def _bool(case: dict, key: str) -> bool:
    return bool(case.get(key, False))


def _steps(case: dict) -> list:
    steps = case.get("steps")
    return steps if isinstance(steps, list) else []


def _step_effect(step: Any) -> bool:
    if not isinstance(step, dict):
        return False
    # Wirkung = Zustand ändern, extern kommunizieren oder Geld berühren.
    return any(_bool(step, k) or step.get(k) is True for k in ("state_change", "external", "money"))


def _step_plans(step: dict) -> str:
    return str(step.get("planned_by", "model"))


def _step_role(step: dict) -> str:
    return str(step.get("human_role", "none"))


def _effective_role(case: dict, steps: list) -> str:
    """Wirksamste menschliche Rolle über alle wirkungsvollen Schritte (Achtung: am stärksten = am wenigsten Eingriff)."""
    ranking = {"none": 5, "exception_only": 4, "mandate": 3, "per_gate": 2, "per_action": 1, "full_control": 0}
    best = "full_control"
    for s in steps:
        if not isinstance(s, dict) or not _step_effect(s):
            continue
        role = _step_role(s)
        if role not in ranking:
            continue
        if ranking.get(role, 0) > ranking[best]:
            best = role
    return best


def level_from_axes(case: dict) -> int:
    """Empfohlener Grad = autonomster wirkungsvoller Schritt (Wer plant + wo greift Mensch ein)."""
    who = case.get("who_plans")
    role = case.get("human_role")
    combo = (who, role)
    for lv in (0, 1, 2, 3, 4, 5):
        if combo in schema.ALLOWED_AXES[lv]:
            return lv
    # Fallback: kombiniere (who_plans, human_role) über die erlaubte Menge.
    return 0


def evaluate_case(case: dict) -> CaseReport:
    """GB-01…GB-16 auf einen Use Case (Schema-Objekt) anwenden."""
    rep = CaseReport(case_id=str(case.get("id", "<unknown>")))

    # --- GB-01: Schema -----------------------------------------------------
    for e in schema.schema_errors(case):
        _find(rep, "GB-01", "error", int(case.get("level", 0) or 0), "Schema: " + e)
    if rep.errors():
        # Struktur kaputt → weitere Regeln werden nicht zuverlässig geprüft.
        return _finalize(rep)

    level = case["level"]
    who = case["who_plans"]
    role = case["human_role"]
    steps = _steps(case)
    foreign = _bool(case, "foreign_input")
    sensitive = _bool(case, "sensitive_data")
    external = _bool(case, "external_action")
    money = _bool(case, "money_effect")
    cust_facing = _bool(case, "customer_facing")
    cust_text = _bool(case, "customer_text_in_decisions")
    safety = _bool(case, "safety_critical")
    gov = case.get("governance") or {}

    # --- GB-02: Achsen stimmen überein -------------------------------------
    if (who, role) not in schema.ALLOWED_AXES[level]:
        _find(
            rep, "GB-02", "error", level,
            f"Achsen nicht erlaubt für Grad {level}: who_plans={who!r}, human_role={role!r}.",
            "Definitionen: Achse 1 (Wer plant) & Achse 2 (Wo greift Mensch ein). "
            "Erlaubte Kombinationen: " + str(sorted(map(str, schema.ALLOWED_AXES[level]))),
        )

    # --- GB-03: Rule of Two -------------------------------------------------
    # Meta 'Agents Rule of Two': pro Sitzung höchstens 2 von 3 — [A] fremde
    # Eingaben, [B] sensible Daten, [C] Zustandsänderung/Aussenwirkung.
    # Auf der gradBuild-Skala: Grad 0–3 (Mensch in der Kette) dürfen alle drei;
    # Grad >= 4 bricht die Kette STRUKTURELL — ein Mandat genügt NICHT.
    rule2 = (foreign, sensitive, external)
    rule2_count = sum(1 for x in rule2 if x)
    if rule2_count >= 3:
        if level > 3:
            _find(
                rep, "GB-03", "error", level,
                "Alle drei Rule-of-Two-Eigenschaften zugleich ([A] fremde Eingaben, [B] sensible Daten, "
                "[C] Aussenwirkung) — bei Grad >= 4 nicht zulässig, auch nicht mit Mandat.",
                "Meta 'Agents Rule of Two' (2025): solange sich Prompt-Injection nicht zuverlässig "
                "erkennen lässt, höchstens 2 von 3 pro Sitzung. Grad 0–3 erlaubt alle drei, weil der "
                "Mensch die Kette bricht. Grad >= 4 muss mindestens eine Eigenschaft strukturell "
                "entfernen: Kundentexte isoliert klassifizieren (entfernt A für den Entscheid-Agenten), "
                "oder nur vertrauenswürdige Quellen (ERP/EDI statt Freitext), oder keine Aussenwirkung. "
                "EchoLeak (M365 Copilot, 2025) zeigt, wie die Kette sonst ausgehebelt wird.",
            )
        else:
            _find(
                rep, "GB-03", "warn", level,
                "Alle drei Rule-of-Two-Eigenschaften zugleich — erlaubt nur, weil Grad <= 3 und menschliches Eintreten die Kette bricht.",
                "Prüfe, dass der Mensch wirklich an jedem wirkungsvollen Punkt dazwischen ist. "
                "Meta Rule of Two & EchoLeak (M365 Copilot, 2025).",
            )

    # --- GB-04: Deckel übersteigt -------------------------------------------
    ceiling = case.get("ceiling")
    if isinstance(ceiling, dict):
        max_level = ceiling.get("max_level")
        if isinstance(max_level, int) and level > max_level:
            _find(
                rep, "GB-04", "error", level,
                f"Grad {level} überschreitet Deckel max_level={max_level} "
                f"(Grund: {ceiling.get('reason', '?')}; Rechtsgrundlage: {ceiling.get('regulation', '?')}).",
                "Deckel sind politisch gesetzt und dürfen nur die Instanz aufheben, die die "
                "Policy verabschiedet hat. Ausnahmen befristet, nur gegen 'machbar' (GB-05).",
            )
        # info: Deckel vorhanden
        else:
            _find(
                rep, "GB-04", "info", level,
                f"Deckel vorhanden (max_level={max_level}, Grund: {ceiling.get('reason', '?')}).",
            )

    # --- GB-05: Ausnahmen gegen 'erlaubt' -------------------------------------
    if cust_facing and not cust_text and level >= 4:
        pass  # ok, Kundentexte fließen NICHT ein.
    if cust_text and (cust_facing or foreign):
        _find(
            rep, "GB-05", "warn", level,
            "customer_text_in_decisions=true: fremde Inhalte fließen in Entscheidungen ein.",
            "Grad-5-Retouren: ein separates Modell ohne Tools klassifiziert Kundentexte; "
            "Entscheidungen beruhen nur auf strukturierten Daten (Meta Rule of Two, "
            "Singapur MGF 2026 — 'Bound the risks upfront').",
        )

    # --- GB-06: Sicherheit — Schutzfunktionen -------------------------------
    if safety:
        if level > 3:
            _find(
                rep, "GB-06", "error", level,
                "safety_critical=true und Grad > 3 — Schutzfunktionen bleiben ausserhalb der KI.",
                "Produktion & Technik: KI 'neben, nie in der Sicherheitskette'. "
                "Maschinenverordnung (EU 2023/1230, in Kraft seit 2027) und ISO/IEC TR 5469 "
                "lassen in-silico lernende Systeme praktisch nicht zu. "
                "Deckel 2: in-schutzwirksame Funktionen höchstens Grad 3.",
            )
        else:
            _find(
                rep, "GB-06", "warn", level,
                "safety_critical=true — Deckel 2 aktiv: höchstens Grad 3.",
                "Deckel 2 (README Abschnitt 'Deckel').",
            )

    # --- GB-07: Automation Bias / Übernahmequote --------------------------------
    ceiling = case.get("ceiling")
    adoption = _bool(gov, "adoption_rate_monitored")
    if level == 2 and not adoption:
        _find(
            rep, "GB-07", "error", level,
            "Grad 2: Übernahmequote wird nicht überwacht (adoption_rate_monitored=false).",
            "Singapore MGF 2026 & Art. 21 DSG: bei fast-bestätigten Vorschlägen ist die "
            "menschliche Entscheidung nur noch Durchklicken (Automation Bias). "
            "Stichproben oder Begründungspflicht nötig.",
        )
    if level == 2 and adoption:
        _find(rep, "GB-07", "info", level, "Übernahmequote wird überwacht — Deckel 1 (Anhang III) aktiv.", "Grad 2 ist gedeckelt; siehe GB-04.")

    # --- GB-08: Mandat mit Limiten im System ----------------------------------
    if role == "mandate":
        mandate = case.get("mandate")
        limits_in_system = bool(mandate.get("limits_in_system")) if isinstance(mandate, dict) else False
        if not limits_in_system:
            _find(
                rep, "GB-08", "error", level,
                "human_role='mandate', aber mandate.limits_in_system=false (oder mandate fehlt).",
                "Limiten (Betrag, Empfängerkreis, Zeitraum) gehören in das Zielsystem "
                "(Berechtigung, Schnittstelle, Zahlungslimite) — NICHT in den Prompt. "
                "C-Teile nachbestellen: Limite als ERP-Freigabestrategie, nicht im Prompt.",
            )
    if level == 4 and role == "exception_only":
        # Exception-only ist die Rolle von Grad 5; wer sie bei Grad 4 beansprucht,
        # muss die Grad-5-Leitplanken führen (umkehrbar, nicht kritisch — README).
        _find(
            rep, "GB-08", "warn", level,
            "Grad 4 mit human_role='exception_only' — übernimmt Grad-5-Leitplanken (Exception-Queue, Stichprobenaudit).",
            "README: 'Wer die Gates öffnet, übernimmt die Leitplanken der nächsthöheren Stufe (umkehrbar, nicht kritisch).'",
        )

    # --- GB-09: Geldwirkung + Geldpfad ------------------------------------------
    if money:
        if level == 3 and role == "per_gate":
            _find(rep, "GB-09", "info", level, "Geldwirkung + Gate — Kreditoren-Workflow OK (Gate vor Auszahlung).")
        elif level >= 4 and money:
            if not (isinstance(case.get("mandate"), dict) and case.get("mandate", {}).get("money_limit")):
                _find(
                    rep, "GB-09", "warn", level,
                    "Geldwirkung bei Grad >= 4 ohne mandate.money_limit.",
                    "Grad 4/5: Mandat mit Betrag, Empfängerkreis, Zeitraum definiert. "
                    "Kontenabstimmung: Umbuchungen bis Schwelle (umkehrbar), darüber Vorschlag.",
                )

    # --- GB-10: Customer-facing Grad 1: kein external/foreign -----------------------
    if level == 1 and external and not sensitive:
        # Grad 1: kein externer Effekt (z.B. keine ausgehenden E-Mails)
        _find(
            rep, "GB-10", "error", level,
            "Grad 1: keine Aussenwirkung (external=true).",
            "Grad 1: 'keine Aussenwirkung, also keine Sende-Werkzeuge und keine "
            "externen Links oder Bilder in Antworten' (README, Section 'Grad 1 Assistent').",
        )
    if level == 1 and foreign and external:
        # Alle drei gleichzeitig wäre GB-03-Ablage
        pass

    # --- GB-11: Identität & minimale Rechten -----------------------------------------
    agent_identity = _bool(gov, "agent_identity_min_privilege")
    audit_log = _bool(gov, "audit_log")
    if level >= 4 and not agent_identity:
        _find(
            rep, "GB-11", "error", level,
            "Grad >= 4: jeder Agent braucht eine eigene Identität mit minimalen Rechten.",
            "README Section 'Systeme und Architekturen pro Grad' → 'Ab Grad 4 bekommt "
            "jeder Agent eine Identität (Entra Agent ID oder Servicekonto).' "
            "Singapur MGF: 'identity management and access controls for agents'.",
        )
    if level >= 4 and not audit_log:
        _find(
            rep, "GB-11", "error", level,
            "Grad >= 4: audit_log fehlt (Beobachtbarkeit über OpenTelemetry/Langfuse).",
        )
    if level == 5 and not (
        _bool(gov, "exception_queue")
        and _bool(gov, "sampling_audit")
        and _bool(gov, "agent_identity_min_privilege")
        and _bool(gov, "audit_log")
    ):
        _find(
            rep, "GB-11", "error", level,
            "Grad 5: fehlende Kontrollen (exception_queue, sampling_audit, agent_identity, audit_log).",
            "README Section 'Grad 5 Autonom': 'Eine deterministische Policy-Schicht "
            "für Geld und Daten, Ausnahmequeue, Stichprobenaudit.',",
        )

    # --- GB-12: Auf-/Rückstufung -----------------------------------------------------
    auto_rollback = _bool(gov, "automatic_rollback")
    kill_test = _bool(gov, "kill_switch_tested")
    new_on_change = _bool(gov, "decides_new_on_model_prompt_tool_change")
    if level >= 3:
        if not auto_rollback:
            _find(
                rep, "GB-12", "error", level,
                "automatic_rollback=false — bei Schwellenriss muss die Rückstufung technisch automatisch greifen.",
                "README Section 'Absichern': 'Bei einem Schwellenriss sollte die "
                "Rückstufung technisch automatisch greifen, nicht erst nach einer Sitzung.'",
            )
        if not kill_test:
            _find(
                rep, "GB-12", "error", level,
                "kill_switch_tested=false — der Notaus muss vor dem Stufenentscheid geprobt werden.",
            )
        if not new_on_change:
            _find(
                rep, "GB-12", "warn", level,
                "decides_new_on_model_prompt_tool_change=false — jeder Modell-/Prompt-/Toolwechsel muss einen neuen Stufenentscheid lösen.",
                'README Section "Absichern": "Jeder Wechsel von Modell, Prompt oder Tool '
                'löst einen neuen Stufenentscheid aus."',
            )

    # --- GB-13: Schattenbetrieb --------------------------------------------------------
    shadow = _bool(gov, "shadow_run_first")
    proposal = _bool(gov, "proposal_mode_first")
    if level >= 4 and not shadow:
        _find(
            rep, "GB-13", "error", level,
            "shadow_run_first=false — der neue Grad muss zuerst im Schattenbetrieb mitlaufen.",
        )
    if level >= 4 and not proposal:
        _find(
            rep, "GB-13", "error", level,
            "proposal_mode_first=false — erst Vorschlagsmodus, dann Mandat (README: 'Zielarchitektur bauen, Freigabe strenger stellen').",
        )

    # --- GB-14: Messung (pass^k / Schatten) ----------------------------------------------
    measurement = case.get("measurement")
    if isinstance(measurement, dict):
        method = measurement.get("method")
        if method == "pass^k":
            # pass^k gilt für wiederholbare Schritte
            if not steps:
                _find(rep, "GB-14", "warn", level, "measurement.pass^k ohne steps — Testset definiert?")
        elif method == "shadow":
            if not _bool(gov, "shadow_run_first"):
                _find(rep, "GB-14", "warn", level, "measurement.shadow ohne shadow_run_first.")
        else:
            _find(rep, "GB-14", "error", level, f"measurement.method={method!r} — erwartet 'pass^k' oder 'shadow'.")
    else:
        if level >= 3:
            _find(rep, "GB-14", "error", level, "Grad >= 3 ohne measurement (pass^k oder shadow).")

    # --- GB-15: Datenklasse / Residency ---------------------------------------------------
    data_class = case.get("data_class")
    residency = case.get("data_residency")
    if sensitive and data_class in (None, "frei"):
        _find(
            rep, "GB-15", "error", level,
            "sensitive_data=true, aber data_class nicht festgelegt.",
            "Datenklassen: frei / intern / vertraulich / geheim (README Section 'Datenklassen').",
        )
    if level >= 4 and data_class == "geheim":
        _find(
            rep, "GB-15", "error", level,
            "data_class='geheim' bei Grad >= 4 — erlaubte Varianten: on-prem ohne Netz, oder keine KI.",
            'ReadMe Section "Betriebsoption nach Datenklasse" → "Geheim: keine KI oder nur on-prem ohne Netz."',
        )
    if residency is not None and residency not in schema.RESIDENCIES:
        # Schema-Fehler bereits gemeldet, hier nur zusätzlich warnen.
        pass

    # --- GB-16: Achsen-Konsistenz bei Schritte-Definition -------------------------------
    if steps:
        for i, s in enumerate(steps):
            if not isinstance(s, dict):
                continue
            sp_role = _step_role(s)
            sp_who = _step_plans(s)
            if _step_effect(s) and (sp_who, sp_role) not in schema.ALLOWED_AXES[level]:
                _find(
                    rep, "GB-16", "error", level,
                    f"Schritt #{i}: Achsen ({sp_who!r}, {sp_role!r}) nicht erlaubt für Grad {level}.",
                )
            # Wirkung im Schritt ohne Rolle? → Mensch fehlt komplett
            if _step_effect(s) and sp_role == "none":
                _find(
                    rep, "GB-16", "warn", level,
                    f"Schritt #{i}: Wirkungsvoller Schritt ohne menschliche Rolle (human_role='none').",
                    'Falls gewollt (Grad 5), sorge für exception_queue + sampling_audit (GB-11).',
                )

    return _finalize(rep)


def _finalize(rep: CaseReport) -> CaseReport:
    # Deterministische Reihenfolge: nach severity (error, warn, info), dann rule, dann message
    sev_order = {"error": 0, "warn": 1, "info": 2}
    rep.findings.sort(key=lambda f: (sev_order.get(f.severity, 3), f.rule, f.message))
    return rep


def evaluate_paths(cases: Dict[str, dict]) -> Dict[str, CaseReport]:
    """Mehrere Fälle auf einmal; Rückgabe {case_id: CaseReport}."""
    return {cid: evaluate_case(c) for cid, c in cases.items()}
