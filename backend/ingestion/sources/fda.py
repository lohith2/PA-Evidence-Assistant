"""
FDA drug label data via OpenFDA API.
Targets the 35 most-denied drugs in prior authorization cases.
"""

import asyncio
import json
from pathlib import Path
import httpx
import structlog

log = structlog.get_logger()

OPENFDA_URL = "https://api.fda.gov/drug/label.json"

DRUGS = [
    "adalimumab", "etanercept", "infliximab", "rituximab", "bevacizumab",
    "trastuzumab", "pembrolizumab", "nivolumab", "dupilumab", "secukinumab",
    "ustekinumab", "tocilizumab", "abatacept", "vedolizumab", "natalizumab",
    "ocrelizumab", "dimethyl fumarate", "fingolimod", "siponimod",
    "semaglutide", "liraglutide", "dulaglutide", "empagliflozin",
    "dapagliflozin", "canagliflozin", "sacubitril", "ivacaftor",
    "lumacaftor", "elexacaftor", "nusinersen", "risdiplam",
    "eculizumab", "ravulizumab", "burosumab",
]

EXTRACT_FIELDS = [
    "indications_and_usage",
    "clinical_pharmacology",
    "mechanism_of_action",
    "contraindications",
    "dosage_and_administration",
    "warnings_and_cautions",
]


def _first(val) -> str:
    """FDA fields are lists of strings — take the first."""
    if isinstance(val, list):
        return val[0] if val else ""
    return val or ""


async def fetch_drug(drug: str, client: httpx.AsyncClient) -> list[dict]:
    try:
        resp = await client.get(
            OPENFDA_URL,
            params={"search": f'openfda.generic_name:"{drug}"', "limit": 2},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        documents = []

        for i, label in enumerate(results):
            openfda = label.get("openfda", {})
            brand = _first(openfda.get("brand_name", [drug]))
            generic = _first(openfda.get("generic_name", [drug]))

            # Combine the most relevant fields into one searchable text
            parts = []
            for field in EXTRACT_FIELDS:
                content = _first(label.get(field, ""))
                if content:
                    parts.append(f"=== {field.replace('_', ' ').upper()} ===\n{content[:1200]}")

            text = "\n\n".join(parts)
            if not text:
                continue

            documents.append({
                "id": f"fda_{drug.replace(' ', '_')}_{i}",
                "source": "FDA",
                "title": f"FDA Label: {brand} ({generic})",
                "text": text[:5000],
                "url": f"https://dailymed.nlm.nih.gov/dailymed/search.cfm?query={drug}",
                "metadata": {
                    "drug": drug,
                    "brand_name": brand,
                    "generic_name": generic,
                    "type": "FDA_LABEL",
                },
            })

        return documents

    except Exception as e:
        log.warning("fda.drug.failed", drug=drug, error=str(e))
        return []


async def download(out_dir: Path) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    documents = []

    async with httpx.AsyncClient() as client:
        # Process in batches of 5 to avoid rate limits
        for i in range(0, len(DRUGS), 5):
            batch = DRUGS[i:i+5]
            results = await asyncio.gather(*[fetch_drug(drug, client) for drug in batch])
            for drug_docs in results:
                documents.extend(drug_docs)
            await asyncio.sleep(1.0)
            log.info("fda.progress", done=min(i+5, len(DRUGS)), total=len(DRUGS))

    (out_dir / "fda_documents.json").write_text(json.dumps(documents, indent=2))
    log.info("fda.download.complete", total=len(documents))
    return documents
