"""OpenAI-kompatibler Client und Zweitmodell-Prüfung (ohne Netzwerk)."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, ClassVar

import pytest

from gradweight_autonomy._http import (
    MAX_RESPONSE_BYTES,
    HttpRequest,
    HttpResponse,
    TransportError,
    urllib_transport,
)
from gradweight_autonomy.llm import (
    ChatClient,
    ChatConfig,
    LlmError,
    SecondModelReview,
)
from gradweight_autonomy.source_check import Source


def completion(content: Any) -> HttpResponse:
    text = content if isinstance(content, str) else json.dumps(content)
    body = {"choices": [{"message": {"role": "assistant", "content": text}}]}
    return HttpResponse(200, json.dumps(body).encode("utf-8"))


class FakeTransport:
    def __init__(self, *responses: HttpResponse | Exception) -> None:
        self.responses = list(responses)
        self.requests: list[HttpRequest] = []

    def __call__(self, request: HttpRequest) -> HttpResponse:
        self.requests.append(request)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


CONFIG = ChatConfig(
    base_url="http://127.0.0.1:9/v1/", model="qwen", api_key="test-key", max_retries=2
)


def client(transport: Callable[[HttpRequest], HttpResponse], sleeps: list[float]) -> ChatClient:
    return ChatClient(CONFIG, transport=transport, sleep=sleeps.append)


# ------------------------------------------------------------------ ChatClient
def test_request_format_and_success() -> None:
    fake = FakeTransport(completion({"verdict": "supported", "unsupported_claims": []}))
    sleeps: list[float] = []
    result = client(fake, sleeps).complete_json([{"role": "user", "content": "x"}])
    assert result == {"verdict": "supported", "unsupported_claims": []}
    req = fake.requests[0]
    assert req.url == "http://127.0.0.1:9/v1/chat/completions"
    assert req.headers["Authorization"] == "Bearer test-key"
    body = json.loads(req.body or b"")
    assert body["temperature"] == 0
    assert body["response_format"] == {"type": "json_object"}
    assert sleeps == []


def test_retries_with_exponential_backoff_then_success() -> None:
    fake = FakeTransport(
        TransportError("timeout"),
        HttpResponse(503),
        completion({"a": 1}),
    )
    sleeps: list[float] = []
    assert client(fake, sleeps).complete_json([]) == {"a": 1}
    assert sleeps == [0.5, 1.0]


def test_gives_up_after_retries() -> None:
    fake = FakeTransport(HttpResponse(429), HttpResponse(429), HttpResponse(429))
    with pytest.raises(LlmError, match=r"3 Versuchen.*HTTP 429"):
        client(fake, []).complete_json([])


def test_client_error_is_not_retried() -> None:
    fake = FakeTransport(HttpResponse(401))
    with pytest.raises(LlmError, match="HTTP 401"):
        client(fake, []).complete_json([])
    assert len(fake.requests) == 1


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (HttpResponse(200, b"kein json"), "Antwortformat"),
        (HttpResponse(200, b'{"choices": []}'), "Antwortformat"),
        (completion("kein json"), "kein gültiges JSON"),
        (completion("[1, 2]"), "kein JSON-Objekt"),
        (HttpResponse(200, b'{"choices": [{"message": {"content": 5}}]}'), "kein Text"),
    ],
)
def test_invalid_responses(response: HttpResponse, message: str) -> None:
    with pytest.raises(LlmError, match=message):
        client(FakeTransport(response), []).complete_json([])


def test_config_validation_and_secret_not_in_repr() -> None:
    with pytest.raises(ValueError, match="negativ"):
        ChatConfig(base_url="http://x", model="m", max_retries=-1)
    assert "test-key" not in repr(CONFIG)


# ------------------------------------------------------------------ Review
SOURCES = [Source("Rückgabe innert 30 Tagen.", "agb")]


@pytest.mark.parametrize(
    ("content", "passed", "verdict"),
    [
        ({"verdict": "supported", "unsupported_claims": []}, True, "supported"),
        ({"verdict": "unsupported", "unsupported_claims": ["Gratisversand"]}, False, "unsupported"),
        ({"verdict": "supported", "unsupported_claims": ["x"]}, False, "error"),
        ({"verdict": "unsupported", "unsupported_claims": []}, False, "error"),
        ({"verdict": "vielleicht", "unsupported_claims": []}, False, "error"),
        ({"verdict": "supported"}, False, "error"),
        ({"verdict": "supported", "unsupported_claims": [], "x": 1}, False, "error"),
        ({"verdict": "unsupported", "unsupported_claims": [""]}, False, "error"),
        ({"verdict": "unsupported", "unsupported_claims": "x"}, False, "error"),
    ],
)
def test_review_is_strict_and_fail_closed(
    content: dict[str, Any], passed: bool, verdict: str
) -> None:
    review = SecondModelReview(client(FakeTransport(completion(content)), []))
    result = review.review("Rückgabe innert 30 Tagen.", SOURCES)
    assert (result.passed, result.verdict) == (passed, verdict)


def test_review_transport_failure_is_fail_closed() -> None:
    fake = FakeTransport(TransportError("a"), TransportError("b"), TransportError("c"))
    result = SecondModelReview(client(fake, [])).review("x", SOURCES)
    assert not result.passed
    assert result.verdict == "error"
    assert "nicht erreichbar" in result.error


def test_review_prompt_marks_material_as_data() -> None:
    fake = FakeTransport(completion({"verdict": "supported", "unsupported_claims": []}))
    SecondModelReview(client(fake, [])).review("Antwort", SOURCES)
    messages = json.loads(fake.requests[0].body or b"")["messages"]
    assert "keine Anweisung" in messages[0]["content"]
    assert "<quellen>\n[1] agb\nRückgabe innert 30 Tagen.\n</quellen>" in messages[1]["content"]


def test_review_rejects_oversized_input() -> None:
    fake = FakeTransport()
    result = SecondModelReview(client(fake, []), max_chars=10).review("x" * 50, SOURCES)
    assert (result.passed, result.error) == (False, "Eingabe zu lang für die Prüfung")
    assert fake.requests == []


# ------------------------------------------------------------------ urllib-Transport (lokal)
class _Handler(BaseHTTPRequestHandler):
    routes: ClassVar[dict[str, tuple[int, bytes]]] = {}

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        payload = self.rfile.read(length)
        status, body = self.routes.get(self.path, (404, b"{}"))
        if self.path == "/echo":
            body = payload
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: ARG002 - Signatur von http.server
        return


@pytest.fixture
def server() -> Iterator[str]:
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_urllib_transport_against_local_server(server: str) -> None:
    content = {"verdict": "supported", "unsupported_claims": []}
    body = json.dumps({"choices": [{"message": {"content": json.dumps(content)}}]}).encode()
    _Handler.routes = {"/v1/chat/completions": (200, body), "/fehler": (500, b"kaputt")}
    cfg = ChatConfig(base_url=f"{server}/v1", model="m", timeout_s=5)
    review = SecondModelReview(ChatClient(cfg))
    assert review.review("Rückgabe innert 30 Tagen.", SOURCES).passed
    echo = urllib_transport(HttpRequest("POST", f"{server}/echo", {}, b'{"x": 1}', 5))
    assert echo.json() == {"x": 1}
    error = urllib_transport(HttpRequest("POST", f"{server}/fehler", {}, b"", 5))
    assert (error.status, error.body) == (500, b"kaputt")


def test_urllib_transport_connection_refused() -> None:
    with pytest.raises(TransportError):
        urllib_transport(HttpRequest("POST", "http://127.0.0.1:9/x", {}, b"", 2))


def test_http_request_validation() -> None:
    with pytest.raises(ValueError, match="http"):
        HttpRequest("GET", "file:///etc/passwd")
    with pytest.raises(ValueError, match="timeout"):
        HttpRequest("GET", "https://example.org", timeout=0)


def test_response_size_limit(server: str) -> None:
    _Handler.routes = {"/gross": (200, b"x" * (MAX_RESPONSE_BYTES + 10))}
    with pytest.raises(TransportError, match="grösser"):
        urllib_transport(HttpRequest("POST", f"{server}/gross", {}, b"", 5))
