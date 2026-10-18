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


class CacheEntry:
    """A cached value with an optional expiry timestamp."""

    def __init__(self, data: dict, expiry: float | None = None):
        self.data = data
        self.expiry = expiry  # None means never expires

    def is_expired(self) -> bool:
        if self.expiry is None:
            return False
        return time.time() > self.expiry


class Cache:
    """On-disk JSON cache keyed by URL hash with per-entry expiry."""

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
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        entry = CacheEntry(payload.get("data"), payload.get("expiry"))
        if entry.is_expired():
            try:
                path.unlink()
            except OSError:
                pass
            return None
        return entry.data

    def set(self, url: str, data: dict, ttl: int | None = None) -> None:
        path = self.cache_dir / self._key(url)
        expiry = None
        if ttl is not None:
            expiry = time.time() + ttl
        payload = {"data": data, "expiry": expiry}
        path.write_text(json.dumps(payload), encoding="utf-8")


class EdgarClient:
    """Polite SEC EDGAR client with caching and rate limiting."""

    def __init__(self, cache: Cache | None = None):
        self.cache = cache or Cache()
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.limiter = RateLimiter(EDGAR_REQUESTS_PER_SECOND)

    def get_json(self, url: str, ttl: int | None = None) -> dict:
        self.limiter.wait()
        cached = self.cache.get(url)
        if cached is not None:
            return cached
        resp = self.session.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        self.cache.set(url, data, ttl=ttl)
        return data

    def get_text(self, url: str, ttl: int | None = None) -> str:
        self.limiter.wait()
        cached = self.cache.get(url)
        if cached is not None and isinstance(cached, dict) and "_text" in cached:
            return cached["_text"]
        resp = self.session.get(url, timeout=30)
        resp.raise_for_status()
        text = resp.text
        self.cache.set(url, {"_text": text}, ttl=ttl)
        return text