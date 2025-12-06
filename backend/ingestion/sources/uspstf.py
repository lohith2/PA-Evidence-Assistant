"""
USPSTF (US Preventive Services Task Force) recommendations.
Free public API, no auth required.
"""

import json
from pathlib import Path
import httpx
import structlog

log = structlog.get_logger()

USPSTF_URL = "https://www.uspreventiveservicestaskforce.org/uspstf/uspstsapi/getAllRecommendations"


async def download(out_dir: Path) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    documents = []

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(USPSTF_URL, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            # Response is a list or has a data key — handle both
            items = data if isinstance(data, list) else data.get("data", data.get("items", []))

            for item in items:
                title = item.get("title") or item.get("Topic") or ""
                # Various field name patterns in USPSTF API
                text_fields = [
                    "recommendationSummary", "recommendation", "rationale",
                    "summary", "Statement", "body"
                ]
                text = ""
                for field in text_fields:
                    text = item.get(field, "")
                    if text:
                        break

                grade = item.get("grade") or item.get("Grade") or ""
                url = item.get("url") or item.get("Url") or ""

                if title and text:
                    documents.append({
                        "id": f"uspstf_{len(documents)}",
                        "source": "USPSTF",
                        "title": f"USPSTF: {title} (Grade {grade})",
                        "text": f"{title}\nGrade: {grade}\n\n{text}"[:4000],
                        "url": url,
                        "metadata": {
                            "grade": grade,
                            "type": "USPSTF_RECOMMENDATION",
                        },
                    })

        except Exception as e:
            log.warning("uspstf.failed", error=str(e))
            # Provide minimal fallback documents for common preventive care topics
            documents = _generate_fallback()

    (out_dir / "uspstf_documents.json").write_text(json.dumps(documents, indent=2))
    log.info("uspstf.download.complete", total=len(documents))
    return documents


def _generate_fallback() -> list[dict]:
    """Minimal fallback if API is unavailable."""
    return [
        {
            "id": "uspstf_diabetes_screening",
            "source": "USPSTF",
            "title": "USPSTF: Diabetes Screening (Grade B)",
            "text": "The USPSTF recommends screening for prediabetes and type 2 diabetes in adults aged 35 to 70 years who have overweight or obesity. Grade B recommendation.",
            "url": "https://www.uspreventiveservicestaskforce.org/uspstf/recommendation/screening-for-prediabetes-and-type-2-diabetes",
            "metadata": {"grade": "B", "type": "USPSTF_RECOMMENDATION"},
        },
        {
            "id": "uspstf_colorectal_screening",
            "source": "USPSTF",
            "title": "USPSTF: Colorectal Cancer Screening (Grade A)",
            "text": "The USPSTF recommends screening for colorectal cancer in all adults aged 45 to 75 years. Grade A recommendation.",
            "url": "https://www.uspreventiveservicestaskforce.org/uspstf/recommendation/colorectal-cancer-screening",
            "metadata": {"grade": "A", "type": "USPSTF_RECOMMENDATION"},
        },
    ]
