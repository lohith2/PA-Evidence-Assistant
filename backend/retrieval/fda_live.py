"""
Live FDA label and PubMed fetchers.
Called by evidence_retriever when Pinecone returns 0 clinical results for a drug.
No API key required for either source.

After a successful fetch, chunks are ingested to Pinecone in the background so
future queries hit the cache instead of live-fetching again.
"""

import asyncio
import hashlib
import urllib.parse

import httpx
import structlog

from agent.state import EvidenceItem
from config import settings

log = structlog.get_logger()

OPENFDA_URL = "https://api.fda.gov/drug/label.json"
ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

LABEL_FIELDS = [
    "indications_and_usage",
    "clinical_pharmacology",
    "warnings_and_cautions",
    "contraindications",
    "description",
    "mechanism_of_action",
    "clinical_studies",
]

# Common biosimilar suffixes added by FDA — strip before searching
_BIOSIMILAR_SUFFIXES = [
    "-aekn", "-aacf", "-adaz", "-bwwd", "-adbm", "-dyyb", "-awwb", "-maly",
    "-aqvh", "-fkjp", "-bvvr", "-kxwh", "-bbmb", "-mnhz",
]


def _clean_drug_name(drug_string: str) -> str:
    """Extract searchable generic name from 'adalimumab (Humira) 40mg...'"""
    name = drug_string.split("(")[0].strip().lower()
    name = name.split()[0] if name else drug_string.lower()
    for suffix in _BIOSIMILAR_SUFFIXES:
        name = name.replace(suffix, "")
    return name.strip()


async def fetch_fda_label(drug_string: str) -> list[EvidenceItem]:
    """
    Fetch FDA drug label from OpenFDA for a given drug name.
    Tries generic name, brand name, and full-text search in order.
    Returns EvidenceItem list — empty if nothing found or on network error.
    """
    drug_keyword = _clean_drug_name(drug_string)
    log.info("fda_live.fetching", drug=drug_keyword)

    chunks: list[EvidenceItem] = []

    search_attempts = [
        f'openfda.generic_name:"{drug_keyword}"',
        f'openfda.brand_name:"{drug_keyword}"',
        f'indications_and_usage:"{drug_keyword}"',
    ]

    try:
        async with httpx.AsyncClient(timeout=15) as http:
            for search_field in search_attempts:
                r = await http.get(
                    OPENFDA_URL,
                    params={"search": search_field, "limit": 2},
                )
                if r.status_code != 200:
                    continue

                results = r.json().get("results", [])
                if not results:
                    continue

                for label in results[:2]:
                    openfda = label.get("openfda", {})
                    brand   = openfda.get("brand_name",   [drug_string])[0]
                    generic = openfda.get("generic_name", [drug_keyword])[0]
                    title   = f"FDA Label: {brand} ({generic.upper()})"

                    text_parts = [f"=== FDA LABEL: {brand} ===\n"]
                    for field in LABEL_FIELDS:
                        val = label.get(field, [])
                        if isinstance(val, list) and val:
                            field_name = field.replace("_", " ").upper()
                            text_parts.append(
                                f"=== {field_name} ===\n{val[0][:1000]}"
                            )
                        elif isinstance(val, str) and val:
                            text_parts.append(val[:500])

                    full_text = "\n\n".join(text_parts)
                    if len(full_text) <= 100:
                        continue

                    chunk: EvidenceItem = {
                        "source": "FDA",
                        "title": title,
                        "text": full_text,
                        "relevance_score": 0.80,
                        "contradicts_denial": False,
                        "url": "https://api.fda.gov/drug/label.json",
                        "live_fetch": True,
                    }
                    chunks.append(chunk)
                    log.info("fda_live.fetched",
                             drug=drug_keyword, title=title,
                             text_length=len(full_text))

                if chunks:
                    break  # stop trying search strategies once we have results

    except Exception as e:
        log.warning("fda_live.error", drug=drug_keyword, error=str(e))

    if not chunks:
        log.warning("fda_live.not_found", drug=drug_keyword)
    else:
        # Ingest to Pinecone in the background — fire-and-forget
        for chunk in chunks:
            asyncio.create_task(
                _ingest_to_pinecone(chunk, drug_keyword)
            )

    return chunks


async def fetch_pubmed_abstracts(
    drug: str,
    denial_reason: str,
    max_results: int = 3,
) -> list[EvidenceItem]:
    """
    Fetch PubMed abstracts for drug + clinical indication.
    Uses NCBI E-utilities — no API key needed.
    Returns EvidenceItem list — empty if nothing found or on network error.
    """
    drug_keyword = _clean_drug_name(drug)
    query = f"{drug_keyword} clinical trial indication approval"

    chunks: list[EvidenceItem] = []

    try:
        async with httpx.AsyncClient(timeout=15) as http:
            # Step 1: get PMIDs
            r = await http.get(ESEARCH_URL, params={
                "db": "pubmed",
                "term": query,
                "retmode": "json",
                "retmax": max_results,
                "sort": "relevance",
            })
            if r.status_code != 200:
                return []

            pmids = r.json().get("esearchresult", {}).get("idlist", [])
            if not pmids:
                return []

            # Step 2: fetch abstracts
            r2 = await http.get(EFETCH_URL, params={
                "db": "pubmed",
                "id": ",".join(pmids),
                "retmode": "text",
                "rettype": "abstract",
            })
            if r2.status_code != 200:
                return []

            abstracts = r2.text.strip().split("\n\n\n")
            for i, abstract in enumerate(abstracts[:max_results]):
                if len(abstract) <= 100:
                    continue
                pmid = pmids[i] if i < len(pmids) else "unknown"
                chunk: EvidenceItem = {
                    "source": "GUIDELINES",
                    "title": f"PubMed: {drug} clinical evidence (live fetch)",
                    "text": abstract[:2000],
                    "relevance_score": 0.65,
                    "contradicts_denial": False,
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    "live_fetch": True,
                }
                chunks.append(chunk)

    except Exception as e:
        log.warning("pubmed_live.error", drug=drug_keyword, error=str(e))

    return chunks


async def _ingest_to_pinecone(chunk: EvidenceItem, drug_keyword: str) -> None:
    """
    Background task: embed and upsert a live-fetched chunk to Pinecone.
    Errors are swallowed — ingestion failure must never affect the user response.
    """
    try:
        import voyageai
        from pinecone import Pinecone

        voyage = voyageai.AsyncClient(api_key=settings.voyage_api_key)
        result = await voyage.embed(
            [chunk["text"][:8000]],  # Voyage token limit
            model="voyage-3",
            input_type="document",
        )

        pc  = Pinecone(api_key=settings.pinecone_api_key)
        idx = pc.Index(settings.pinecone_index)

        chunk_id = "live-" + hashlib.sha256(
            (chunk["title"] + chunk["text"][:200]).encode()
        ).hexdigest()[:32]

        idx.upsert(vectors=[{
            "id": chunk_id,
            "values": result.embeddings[0],
            "metadata": {
                "text":       chunk["text"][:2000],
                "source":     chunk["source"],
                "title":      chunk["title"],
                "url":        chunk.get("url", ""),
                "drug":       drug_keyword,
                "live_fetch": True,
            },
        }])
        log.info("fda_live.ingested_to_pinecone", chunk_id=chunk_id,
                 drug=drug_keyword)
    except Exception as e:
        log.warning("fda_live.ingest_failed", drug=drug_keyword, error=str(e))
