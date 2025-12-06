"""
CMS National Coverage Determinations (NCD) and Local Coverage Determinations (LCD).
Fetched from the CMS Medicare Coverage Database API — completely free, no auth needed.
"""

import asyncio
import json
from pathlib import Path
import httpx
import structlog

log = structlog.get_logger()

NCD_LIST_URL = "https://www.cms.gov/medicare-coverage-database/api/v1/ncd/list"
LCD_SEARCH_URL = "https://www.cms.gov/medicare-coverage-database/api/v1/lcd"

LCD_SEARCH_TERMS = [
    "biologic agents", "IVIG", "growth hormone", "chemotherapy",
    "immunotherapy", "monoclonal antibody", "rheumatoid arthritis",
    "multiple sclerosis", "diabetes", "cardiovascular", "oncology",
]


async def fetch_ncds(out_dir: Path, client: httpx.AsyncClient) -> list[dict]:
    """Fetch all NCDs from CMS API."""
    documents = []
    try:
        resp = await client.get(NCD_LIST_URL, timeout=30)
        resp.raise_for_status()
        ncd_list = resp.json()

        items = ncd_list if isinstance(ncd_list, list) else ncd_list.get("data", [])
        log.info("cms.ncd.fetched_list", count=len(items))

        # Fetch individual NCDs (limit to avoid rate limiting)
        for item in items[:50]:
            ncd_id = item.get("id") or item.get("ncdId")
            if not ncd_id:
                continue
            try:
                detail_resp = await client.get(
                    f"https://www.cms.gov/medicare-coverage-database/api/v1/ncd/{ncd_id}",
                    timeout=30
                )
                detail_resp.raise_for_status()
                detail = detail_resp.json()

                # Extract text — field names vary in CMS API
                text_fields = ["coverageSummary", "summary", "description", "body", "content"]
                text = ""
                for field in text_fields:
                    text = detail.get(field, "")
                    if text:
                        break

                if text:
                    documents.append({
                        "id": f"ncd_{ncd_id}",
                        "source": "CMS",
                        "title": detail.get("title", detail.get("name", f"NCD {ncd_id}")),
                        "text": text[:4000],
                        "url": f"https://www.cms.gov/medicare-coverage-database/view/ncd.aspx?NCDId={ncd_id}",
                        "metadata": {"type": "NCD", "ncd_id": str(ncd_id)},
                    })
                await asyncio.sleep(0.2)  # Rate limiting
            except Exception as e:
                log.warning("cms.ncd.detail.failed", ncd_id=ncd_id, error=str(e))

    except Exception as e:
        log.error("cms.ncd.list.failed", error=str(e))

    log.info("cms.ncd.complete", documents=len(documents))
    return documents


async def fetch_lcds(out_dir: Path, client: httpx.AsyncClient) -> list[dict]:
    """Fetch LCDs for high-denial drug categories."""
    documents = []
    for term in LCD_SEARCH_TERMS:
        try:
            resp = await client.get(
                LCD_SEARCH_URL,
                params={"keyword": term, "maxResults": 10},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            items = data if isinstance(data, list) else data.get("data", [])

            for item in items[:5]:
                lcd_id = item.get("id") or item.get("lcdId")
                text = item.get("coverageSummary") or item.get("summary") or item.get("description", "")
                if text:
                    documents.append({
                        "id": f"lcd_{lcd_id}_{term.replace(' ', '_')}",
                        "source": "CMS",
                        "title": item.get("title", f"LCD: {term}"),
                        "text": text[:4000],
                        "url": item.get("url", ""),
                        "metadata": {"type": "LCD", "search_term": term},
                    })
            await asyncio.sleep(0.3)
        except Exception as e:
            log.warning("cms.lcd.failed", term=term, error=str(e))

    log.info("cms.lcd.complete", documents=len(documents))
    return documents


async def download(out_dir: Path) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient() as client:
        ncds, lcds = await asyncio.gather(
            fetch_ncds(out_dir, client),
            fetch_lcds(out_dir, client),
        )

    documents = ncds + lcds
    (out_dir / "cms_documents.json").write_text(json.dumps(documents, indent=2))
    log.info("cms.download.complete", total=len(documents))
    return documents
