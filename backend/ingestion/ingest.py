"""
Main ingestion pipeline.

Usage:
  python -m ingestion.ingest --source ALL
  python -m ingestion.ingest --source CMS --path ./data/cms
  python -m ingestion.ingest --source FDA --path ./data/fda

Chunks documents, embeds with Voyage AI, upserts to Pinecone in batches of 100.
Target: >1000 vectors.
"""

import asyncio
import argparse
import json
from pathlib import Path
from typing import Optional
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential
import voyageai
from pinecone import Pinecone, ServerlessSpec

from config import settings

log = structlog.get_logger()

CHUNK_SIZE = 800    # ~200 tokens/chunk to stay comfortably under 10K TPM
CHUNK_OVERLAP = 100
BATCH_SIZE = 10     # 10 chunks × ~200 tokens = ~2K tokens/batch
EMBED_SLEEP = 25.0  # 3 RPM = 1 req/20s; 25s gives breathing room


def chunk_text(text: str, doc_id: str, metadata: dict) -> list[dict]:
    """Split long documents into overlapping chunks for retrieval."""
    chunks = []
    start = 0
    chunk_idx = 0

    while start < len(text):
        end = start + CHUNK_SIZE
        chunk = text[start:end]

        # Try to break at sentence boundary
        if end < len(text):
            last_period = chunk.rfind(". ")
            if last_period > CHUNK_SIZE // 2:
                chunk = chunk[:last_period + 1]
                end = start + last_period + 1

        chunks.append({
            "id": f"{doc_id}_chunk_{chunk_idx}",
            "text": chunk.strip(),
            "metadata": metadata,
        })
        start = end - CHUNK_OVERLAP
        chunk_idx += 1

    return chunks


@retry(stop=stop_after_attempt(6), wait=wait_exponential(multiplier=2, min=25, max=120))
async def embed_batch(texts: list[str], voyage: voyageai.AsyncClient) -> list[list[float]]:
    result = await voyage.embed(texts, model="voyage-3", input_type="document")
    return result.embeddings


def get_or_create_index(pc: Pinecone) -> object:
    existing = [idx.name for idx in pc.list_indexes()]
    if settings.pinecone_index not in existing:
        log.info("pinecone.index.creating", name=settings.pinecone_index)
        pc.create_index(
            name=settings.pinecone_index,
            dimension=1024,  # voyage-3 dimension
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        log.info("pinecone.index.created")
    return pc.Index(settings.pinecone_index)


async def ingest_documents(documents: list[dict], source_name: str):
    if not documents:
        log.warning("ingest.empty", source=source_name)
        return

    pc = Pinecone(api_key=settings.pinecone_api_key)
    index = get_or_create_index(pc)
    voyage = voyageai.AsyncClient(api_key=settings.voyage_api_key)

    # Chunk all documents
    all_chunks = []
    for doc in documents:
        meta = {
            "source": doc.get("source", source_name),
            "title": doc.get("title", ""),
            "url": doc.get("url", ""),
            "text": doc.get("text", "")[:1000],  # store truncated text in metadata
            **(doc.get("metadata") or {}),
        }
        chunks = chunk_text(doc.get("text", ""), doc["id"], meta)
        all_chunks.extend(chunks)

    log.info("ingest.chunks", source=source_name, chunks=len(all_chunks))

    # Embed and upsert in batches
    total_upserted = 0
    for i in range(0, len(all_chunks), BATCH_SIZE):
        batch = all_chunks[i:i + BATCH_SIZE]
        texts = [c["text"] for c in batch]

        embeddings = await embed_batch(texts, voyage)

        vectors = [
            {
                "id": chunk["id"],
                "values": embedding,
                "metadata": chunk["metadata"],
            }
            for chunk, embedding in zip(batch, embeddings)
        ]

        # Upsert is idempotent — safe to re-run
        index.upsert(vectors=vectors)
        total_upserted += len(vectors)
        log.info("ingest.batch.done", source=source_name,
                 batch=i // BATCH_SIZE + 1, upserted=total_upserted)

        await asyncio.sleep(EMBED_SLEEP)  # Voyage free tier rate limit

    log.info("ingest.source.complete", source=source_name, total=total_upserted)
    return total_upserted


async def main(source: str, data_path: Optional[str] = None):
    from ingestion.sources import cms, fda, guidelines, uspstf, payer_policies

    base = Path(data_path) if data_path else Path("./data")
    source_upper = source.upper()

    source_map = {
        "CMS": (cms.download, base / "cms"),
        "FDA": (fda.download, base / "fda"),
        "GUIDELINES": (guidelines.download, base / "guidelines"),
        "USPSTF": (uspstf.download, base / "uspstf"),
        "PAYER_POLICIES": (payer_policies.download, base / "payer_policies"),
    }

    if source_upper == "ALL":
        sources_to_run = list(source_map.keys())
    elif source_upper in source_map:
        sources_to_run = [source_upper]
    else:
        raise ValueError(f"Unknown source: {source}. Options: {list(source_map.keys())} or ALL")

    total = 0
    for src in sources_to_run:
        download_fn, out_dir = source_map[src]
        log.info("ingest.source.start", source=src)
        documents = await download_fn(out_dir)
        upserted = await ingest_documents(documents, src)
        total += upserted or 0

    # Final stats
    pc = Pinecone(api_key=settings.pinecone_api_key)
    index = pc.Index(settings.pinecone_index)
    stats = index.describe_index_stats()
    vector_count = stats["total_vector_count"]

    log.info("ingest.complete", total_upserted=total, pinecone_vectors=vector_count)
    print(f"\n✓ Ingestion complete. Total vectors in Pinecone: {vector_count}")

    if vector_count < 1000:
        print(f"⚠  Warning: Only {vector_count} vectors. Target is >1000.")
        print("   Run: python -m ingestion.ingest --source ALL")
    else:
        print("✓ Vector count target met (>1000)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prior Auth Agent — Data Ingestion Pipeline")
    parser.add_argument("--source", default="ALL",
                        help="Source to ingest: CMS, FDA, GUIDELINES, USPSTF, PAYER_POLICIES, or ALL")
    parser.add_argument("--path", default=None, help="Base data directory path")
    args = parser.parse_args()

    asyncio.run(main(args.source, args.path))
