"""
LLM-as-judge evaluation endpoint.

Evaluates appeal letter quality on 4 dimensions:
  - citation_accuracy: do citations match evidence sources?
  - policy_compliance: does the letter address the specific policy requirements?
  - clinical_accuracy: are clinical claims accurate per the evidence?
  - letter_quality: professional tone, structure, specificity

Uses Sonnet for evaluation (same quality as appeal drafter — judge should be
at least as capable as the model being judged).
"""

import json
import structlog
from fastapi import APIRouter, HTTPException
from google import genai
from google.genai import types
from sqlalchemy import text

from config import settings
from api.db import AsyncSessionLocal

log = structlog.get_logger()
router = APIRouter()
client = genai.Client(api_key=settings.gemini_api_key)


@router.post("/run")
async def run_eval(body: dict):
    session_id = body.get("session_id")
    if not session_id:
        raise HTTPException(400, "session_id required")

    async with AsyncSessionLocal() as db:
        case_result = await db.execute(text(
            "SELECT * FROM appeal_cases WHERE session_id = :sid"
        ), {"sid": session_id})
        case = case_result.mappings().one_or_none()
        if not case:
            raise HTTPException(404, "Case not found")

        ev_result = await db.execute(text(
            "SELECT title, source, text FROM evidence_items WHERE session_id = :sid"
        ), {"sid": session_id})
        evidence = ev_result.mappings().all()

    letter = case["appeal_letter"] or ""
    if not letter:
        raise HTTPException(400, "No appeal letter to evaluate")

    evidence_summary = "\n".join(
        f"[{e['source']}] {e['title']}: {e['text'][:200]}"
        for e in evidence[:10]
    )

    prompt = f"""Evaluate this prior authorization appeal letter on 4 dimensions (0.0-1.0 each).

Evidence available:
{evidence_summary}

Appeal letter:
{letter[:3000]}

Denial reason being appealed: {case['denial_reason']}
Payer policy: {case['policy_code']}

Score:
1. citation_accuracy: Do all citations in [brackets] match the available evidence sources?
2. policy_compliance: Does the letter directly address the specific denial reason and policy code?
3. clinical_accuracy: Are clinical claims accurate and supported by the listed evidence?
4. letter_quality: Professional tone, clear structure, specific and actionable arguments?

Output JSON only:
{{
  "citation_accuracy": 0.0,
  "policy_compliance": 0.0,
  "clinical_accuracy": 0.0,
  "letter_quality": 0.0,
  "overall": 0.0,
  "reasoning": "brief explanation"
}}"""

    response = await client.aio.models.generate_content(
        model=settings.model_reasoning,
        contents=prompt,
        config=types.GenerateContentConfig(
            max_output_tokens=512,
            temperature=0
        )
    )

    text_resp = (response.text or "").strip()
    if text_resp.startswith("```"):
        text_resp = text_resp.split("```")[1]
        if text_resp.startswith("json"):
            text_resp = text_resp[4:]

    scores = json.loads(text_resp)

    # Persist eval results
    async with AsyncSessionLocal() as db:
        await db.execute(text("""
            INSERT INTO eval_results (
                session_id, citation_accuracy, policy_compliance,
                clinical_accuracy, letter_quality, overall, reasoning
            ) VALUES (
                :session_id, :citation_accuracy, :policy_compliance,
                :clinical_accuracy, :letter_quality, :overall, :reasoning
            )
        """), {"session_id": session_id, **scores})
        await db.commit()

    log.info("eval.complete", session_id=session_id, overall=scores.get("overall"))
    return scores
