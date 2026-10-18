"""On-disk HTTP cache and rate limiting for polite EDGAR usage."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import requests

from stock_analyzer.config import CACHE_DIR, EDGAR_REQUESTS_PER_SECOND, USER_AGENT


class RateLimiter:
    """Simple token-bucket rate limiter."""

    def __init__(self, requests_per_second: float):
        self.min_interval = 1.0 / requests_per_second if requests_per_second > 0 else 0
        self._last_call = 0.0

    def wait(self) -> None:
        if self.min_interval <= 0:
            return
        elapsed = time.time() - self._last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_call = time.time()


class Cache:
    """On-disk JSON cache keyed by URL hash."""

    def __init__(self, cache_dir: Path = CACHE_DIR):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _key(self, url: str) -> str:
        return hashlib.sha256(url.encode()).hexdigest()[:16] + ".json"

    def get(self, url: str) -> dict | None:
        path = self.cache_dir / self._key(url)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def set(self, url: str, data: dict) -> None:
        path = self.cache_dir / self._key(url)
        path.write_text(json.dumps(data), encoding="utf-8")


class EdgarClient:
    """Polite SEC EDGAR client with caching and rate limiting."""

    def __init__(self, cache: Cache | None = None):
        self.cache = cache or Cache()
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.limiter = RateLimiter(EDGAR_REQUESTS_PER_SECOND)

    def get_json(self, url: str) -> dict:
        self.limiter.wait()
        cached = self.cache.get(url)
        if cached is not None:
            return cached
        resp = self.session.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        self.cache.set(url, data)
        return data

    def get_text(self, url: str) -> str:
        self.limiter.wait()
        cached = self.cache.get(url)
        if cached is not None and isinstance(cached, dict) and "_text" in cached:
            return cached["_text"]
        resp = self.session.get(url, timeout=30)
        resp.raise_for_status()
        text = resp.text
        self.cache.set(url, {"_text": text})
        return text