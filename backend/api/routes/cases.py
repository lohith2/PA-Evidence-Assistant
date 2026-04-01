from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from api.db import AsyncSessionLocal
from agent.phi_scrubber import scrub_phi
from typing import Optional

router = APIRouter()


@router.get("/")
async def list_cases(
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
):
    filters = []
    params: dict = {"limit": limit, "offset": offset}

    if status and status != "all":
        filters.append("status = :status")
        params["status"] = status

    if search:
        filters.append("(drug_or_procedure ILIKE :search OR payer ILIKE :search)")
        params["search"] = f"%{search}%"

    where = ("WHERE " + " AND ".join(filters)) if filters else ""

    async with AsyncSessionLocal() as db:
        result = await db.execute(text(f"""
            SELECT
                id, session_id, user_id, drug_or_procedure, payer,
                denial_reason, policy_code, confidence_score, quality_score,
                escalated, status, outcome,
                COALESCE(display_created_at, created_at) as created_at
            FROM appeal_cases
            {where}
            ORDER BY COALESCE(display_created_at, created_at) DESC
            LIMIT :limit OFFSET :offset
        """), params)
        rows = result.mappings().all()

        count_result = await db.execute(text(f"""
            SELECT COUNT(*) as total FROM appeal_cases {where}
        """), {k: v for k, v in params.items() if k not in ("limit", "offset")})
        total = count_result.scalar()

    return {
        "total": total,
        "cases": [
            {
                **dict(r),
                "created_at": str(r["created_at"]) if r["created_at"] else None,
                "confidence_score": round((r["confidence_score"] or 0) * 100),
                "quality_score": round((r["quality_score"] or 0) * 100),
            }
            for r in rows
        ],
    }


@router.get("/{session_id}")
async def get_case(session_id: str):
    async with AsyncSessionLocal() as db:
        result = await db.execute(text("""
            SELECT *, COALESCE(display_created_at, created_at) as created_at
            FROM appeal_cases
            WHERE session_id = :session_id
        """), {"session_id": session_id})
        row = result.mappings().one_or_none()

        if not row:
            raise HTTPException(status_code=404, detail="Case not found")

        ev_result = await db.execute(text("""
            SELECT * FROM evidence_items WHERE session_id = :session_id
            ORDER BY relevance_score DESC
        """), {"session_id": session_id})
        evidence = ev_result.mappings().all()

    case = dict(row)
    case["created_at"] = str(case["created_at"]) if case["created_at"] else None
    # Scrub any residual PHI from raw_denial_text before returning
    if "raw_denial_text" in case:
        case["raw_denial_text"] = scrub_phi(case["raw_denial_text"])
    return {
        **case,
        "evidence_items": [dict(e) for e in evidence],
        "phi_notice": "This response has been de-identified per HIPAA Safe Harbor.",
    }


class UpdateCaseRequest(BaseModel):
    status: Optional[str] = None
    appeal_letter: Optional[str] = None
    outcome: Optional[str] = None


@router.patch("/{session_id}")
async def update_case(session_id: str, body: UpdateCaseRequest):
    async with AsyncSessionLocal() as db:
        await db.execute(text("""
            UPDATE appeal_cases
            SET status = COALESCE(:status, status),
                appeal_letter = COALESCE(:letter, appeal_letter),
                outcome = COALESCE(:outcome, outcome)
            WHERE session_id = :sid
        """), {
            "status": body.status,
            "letter": body.appeal_letter,
            "outcome": body.outcome,
            "sid": session_id,
        })
        await db.commit()
    return {"status": "updated", "session_id": session_id}


@router.patch("/{session_id}/status")
async def update_status(session_id: str, body: dict):
    status = body.get("status")
    outcome = body.get("outcome")

    async with AsyncSessionLocal() as db:
        await db.execute(text("""
            UPDATE appeal_cases
            SET status = COALESCE(:status, status),
                outcome = COALESCE(:outcome, outcome)
            WHERE session_id = :session_id
        """), {"session_id": session_id, "status": status, "outcome": outcome})
        await db.commit()

    return {"ok": True}
