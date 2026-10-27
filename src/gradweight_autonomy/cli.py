"""Kommandozeile ``gw-autonomy``.

Exit-Codes:

* ``0``: keine Befunde ab der Schwelle ``--fail-on`` (Standard: Fehler) bzw. Kette intakt
* ``1``: mindestens ein Befund ab der Schwelle bzw. Kette verletzt
* ``2``: Aufruf- oder Eingabefehler (Datei fehlt, ungültige Option, kein Fall gefunden)
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from gradweight_autonomy import __version__
from gradweight_autonomy.audit import (
    AuditConfigurationError,
    AuditTrail,
    VerificationResult,
    parse_head,
    verify_jsonl,
)
from gradweight_autonomy.validator.docs import rules_json, rules_markdown, rules_text
from gradweight_autonomy.validator.engine import CaseReport, validate_path, validate_text
from gradweight_autonomy.validator.jsonschema_lite import SCHEMA_RESOURCE
from gradweight_autonomy.validator.model import Severity
from gradweight_autonomy.validator.report import render_json, render_sarif, render_text

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2
ENV_AS_OF = "GW_AUTONOMY_AS_OF"

_THRESHOLDS: dict[str, Severity | None] = {
    "error": Severity.ERROR,
    "warning": Severity.WARNING,
    "note": Severity.NOTE,
    "never": None,
}


class UsageError(Exception):
    """Fehler im Aufruf; führt zu Exit-Code 2."""


def _parse_date(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"ungültiges Datum {text!r} (erwartet JJJJ-MM-TT)"
        ) from exc


def _default_as_of() -> date:
    env = os.environ.get(ENV_AS_OF)
    if env:
        try:
            return date.fromisoformat(env)
        except ValueError as exc:
            raise UsageError(f"{ENV_AS_OF}={env!r} ist kein Datum (JJJJ-MM-TT)") from exc
    return date.today()  # noqa: DTZ011 - Stichtag ist ein Kalenderdatum


def _expand(paths: Sequence[str]) -> list[str]:
    files: list[str] = []
    for raw in paths:
        if raw == "-":
            files.append(raw)
            continue
        p = Path(raw)
        if p.is_dir():
            found = sorted(str(f) for f in p.glob("*.json") if f.is_file())
            if not found:
                raise UsageError(f"{raw}: keine .json-Dateien im Verzeichnis")
            files.extend(found)
        elif p.is_file():
            files.append(raw)
        else:
            raise UsageError(f"{raw}: Datei oder Verzeichnis nicht gefunden")
    return files


def _cmd_validate(args: argparse.Namespace) -> int:
    as_of: date = args.as_of or _default_as_of()
    threshold = _THRESHOLDS[args.fail_on]
    reports: list[CaseReport] = []
    for item in _expand(args.paths):
        if item == "-":
            reports.append(validate_text(sys.stdin.read(), source="<stdin>", as_of=as_of))
            continue
        try:
            reports.append(
                validate_path(item, as_of=as_of, check_evidence_files=args.check_evidence)
            )
        except (OSError, UnicodeDecodeError) as exc:
            raise UsageError(f"{item}: nicht lesbar ({exc})") from exc
    exit_code = EXIT_FINDINGS if any(r.fails(threshold) for r in reports) else EXIT_OK
    text = render_text(reports, threshold=threshold, exit_code=exit_code)
    if args.format == "json":
        rendered = render_json(reports, threshold=threshold, as_of=as_of, exit_code=exit_code)
    elif args.format == "sarif":
        rendered = render_sarif(reports)
    else:
        rendered = text
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
        sys.stdout.write(text)
    else:
        sys.stdout.write(rendered)
    return exit_code


def _cmd_rules(args: argparse.Namespace) -> int:
    render = {"markdown": rules_markdown, "json": rules_json, "text": rules_text}[args.format]
    sys.stdout.write(render())
    return EXIT_OK


def _cmd_schema(_: argparse.Namespace) -> int:
    from importlib import resources  # noqa: PLC0415 - nur hier gebraucht

    text = (
        resources.files("gradweight_autonomy.validator")
        .joinpath("schemas")
        .joinpath(SCHEMA_RESOURCE)
        .read_text(encoding="utf-8")
    )
    sys.stdout.write(text)
    return EXIT_OK


def _hmac_key(env_name: str | None) -> bytes | None:
    if not env_name:
        return None
    value = os.environ.get(env_name)
    if not value:
        raise UsageError(f"Umgebungsvariable {env_name} ist nicht gesetzt")
    try:
        key = bytes.fromhex(value)
    except ValueError as exc:
        raise UsageError(f"{env_name} muss den Schlüssel hexadezimal enthalten") from exc
    if len(key) < 16:
        raise UsageError(f"{env_name}: Schlüssel muss mindestens 16 Bytes (32 Hex-Zeichen) haben")
    return key


def _head(text: str | None) -> tuple[int, str] | None:
    if text is None:
        return None
    try:
        return parse_head(text)
    except ValueError as exc:
        raise UsageError(str(exc)) from exc


def _print_verification(result: VerificationResult) -> int:
    sys.stdout.write(result.summary() + "\n")
    for problem in result.problems:
        sys.stdout.write(f"  Eintrag {problem.seq}: {problem.kind}: {problem.detail}\n")
    return EXIT_OK if result.ok else EXIT_FINDINGS


def _open_trail(path: str, key: bytes | None) -> AuditTrail:
    if not Path(path).is_file():
        raise UsageError(f"{path}: Datenbank nicht gefunden")
    try:
        return AuditTrail(path, hmac_key=key)
    except AuditConfigurationError as exc:
        raise UsageError(str(exc)) from exc


def _cmd_audit(args: argparse.Namespace) -> int:
    key = _hmac_key(args.hmac_key_env)
    if args.audit_command == "verify-export":
        if not Path(args.file).is_file():
            raise UsageError(f"{args.file}: Datei nicht gefunden")
        try:
            result = verify_jsonl(args.file, key=key, expected_head=_head(args.expect_head))
        except ValueError as exc:
            raise UsageError(str(exc)) from exc
        return _print_verification(result)
    with _open_trail(args.db, key) as trail:
        if args.audit_command == "verify":
            return _print_verification(trail.verify(expected_head=_head(args.expect_head)))
        target = Path(args.output)
        if args.format == "csv":
            trail.export_csv(target)
        else:
            trail.export_jsonl(target)
        seq, head_hash = trail.head()
        sys.stdout.write(
            f"{trail.count()} Einträge exportiert nach {target}; Kopf {seq}:{head_hash}\n"
        )
        return EXIT_OK


def _cmd_demo(_: argparse.Namespace) -> int:
    from gradweight_autonomy.demo import main as demo_main  # noqa: PLC0415 - nur bei Bedarf laden

    return demo_main()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gw-autonomy",
        description="Autonomiegrade für KI in KMU-Prozessen: Validator und Audit-Werkzeuge.",
        epilog="Exit-Codes: 0 = bestanden, 1 = Befunde ab Schwelle bzw. Kette verletzt, "
        "2 = Aufruf- oder Eingabefehler.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    val = sub.add_parser("validate", help="Use-Case-Beschreibungen prüfen")
    val.add_argument("paths", nargs="+", help="Dateien, Verzeichnisse (*.json) oder - für stdin")
    val.add_argument("--format", choices=("text", "json", "sarif"), default="text")
    val.add_argument("--output", "-o", help="Bericht in Datei schreiben (Text bleibt auf stdout)")
    val.add_argument(
        "--fail-on",
        choices=tuple(_THRESHOLDS),
        default="error",
        help="ab welchem Schweregrad Exit-Code 1 (Standard: error)",
    )
    val.add_argument(
        "--check-evidence",
        action="store_true",
        help="lokale Nachweis-Dateien prüfen (Existenz, SHA-256)",
    )
    val.add_argument(
        "--as-of",
        type=_parse_date,
        help=f"Stichtag für Nachweis-Alter (Standard: heute oder ${ENV_AS_OF})",
    )
    val.set_defaults(func=_cmd_validate)

    rules = sub.add_parser("rules", help="Regelwerk ausgeben")
    rules.add_argument("--format", choices=("text", "markdown", "json"), default="text")
    rules.set_defaults(func=_cmd_rules)

    schema = sub.add_parser("schema", help="JSON Schema der Use-Case-Beschreibung ausgeben")
    schema.set_defaults(func=_cmd_schema)

    audit = sub.add_parser("audit", help="Audit-Trail prüfen und exportieren")
    audit_sub = audit.add_subparsers(dest="audit_command", required=True)
    key_help = "Name der Umgebungsvariable mit dem HMAC-Schlüssel (hexadezimal)"
    head_help = "extern verankerter Kopf SEQ:HASH"
    verify = audit_sub.add_parser("verify", help="Hash-Kette einer Datenbank prüfen")
    verify.add_argument("db")
    verify.add_argument("--hmac-key-env", help=key_help)
    verify.add_argument("--expect-head", help=head_help)
    export = audit_sub.add_parser("export", help="Kette exportieren (JSONL oder CSV)")
    export.add_argument("db")
    export.add_argument("--output", "-o", required=True)
    export.add_argument("--format", choices=("jsonl", "csv"), default="jsonl")
    export.add_argument("--hmac-key-env", help=key_help)
    vexp = audit_sub.add_parser("verify-export", help="JSONL-Export ohne Datenbank prüfen")
    vexp.add_argument("file")
    vexp.add_argument("--hmac-key-env", help=key_help)
    vexp.add_argument("--expect-head", help=head_help)
    audit.set_defaults(func=_cmd_audit)

    demo = sub.add_parser("demo", help="Durchgang Grad 2 mit fiktiven Daten (ohne Netzwerk)")
    demo.set_defaults(func=_cmd_demo)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse: --help (0) oder Aufruffehler (2)
        return int(exc.code) if isinstance(exc.code, int) else EXIT_USAGE
    try:
        code: int = args.func(args)
    except UsageError as exc:
        sys.stderr.write(f"gw-autonomy: {exc}\n")
        return EXIT_USAGE
    return code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
