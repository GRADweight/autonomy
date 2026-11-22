"""Dokumentation gegen den Code prüfen: Zahlen, Beispiele, Links, Sprache."""

from __future__ import annotations

import doctest
import json
import re
import shlex
from pathlib import Path
from typing import Any

import pytest

from gradweight_autonomy import __version__
from gradweight_autonomy.cli import main
from gradweight_autonomy.validator import RULES
from gradweight_autonomy.validator.docs import rules_markdown, schema_markdown
from gradweight_autonomy.validator.model import LEVELS

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
SKIP_DIRS = {".git", ".venv", "venv", "dist", "build", "__pycache__", ".mypy_cache", ".ruff_cache"}
SKIP_DIRS |= {".pytest_cache", ".hypothesis", "htmlcov"}


def text_files(*suffixes: str) -> list[Path]:
    found = []
    for path in ROOT.rglob("*"):
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        if path.is_file() and path.suffix in suffixes:
            found.append(path)
    return sorted(found)


MARKDOWN = text_files(".md")


def blocks(text: str, marker: str) -> list[str]:
    pattern = rf"<!-- {marker} -->\n```[a-z]*\n(.*?)\n```"
    return re.findall(pattern, text, flags=re.S)


# ------------------------------------------------------------------ generierte Doku
def test_generated_rule_reference_is_current() -> None:
    assert (ROOT / "docs" / "regeln.md").read_text(encoding="utf-8") == rules_markdown()


def test_generated_schema_reference_is_current() -> None:
    assert (ROOT / "docs" / "schema.md").read_text(encoding="utf-8") == schema_markdown()


# ------------------------------------------------------------------ Zahlen im README
def test_rule_counts_in_readme_match_code() -> None:
    counts = {int(n) for n in re.findall(r"(\d+) (?:Regeln|rules)\b", README)}
    assert counts == {len(RULES)}
    assert "six autonomy grades (0–5)" in README
    assert "sechs Graden" in README
    assert len(LEVELS) == 6


def test_readme_does_not_state_test_counts() -> None:
    assert not re.search(r"\d+\s+(?:Tests|pytest-Tests|tests)\b", README)


# ------------------------------------------------------------------ ausführbare Beispiele
CONSOLE = blocks(README, "console")


@pytest.mark.parametrize("block", CONSOLE, ids=lambda b: b.splitlines()[0][:60])
def test_readme_console_output_is_real(
    block: str, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(ROOT)
    monkeypatch.delenv("GW_AUTONOMY_AS_OF", raising=False)
    command, *expected = block.splitlines()
    assert command.startswith("$ gw-autonomy ")
    code = main(shlex.split(command)[2:])
    out = capsys.readouterr().out
    assert out.rstrip("\n") == "\n".join(expected)
    assert out.rstrip().endswith(f"Exit-Code {code}.")


def test_readme_has_console_and_doctest_examples() -> None:
    assert len(CONSOLE) >= 2
    assert blocks(README, "doctest")


@pytest.mark.parametrize("block", blocks(README, "doctest"))
def test_readme_python_examples_run(block: str) -> None:
    parser = doctest.DocTestParser()
    test = parser.get_doctest(block, {}, "README", "README.md", 0)
    runner = doctest.DocTestRunner(optionflags=doctest.ELLIPSIS)
    runner.run(test)
    assert runner.failures == 0
    assert runner.tries > 0


def _is_subset(part: Any, whole: Any) -> bool:
    if isinstance(part, dict):
        return isinstance(whole, dict) and all(
            k in whole and _is_subset(v, whole[k]) for k, v in part.items()
        )
    if isinstance(part, list):
        return isinstance(whole, list) and all(
            i < len(whole) and _is_subset(v, whole[i]) for i, v in enumerate(part)
        )
    return bool(part == whole)


def test_readme_json_excerpt_matches_example() -> None:
    found = re.findall(r"<!-- excerpt:(\S+) -->\n```json\n(.*?)\n```", README, flags=re.S)
    assert found
    for rel, excerpt in found:
        source = json.loads((ROOT / rel).read_text(encoding="utf-8"))
        assert _is_subset(json.loads(excerpt), source), rel


def test_quickstart_commands_after_install_work(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Installation selbst prüft die CI (Job package); hier die Befehle danach."""
    monkeypatch.chdir(ROOT)
    match = re.search(r"<!-- quickstart:start -->\n```bash\n(.*?)\n```", README, flags=re.S)
    assert match
    lines = match.group(1).splitlines()
    assert "pip install ." in lines
    for line in lines:
        if line.startswith("gw-autonomy "):
            assert main(shlex.split(line)[1:]) == 0, line
    capsys.readouterr()


# ------------------------------------------------------------------ Links
@pytest.mark.parametrize("path", MARKDOWN, ids=lambda p: str(p.relative_to(ROOT)))
def test_relative_links_exist(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for target in re.findall(r"\]\(([^)\s]+)\)", text):
        if re.match(r"[a-z]+:", target) or target.startswith("#"):
            continue
        file_part, _, anchor = target.partition("#")
        resolved = (path.parent / file_part).resolve()
        assert resolved.exists(), f"{path.name}: {target}"
        if anchor and resolved.suffix == ".md":
            headings = re.findall(r"^#+ (.+)$", resolved.read_text(encoding="utf-8"), flags=re.M)
            slugs = {re.sub(r"[^\w\- ]", "", h.lower()).replace(" ", "-") for h in headings}
            assert anchor in slugs, f"{path.name}: {target}"


# ------------------------------------------------------------------ Versionen
def test_versions_agree() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert f'version = "{__version__}"' in pyproject
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [{__version__}]" in changelog


def test_license_is_plain_mit() -> None:
    text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert text.startswith("MIT License\n\nCopyright (c) 2026 GRADweight GmbH\n")
    assert text.rstrip().endswith("SOFTWARE.")
    assert 'license = "MIT"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")


# ------------------------------------------------------------------ Interna und Sprache
# Aus Teilen zusammengesetzt, damit diese Datei selbst nicht auf die Suche anspricht.
_FORBIDDEN_TERMS = (
    ("noch NICHT", " public"),
    ("Pruefen vor", " Public"),
    ("Talent", "-Signal"),
    ("Ed", "in"),
    ("/Us", "ers/"),
    ("ed", "in@"),
    ("Lach", "nummer"),
    ("EVAL", "UATION"),
    ("edd", "avv"),
    ("internal", "-kb"),
    ("PROJEKT", ".md"),
)
FORBIDDEN = re.compile("|".join(re.escape(a + b) for a, b in _FORBIDDEN_TERMS))
ALL_TEXT = text_files(".md", ".py", ".json", ".yml", ".yaml", ".toml", ".txt", ".cfg")
ALL_TEXT += [ROOT / ".gitignore", ROOT / ".gitleaksignore"]


@pytest.mark.parametrize("path", ALL_TEXT, ids=lambda p: str(p.relative_to(ROOT)))
def test_no_internal_markers(path: Path) -> None:
    assert not FORBIDDEN.search(path.read_text(encoding="utf-8")), path


@pytest.mark.parametrize("path", ALL_TEXT, ids=lambda p: str(p.relative_to(ROOT)))
def test_only_official_contact_address(path: Path) -> None:
    emails = set(re.findall(r"[\w.+-]+@[\w-]+\.[A-Za-z]{2,}", path.read_text(encoding="utf-8")))
    assert emails <= {"mail@gradweight.ch"}, (path, emails)


@pytest.mark.parametrize("path", MARKDOWN, ids=lambda p: str(p.relative_to(ROOT)))
def test_swiss_spelling_and_tone(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    assert "ß" not in text
    assert not re.search(r"[\U0001F300-\U0001FAFF\u2600-\u27bf]", text), "keine Emojis"
    for word in ("Multi-Agent", "production-ready", "Production-ready", "revolutionär", "genial"):
        assert word not in text, word
    assert "!!" not in text
