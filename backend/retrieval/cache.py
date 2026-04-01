"""
Redis semantic query cache.

Caches vector search results by query hash to avoid redundant Pinecone + Voyage
calls for identical or near-identical queries within a session window.
TTL: 1 hour (policies don't change that fast).
"""

import json
import hashlib
import re
import structlog
from redis import asyncio as aioredis
from typing import Optional
from config import settings

_redis: Optional[aioredis.Redis] = None
TTL = 3600  # 1 hour
_TOKEN_RE = re.compile(r"[a-z0-9]+")
log = structlog.get_logger()


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


def _query_tokens(query: str) -> set[str]:
    return {
        token for token in _TOKEN_RE.findall((query or "").lower())
        if len(token) >= 4
    }


def _drug_index_key(drug_keyword: str) -> str:
    return f"pa:cache:index:drug:{drug_keyword}"


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
        await r.setex(key, TTL, json.dumps(results))

        for token in _query_tokens(query):
            index_key = _drug_index_key(token)
            await r.sadd(index_key, key)
            await r.expire(index_key, TTL)
    except Exception:
        pass


async def invalidate_cache_for_drug(drug: str) -> None:
    drug_keyword = (drug or "").split("(")[0].strip().lower().split()[0] if drug else ""
    if not drug_keyword:
        return

    try:
        r = _get_redis()
        index_key = _drug_index_key(drug_keyword)
        keys = list(await r.smembers(index_key))

        # Fallback for older hashed cache entries created before the reverse index existed.
        if not keys:
            keys = await r.keys("pa:cache:*")

        if keys:
            await r.delete(*keys)
            await r.delete(index_key)
            log.info("cache.invalidated", drug=drug_keyword, keys_deleted=len(keys))
    except Exception as e:
        log.warning("cache.invalidation_failed", drug=drug_keyword, error=str(e))
