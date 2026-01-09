"""
Redis semantic query cache.

Caches vector search results by query hash to avoid redundant Pinecone + Voyage
calls for identical or near-identical queries within a session window.
TTL: 1 hour (policies don't change that fast).
"""

import json
import hashlib
import structlog
from redis import asyncio as aioredis
from typing import Optional
from config import settings

_redis: Optional[aioredis.Redis] = None


def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        url = settings.redis_url
        if url.startswith("rediss://"):
            _redis = aioredis.from_url(
                url,
                encoding="utf-8",
                decode_responses=True,
                ssl_cert_reqs=None,
            )
        else:
            _redis = aioredis.from_url(url, decode_responses=True)
    return _redis


def _cache_key(query: str, top_k: int, effective_filter: Optional[dict]) -> str:
    filter_str = json.dumps(effective_filter, sort_keys=True) if effective_filter else ""
    raw = f"{query}|{top_k}|{filter_str}"
    return "pa:cache:" + hashlib.sha256(raw.encode()).hexdigest()[:24]


async def get_cached(query: str, top_k: int, effective_filter: Optional[dict]) -> Optional[list[dict]]:
    try:
        r = _get_redis()
        key = _cache_key(query, top_k, effective_filter)
        val = await r.get(key)
        if val:
            return json.loads(val)
    except Exception:
        pass
    return None


async def set_cached(
    query: str, top_k: int, effective_filter: Optional[dict], results: list[dict]
) -> None:
    try:
        r = _get_redis()
        key = _cache_key(query, top_k, effective_filter)
        await r.setex(key, 3600, json.dumps(results))
    except Exception:
        pass
