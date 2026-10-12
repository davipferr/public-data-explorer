"""HTTP helpers with an on-disk cache, retries and polite rate limiting.

Framework already caches loader *outputs*, but the raw downloads (hundreds of MB
of zipped CSVs) are cached here too, so editing a cleaning step doesn't trigger a
re-download of everything.
"""

from __future__ import annotations

import atexit
import gzip
import hashlib
import os
import sys
import time
from datetime import timedelta
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = Path(os.environ.get("PDE_CACHE_DIR", ROOT / "data_cache"))
USER_AGENT = "public-data-explorer/0.1 (build-time data loader; python-httpx)"

# Status codes worth retrying: rate limiting and transient server errors.
RETRY_STATUS = {429, 500, 502, 503, 504}


class NotFound(Exception):
    """The resource does not exist (yet), e.g. today's bulk file isn't published."""


def log(*args: object) -> None:
    """Loaders write data to stdout, so all diagnostics must go to stderr."""
    print(*args, file=sys.stderr, flush=True)


def _cache_path(url: str, params: dict | None, suffix: str) -> Path:
    key = url + "?" + "&".join(f"{k}={v}" for k, v in sorted((params or {}).items()))
    digest = hashlib.sha256(key.encode()).hexdigest()[:20]
    return CACHE_DIR / f"{digest}{suffix}"


def cached_path(url: str, params: dict | None = None, suffix: str = ".bin") -> Path | None:
    """Where ``fetch`` stored this request, or None if it was never downloaded.

    ``suffix`` must match the one passed to ``fetch``. Ignores ``max_age``.
    """
    path = _cache_path(url, params, suffix)
    return path if path.exists() else None


_client: httpx.Client | None = None


def _get_client() -> httpx.Client:
    """One client per process, so consecutive requests to the same host reuse the
    TLS connection (thousands of API calls for Bolsa Família, Câmara pagination)."""
    global _client
    if _client is None:
        _client = httpx.Client(follow_redirects=True)
        atexit.register(_client.close)
    return _client


def _maybe_gunzip(data: bytes) -> bytes:
    # IBGE's servicodados sometimes sends gzip bodies without a Content-Encoding
    # header, so httpx can't transparently decode them.
    return gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data


def fetch(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    max_age: timedelta | None = timedelta(days=7),
    suffix: str = ".bin",
    retries: int = 5,
    timeout: float = 300.0,
) -> bytes:
    """GET ``url`` and return the body, using the disk cache when fresh.

    ``headers`` are deliberately *not* part of the cache key, so secrets such as
    API keys never end up in file names. ``max_age=None`` caches forever.
    """
    path = _cache_path(url, params, suffix)
    if path.exists() and (max_age is None or time.time() - path.stat().st_mtime < max_age.total_seconds()):
        return path.read_bytes()

    hdrs = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"} | (headers or {})
    delay = 2.0
    for attempt in range(1, retries + 1):
        try:
            resp = _get_client().get(url, params=params, headers=hdrs, timeout=timeout)
            if resp.status_code in (403, 404):
                raise NotFound(f"{resp.status_code} for {url}")
            if resp.status_code in RETRY_STATUS:
                raise httpx.HTTPStatusError(f"{resp.status_code}", request=resp.request, response=resp)
            resp.raise_for_status()
            data = _maybe_gunzip(resp.content)
            break
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            if attempt == retries:
                raise
            retry_after = getattr(getattr(exc, "response", None), "headers", {}).get("Retry-After")
            wait = float(retry_after) if retry_after and retry_after.isdigit() else delay
            log(f"  retry {attempt}/{retries} for {url} in {wait:.0f}s ({exc})")
            time.sleep(wait)
            delay *= 2

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_bytes(data)
    tmp.replace(path)
    return data


class RateLimiter:
    """Simple fixed-interval limiter: at most ``per_minute`` calls per minute."""

    def __init__(self, per_minute: int):
        self.interval = 60.0 / per_minute
        self._last = 0.0

    def wait(self) -> None:
        now = time.monotonic()
        sleep_for = self._last + self.interval - now
        if sleep_for > 0:
            time.sleep(sleep_for)
        self._last = time.monotonic()
