"""Read-only client for the TripView API (api.tripview.com.au).

The endpoint list, the `X-Auth` signature and the `types`/`routes` semantics
come from the reverse engineering in 逆向分析报告.md; the signing secret is the
constant baked into libtv.so. Requests are small, read-only and cached.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
import os
from typing import Any

import httpx

API_BASE = os.environ.get("TRIPLENS_API_BASE", "https://api.tripview.com.au")
STATIC_BASE = os.environ.get("TRIPLENS_STATIC_BASE", "https://static.tripview.com.au")
USER_AGENT = "TripViewLite-Android/4.5.6.689 (Android 14; Pixel)"
SIGNING_SECRET = "8vL]Zs+Ju%oQ@3zm;kRU"

# types: d=delays t=transpositions v=vehicles a=alerts
DEFAULT_TYPES = "dtva"


def x_auth(ts: int | None = None) -> str:
    ts = int(time.time()) if ts is None else ts
    digest = hashlib.md5((str(ts) + SIGNING_SECRET).encode()).hexdigest()
    return f"{ts}.{digest}"


class _Cache:
    def __init__(self) -> None:
        self.data: dict[str, tuple[float, Any]] = {}
        self.locks: dict[str, asyncio.Lock] = {}

    def lock(self, key: str) -> asyncio.Lock:
        return self.locks.setdefault(key, asyncio.Lock())

    def get(self, key: str, ttl: float) -> Any | None:
        hit = self.data.get(key)
        if hit and time.time() - hit[0] < ttl:
            return hit[1]
        return None

    def put(self, key: str, value: Any) -> Any:
        self.data[key] = (time.time(), value)
        return value


class Upstream:
    """Async, cached, read-only access to the private API."""

    def __init__(self, region: str = "syd") -> None:
        self.region = region
        self._cache = _Cache()
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=15.0),
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, url: str, key: str, ttl: float) -> Any:
        cached = self._cache.get(key, ttl)
        if cached is not None:
            return cached
        async with self._cache.lock(key):
            cached = self._cache.get(key, ttl)
            if cached is not None:
                return cached
            resp = await self._client.get(url, headers={"X-Auth": x_auth()})
            resp.raise_for_status()
            return self._cache.put(key, resp.content)

    async def config(self, ttl: float = 600) -> dict:
        raw = await self._get(f"{API_BASE}/config?v=3", "config", ttl)
        import json

        return json.loads(raw)

    async def region_config(self, region: str | None = None,
                            ttl: float = 600) -> dict:
        region = region or self.region
        cfg = await self.config(ttl)
        for reg in cfg.get("regions", []):
            if reg.get("name") == region:
                return reg
        return {}

    async def timetables(self, region: str | None = None) -> dict[str, dict]:
        """{name: {url, desc, size, colour, time}} for one region."""
        reg = await self.region_config(region)
        return {t["name"]: t for t in reg.get("timetables", [])}

    async def realtime(self, routes: str | None = None, types: str = DEFAULT_TYPES,
                       region: str | None = None, ttl: float = 12) -> dict:
        region = region or self.region
        q = f"types={types}&region={region}"
        if routes:
            q += f"&routes={routes}"
        key = f"realtime:{q}"
        raw = await self._get(f"{API_BASE}/realtime?{q}", key, ttl)
        import json

        return json.loads(raw)

    async def svinfo(self, region: str | None = None, ttl: float = 300) -> str:
        region = region or self.region
        raw = await self._get(f"{API_BASE}/svinfo?region={region}",
                              f"svinfo:{region}", ttl)
        return raw.decode("utf-8", "replace")

    async def download(self, url: str) -> bytes:
        """Absolute URL fetch (timetable files live on the static host)."""
        resp = await self._client.get(url)
        resp.raise_for_status()
        return resp.content
