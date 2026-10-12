import httpx
import pytest

from pipeline import http


@pytest.fixture
def mock_client(tmp_path, monkeypatch):
    """Route the shared client through a mock transport; record every request."""
    seen: list[httpx.Request] = []
    responses: dict[str, list[httpx.Response]] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        queue = responses.get(request.url.path)
        return queue.pop(0) if queue else httpx.Response(200, content=b"ok")

    monkeypatch.setattr(http, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(http, "_client", httpx.Client(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(http.time, "sleep", lambda s: None)
    return seen, responses


def test_requests_share_one_client(mock_client):
    seen, _ = mock_client
    client = http._get_client()
    assert http.fetch("https://example.test/a") == b"ok"
    assert http.fetch("https://example.test/b") == b"ok"
    assert http._get_client() is client
    assert [r.url.path for r in seen] == ["/a", "/b"]


def test_cache_hit_skips_network_and_cached_path_finds_it(mock_client):
    seen, _ = mock_client
    assert http.cached_path("https://example.test/c", {"x": 1}) is None
    http.fetch("https://example.test/c", params={"x": 1})
    http.fetch("https://example.test/c", params={"x": 1})
    assert len(seen) == 1
    assert http.cached_path("https://example.test/c", {"x": 1}).read_bytes() == b"ok"


def test_retries_then_succeeds_and_not_found(mock_client):
    seen, responses = mock_client
    responses["/flaky"] = [httpx.Response(503), httpx.Response(200, content=b"done")]
    assert http.fetch("https://example.test/flaky") == b"done"
    responses["/gone"] = [httpx.Response(404)]
    with pytest.raises(http.NotFound):
        http.fetch("https://example.test/gone")


def test_headers_are_sent_but_not_part_of_cache_key(mock_client):
    seen, _ = mock_client
    http.fetch("https://example.test/k", headers={"chave-api-dados": "secret"})
    assert seen[0].headers["chave-api-dados"] == "secret"
    assert "secret" not in str(http.cached_path("https://example.test/k"))
