"""Gemeinsame Basis für Bausteine mit eigener SQLite-Verbindung."""

from __future__ import annotations

from types import TracebackType
from typing import TypeVar

_T = TypeVar("_T", bound="Closable")


class Closable:
    """Kontextmanager-Unterstützung: ``with AuditTrail(...) as trail: ...``."""

    def close(self) -> None:  # pragma: no cover - wird überschrieben
        raise NotImplementedError

    def __enter__(self: _T) -> _T:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
