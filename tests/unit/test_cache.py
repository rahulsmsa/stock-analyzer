"""Tests for the cache layer: expiry, User-Agent, rate limiting (G8, T011a)."""

from __future__ import annotations

import time

from stock_analyzer.data.cache import Cache, EdgarClient, RateLimiter


def test_rate_limiter_spaces_calls():
    limiter = RateLimiter(requests_per_second=1000.0)  # effectively no delay
    t0 = time.perf_counter()
    limiter.wait()
    limiter.wait()
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.1


def test_cache_set_and_get(tmp_path):
    c = Cache(cache_dir=tmp_path)
    c.set("http://example.com/a", {"foo": 1})
    assert c.get("http://example.com/a") == {"foo": 1}
    assert c.get("http://example.com/missing") is None


def test_cache_expiry(tmp_path):
    c = Cache(cache_dir=tmp_path)
    c.set("http://example.com/market", {"price": 100}, ttl=1)
    assert c.get("http://example.com/market") == {"price": 100}
    time.sleep(1.1)
    assert c.get("http://example.com/market") is None


def test_cache_no_expiry_by_default(tmp_path):
    c = Cache(cache_dir=tmp_path)
    c.set("http://example.com/filing", {"accession": "0001"})
    assert c.get("http://example.com/filing") == {"accession": "0001"}


def test_edgar_client_user_agent(tmp_path):
    c = Cache(cache_dir=tmp_path)
    client = EdgarClient(cache=c)
    ua = client.session.headers.get("User-Agent", "")
    assert "stock-analyzer" in ua
    assert "contact" in ua.lower()


def test_edgar_client_rate_limiter_present(tmp_path):
    c = Cache(cache_dir=tmp_path)
    client = EdgarClient(cache=c)
    assert client.limiter is not None
    assert client.limiter.min_interval > 0


def test_cache_roundtrip_persists_to_disk(tmp_path):
    cache_file = tmp_path / "cache"
    c1 = Cache(cache_dir=cache_file)
    c1.set("http://example.com/x", {"v": 42})
    c2 = Cache(cache_dir=cache_file)
    assert c2.get("http://example.com/x") == {"v": 42}
