"""
Clinical practice guidelines via PubMed E-utilities API.
No API key required for modest usage (< 3 req/sec).
"""

import asyncio
import json
from pathlib import Path
from xml.etree import ElementTree as ET
import httpx
import structlog

log = structlog.get_logger()

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

CONDITIONS = [
    "rheumatoid arthritis biologic DMARD guidelines",
    "psoriatic arthritis treatment guidelines systematic review",
    "multiple sclerosis disease modifying therapy",
    "Crohn disease biologic treatment guidelines",
    "ulcerative colitis biologic therapy",
    "breast cancer HER2 trastuzumab guidelines",
    "lung cancer immunotherapy pembrolizumab guidelines",
    "type 2 diabetes GLP1 agonist guidelines",
    "heart failure SGLT2 inhibitor therapy",
    "atopic dermatitis dupilumab treatment guidelines",
    "severe asthma biologic treatment",
    "migraine prevention CGRP guidelines",
    "osteoporosis treatment guidelines bisphosphonate",
    "growth hormone deficiency treatment guidelines",
    "hereditary angioedema treatment",
    "psoriasis biologic treatment guidelines",
    "ankylosing spondylitis biologic therapy",
    "inflammatory bowel disease biologic guidelines",
]


async def search_pubmed(condition: str, client: httpx.AsyncClient) -> list[str]:
    """Search PubMed and return PMIDs."""
    try:
        resp = await client.get(
            ESEARCH_URL,
            params={
                "db": "pubmed",
                "term": f"{condition}[Title/Abstract]",
                "retmode": "json",
                "retmax": 5,
                "sort": "relevance",
                "mindate": "2018",
            },
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("esearchresult", {}).get("idlist", [])
    except Exception as e:
        log.warning("pubmed.search.failed", condition=condition[:50], error=str(e))
        return []


async def fetch_abstracts(pmids: list[str], client: httpx.AsyncClient) -> list[dict]:
    """Fetch abstract XML for given PMIDs."""
    if not pmids:
        return []
    try:
        resp = await client.get(
            EFETCH_URL,
            params={
                "db": "pubmed",
                "id": ",".join(pmids),
                "retmode": "xml",
                "rettype": "abstract",
            },
            timeout=30,
        )
        resp.raise_for_status()

        root = ET.fromstring(resp.text)
        documents = []

        for article in root.findall(".//PubmedArticle"):
            try:
                pmid_el = article.find(".//PMID")
                pmid = pmid_el.text if pmid_el is not None else ""

                title_el = article.find(".//ArticleTitle")
                title = "".join(title_el.itertext()) if title_el is not None else "Unknown"

                abstract_els = article.findall(".//AbstractText")
                abstract = " ".join("".join(el.itertext()) for el in abstract_els)

                journal_el = article.find(".//Journal/Title")
                journal = journal_el.text if journal_el is not None else ""

                year_el = article.find(".//PubDate/Year")
                year = year_el.text if year_el is not None else ""

                # Classify source by journal
                source = "GUIDELINES"
                journal_lower = journal.lower()
                if any(x in journal_lower for x in ["arthritis", "rheumatol"]):
                    source = "ACR"
                elif any(x in journal_lower for x in ["heart", "cardiol", "circulation"]):
                    source = "AHA"
                elif any(x in journal_lower for x in ["diabetes", "endocrin"]):
                    source = "ADA"
                elif any(x in journal_lower for x in ["cancer", "oncol", "asco"]):
                    source = "ASCO"
                elif any(x in journal_lower for x in ["neurol", "multiple sclerosis"]):
                    source = "AAN"

                if abstract:
                    documents.append({
                        "id": f"pubmed_{pmid}",
                        "source": source,
                        "title": f"{title} ({year})",
                        "text": f"{title}\n\n{abstract}"[:4000],
                        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                        "metadata": {
                            "pmid": pmid,
                            "journal": journal,
                            "year": year,
                            "type": "GUIDELINE",
                        },
                    })
            except Exception as e:
                log.warning("pubmed.parse.article.failed", error=str(e))

        return documents

    except Exception as e:
        log.warning("pubmed.fetch.failed", pmids=pmids, error=str(e))
        return []


async def download(out_dir: Path) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    all_documents = []

    async with httpx.AsyncClient() as client:
        for condition in CONDITIONS:
            pmids = await search_pubmed(condition, client)
            if pmids:
                docs = await fetch_abstracts(pmids, client)
                all_documents.extend(docs)
                log.info("guidelines.condition.done", condition=condition[:50], docs=len(docs))
            await asyncio.sleep(0.4)  # PubMed rate limit: 3 req/sec

    # Deduplicate by ID
    seen = set()
    unique_docs = []
    for doc in all_documents:
        if doc["id"] not in seen:
            seen.add(doc["id"])
            unique_docs.append(doc)

    (out_dir / "guidelines_documents.json").write_text(json.dumps(unique_docs, indent=2))
    log.info("guidelines.download.complete", total=len(unique_docs))
    return unique_docs
