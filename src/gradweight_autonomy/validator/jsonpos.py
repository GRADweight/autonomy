"""Zeilen und Spalten zu JSON Pointern finden (für Text- und SARIF-Ausgabe).

``json`` aus der Standardbibliothek liefert keine Positionen. Dieser kleine
Scanner geht den (bereits als gültig geparsten) Text einmal durch und merkt
sich für jeden JSON Pointer, wo der Wert beginnt.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from gradweight_autonomy.validator.jsonschema_lite import escape_pointer_token

_WS = re.compile(r"[ \t\n\r]*")
_NUMBER = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")
_STRING = re.compile(r'"(?:[^"\\\x00-\x1f]|\\.)*"', re.DOTALL)


@dataclass(frozen=True)
class Position:
    """1-basierte Zeile und Spalte (Spalte in Unicode-Codepunkten)."""

    line: int
    column: int


class _Scanner:
    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0
        self.offsets: dict[str, int] = {}
        # Zeilenanfänge für die Umrechnung Offset -> Zeile/Spalte
        self.line_starts = [0] + [m.end() for m in re.finditer("\n", text)]

    def skip_ws(self) -> None:
        m = _WS.match(self.text, self.pos)
        if m:
            self.pos = m.end()

    def expect(self, char: str) -> None:
        if self.text[self.pos : self.pos + 1] != char:
            raise ValueError(f"erwartet {char!r} an Position {self.pos}")
        self.pos += 1

    def string(self) -> str:
        m = _STRING.match(self.text, self.pos)
        if not m:
            raise ValueError(f"String erwartet an Position {self.pos}")
        self.pos = m.end()
        value: str = json.loads(m.group(0))
        return value

    def value(self, pointer: str) -> None:
        self.skip_ws()
        self.offsets[pointer] = self.pos
        ch = self.text[self.pos : self.pos + 1]
        if ch == "{":
            self.pos += 1
            self.skip_ws()
            if self.text[self.pos : self.pos + 1] == "}":
                self.pos += 1
                return
            while True:
                self.skip_ws()
                key = self.string()
                self.skip_ws()
                self.expect(":")
                self.value(f"{pointer}/{escape_pointer_token(key)}")
                self.skip_ws()
                if self.text[self.pos : self.pos + 1] == ",":
                    self.pos += 1
                    continue
                self.expect("}")
                return
        if ch == "[":
            self.pos += 1
            self.skip_ws()
            if self.text[self.pos : self.pos + 1] == "]":
                self.pos += 1
                return
            index = 0
            while True:
                self.value(f"{pointer}/{index}")
                index += 1
                self.skip_ws()
                if self.text[self.pos : self.pos + 1] == ",":
                    self.pos += 1
                    continue
                self.expect("]")
                return
        if ch == '"':
            self.string()
            return
        for literal in ("true", "false", "null"):
            if self.text.startswith(literal, self.pos):
                self.pos += len(literal)
                return
        m = _NUMBER.match(self.text, self.pos)
        if not m:
            raise ValueError(f"unerwartetes Zeichen an Position {self.pos}")
        self.pos = m.end()

    def position(self, offset: int) -> Position:
        lo, hi = 0, len(self.line_starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self.line_starts[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return Position(line=lo + 1, column=offset - self.line_starts[lo] + 1)


class PointerLocator:
    """Liefert die Position eines JSON Pointers in einem JSON-Text."""

    def __init__(self, text: str) -> None:
        self._scanner = _Scanner(text.removeprefix("﻿"))
        self._ok = True
        try:
            self._scanner.value("")
        except (ValueError, IndexError):
            self._ok = False

    def offset(self, pointer: str) -> int | None:
        """Zeichen-Offset des Werts (``None``, wenn unbekannt)."""
        return self._scanner.offsets.get(pointer) if self._ok else None

    def locate(self, pointer: str) -> Position:
        """Position des Werts; fehlt er, die des nächsten vorhandenen Elternteils."""
        if not self._ok:
            return Position(1, 1)
        current = pointer
        while True:
            offset = self._scanner.offsets.get(current)
            if offset is not None:
                return self._scanner.position(offset)
            if not current:
                return Position(1, 1)
            current = current.rsplit("/", 1)[0]
