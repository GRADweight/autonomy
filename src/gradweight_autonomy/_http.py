"""Minimale HTTP-Schicht auf ``urllib`` mit austauschbarem Transport.

Adapter (bexio, OpenAI-kompatible API) erhalten einen ``Transport`` als
Abhängigkeit. In Tests wird ein Fake oder ein lokaler ``http.server``
eingesetzt; es gibt keinen Netzwerkzugriff in den Tests.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

MAX_RESPONSE_BYTES = 5 * 1024 * 1024


class TransportError(RuntimeError):
    """Verbindungsfehler ohne HTTP-Antwort (Timeout, DNS, Verbindungsabbruch)."""


@dataclass(frozen=True)
class HttpRequest:
    """Eine HTTP-Anfrage."""

    method: str
    url: str
    headers: Mapping[str, str] = field(default_factory=dict)
    body: bytes | None = None
    timeout: float = 30.0

    def __post_init__(self) -> None:
        scheme = urllib.parse.urlsplit(self.url).scheme
        if scheme not in ("http", "https"):
            raise ValueError(f"nur http(s)-URLs erlaubt, nicht {scheme!r}")
        if self.timeout <= 0:
            raise ValueError("timeout muss positiv sein")


@dataclass(frozen=True)
class HttpResponse:
    """Eine HTTP-Antwort."""

    status: int
    body: bytes = b""
    headers: Mapping[str, str] = field(default_factory=dict)

    def json(self) -> Any:
        """Body als JSON (wirft ``ValueError`` bei ungültigem JSON)."""
        return json.loads(self.body.decode("utf-8"))


Transport = Callable[[HttpRequest], HttpResponse]


def _read_limited(stream: Any) -> bytes:
    data: bytes = stream.read(MAX_RESPONSE_BYTES + 1)
    if len(data) > MAX_RESPONSE_BYTES:
        raise TransportError(f"Antwort grösser als {MAX_RESPONSE_BYTES} Bytes")
    return data


def urllib_transport(request: HttpRequest) -> HttpResponse:
    """Standard-Transport über ``urllib.request`` (Schema bereits auf http/https geprüft)."""
    req = urllib.request.Request(  # noqa: S310 - Schema in HttpRequest geprüft
        request.url, data=request.body, headers=dict(request.headers), method=request.method
    )
    try:
        with urllib.request.urlopen(req, timeout=request.timeout) as resp:  # noqa: S310
            return HttpResponse(resp.status, _read_limited(resp), dict(resp.headers.items()))
    except urllib.error.HTTPError as exc:
        body = _read_limited(exc) if exc.fp is not None else b""
        headers = dict(exc.headers.items()) if exc.headers is not None else {}
        return HttpResponse(exc.code, body, headers)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise TransportError(f"{type(exc).__name__}: {exc}") from exc
