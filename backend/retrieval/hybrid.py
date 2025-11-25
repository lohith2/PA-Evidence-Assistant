"""
Hybrid retrieval: BM25 exact match + Pinecone semantic search → RRF fusion.

WHY BM25 is critical for policy codes:
Policy codes like "4.2.1b" are opaque alphanumeric strings. A semantic embedding
model will treat "4.2.1b" as near-meaningless tokens and may return sections
about "4.2.1a" or completely different policy numbers. BM25 exact match ensures
the specific policy section number is always retrieved when present in the corpus.

Semantic search handles the opposite case: finding relevant policy language
when we only have a natural language description of the denial reason.

RRF (Reciprocal Rank Fusion) merges the two ranked lists without needing
normalized scores — it uses ranks, not scores, so BM25 and cosine similarity
are directly comparable.
"""

import structlog
from rank_bm25 import BM25Okapi
from pinecone import Pinecone
import voyageai
from typing import Optional

from config import settings
from retrieval.cache import get_cached, set_cached

log = structlog.get_logger()

# ── Clients (lazy-initialized) ────────────────────────────────────────────────
_pc: Optional[Pinecone] = None
_voyage: Optional[voyageai.AsyncClient] = None
_bm25_corpus: Optional[list[dict]] = None
_bm25_index: Optional[BM25Okapi] = None


def _get_pinecone_index():
    global _pc
    if _pc is None:
        _pc = Pinecone(api_key=settings.pinecone_api_key)
    return _pc.Index(settings.pinecone_index)


def _get_voyage() -> voyageai.AsyncClient:
    global _voyage
    if _voyage is None:
        _voyage = voyageai.AsyncClient(api_key=settings.voyage_api_key)
    return _voyage


def _get_bm25(corpus: list[dict]) -> BM25Okapi:
    """Build BM25 index from a flat list of text chunks."""
    tokenized = [doc["text"].lower().split() for doc in corpus]
    return BM25Okapi(tokenized)


async def _embed(texts: list[str]) -> list[list[float]]:
    """Embed texts with exponential backoff on rate limit errors."""
    import asyncio as _asyncio
    retries = 3
    for attempt in range(retries):
        try:
            voyage = _get_voyage()
            result = await voyage.embed(texts, model="voyage-3", input_type="query")
            return result.embeddings
        except Exception as e:
            if "rate" in str(e).lower() and attempt < retries - 1:
                wait = 2 ** attempt  # 1s, 2s
                log.warning("voyage.rate_limit", attempt=attempt, wait=wait)
                await _asyncio.sleep(wait)
            else:
                raise
    return []


def _rrf(lists: list[list[dict]], k: int = 60) -> list[dict]:
    """
    Reciprocal Rank Fusion.
    k=60 is the standard constant from the original RRF paper (Cormack 2009).
    Score = sum(1 / (k + rank)) across all lists for each document.
    """
    scores: dict[str, float] = {}
    docs: dict[str, dict] = {}

    for ranked_list in lists:
        for rank, doc in enumerate(ranked_list, start=1):
            uid = doc.get("id") or doc.get("title", "") + doc.get("text", "")[:40]
            scores[uid] = scores.get(uid, 0.0) + 1.0 / (k + rank)
            docs[uid] = doc

    ranked = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    return [{"score": scores[uid], **docs[uid]} for uid in ranked]


def _deduplicate(chunks: list[dict]) -> list[dict]:
    """
    Remove duplicate chunks after RRF fusion.
    Deduplicates by Pinecone vector ID first, then by source+title to catch
    the same document retrieved under different IDs (e.g. re-ingested chunks).
    """
    seen_ids: set[str] = set()
    seen_title_keys: set[str] = set()
    unique: list[dict] = []

    for chunk in chunks:
        chunk_id = chunk.get("id", "")
        title_key = f"{chunk.get('source', '')}:{chunk.get('title', '')[:60]}"

        if chunk_id and chunk_id in seen_ids:
            continue
        if title_key in seen_title_keys:
            continue

        if chunk_id:
            seen_ids.add(chunk_id)
        seen_title_keys.add(title_key)
        unique.append(chunk)

    return unique


class HybridRetriever:
    async def search(
        self,
        query: str,
        top_k: int = 5,
        filter_source: Optional[str] = None,
        metadata_filter: Optional[dict] = None,
    ) -> list[dict]:
        # metadata_filter takes precedence over filter_source shorthand
        effective_filter = metadata_filter or (
            {"source": {"$eq": filter_source}} if filter_source else None
        )

        # Check Redis cache first
        cached = await get_cached(query, top_k, effective_filter)
        if cached:
            log.debug("cache.hit", query=query[:60])
            return cached

        try:
            results = await self._search_uncached(query, top_k, effective_filter)
        except Exception as e:
            # Graceful degradation: embed failures (rate limit, network) return empty
            # rather than crashing the agent. Contradiction finder handles sparse evidence.
            log.warning("retrieval.failed", query=query[:60], error=str(e))
            return []
        await set_cached(query, top_k, effective_filter, results)
        return results

    async def _search_uncached(
        self, query: str, top_k: int, pinecone_filter: Optional[dict]
    ) -> list[dict]:
        index = _get_pinecone_index()

        # Embed query
        embeddings = await _embed([query])
        query_vector = embeddings[0]

        # Semantic search via Pinecone
        # (pinecone_filter already built by caller)
        log.info("pinecone.query", filter=str(pinecone_filter), query_preview=query[:50])
        try:
            semantic_results = index.query(
                vector=query_vector,
                top_k=top_k * 2,
                filter=pinecone_filter,
                include_metadata=True,
            )
            semantic_chunks = [
                {
                    "id": m.id,
                    "score": m.score,
                    "text": m.metadata.get("text", ""),
                    "title": m.metadata.get("title", ""),
                    "source": m.metadata.get("source", ""),
                    "url": m.metadata.get("url", ""),
                }
                for m in semantic_results.matches
            ]
        except Exception as e:
            log.warning("pinecone.error", error=str(e))
            semantic_chunks = []

        # BM25 search against all fetched metadata (lightweight in-memory)
        if semantic_chunks:
            bm25 = _get_bm25(semantic_chunks)
            tokens = query.lower().split()
            bm25_scores = bm25.get_scores(tokens)
            bm25_ranked = sorted(
                zip(bm25_scores, semantic_chunks),
                key=lambda x: x[0],
                reverse=True,
            )
            bm25_chunks = [chunk for _, chunk in bm25_ranked]
        else:
            bm25_chunks = []

        # Fuse and deduplicate
        fused = _rrf([semantic_chunks, bm25_chunks])
        fused = _deduplicate(fused)
        return fused[:top_k]
