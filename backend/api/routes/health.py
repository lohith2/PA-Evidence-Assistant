from datetime import timedelta
from fastapi import APIRouter
from sqlalchemy import text
from api.db import AsyncSessionLocal
from api.date_overrides import display_created_at
import redis.asyncio as aioredis
from config import settings

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/stats")
async def stats():
    async with AsyncSessionLocal() as db:
        result = await db.execute(text("""
            SELECT
                COUNT(*) as total_appeals,
                AVG(confidence_score) as avg_confidence,
                AVG(quality_score) as avg_quality,
                COUNT(*) FILTER (WHERE escalated = true) as escalated_count,
                COUNT(*) FILTER (WHERE outcome = 'approved') as approved_count,
                COUNT(*) FILTER (WHERE outcome IS NOT NULL) as submitted_count,
                COUNT(*) FILTER (WHERE status = 'submitted') as pending_count
            FROM appeal_cases
        """))
        row = result.mappings().one()

        payer_result = await db.execute(text("""
            SELECT payer, COUNT(*) as count
            FROM appeal_cases
            WHERE payer IS NOT NULL
            GROUP BY payer
            ORDER BY count DESC
            LIMIT 10
        """))
        payer_rows = payer_result.mappings().all()

        drug_result = await db.execute(text("""
            SELECT drug_or_procedure, COUNT(*) as count
            FROM appeal_cases
            WHERE drug_or_procedure IS NOT NULL
            GROUP BY drug_or_procedure
            ORDER BY count DESC
            LIMIT 10
        """))
        drug_rows = drug_result.mappings().all()

        trend_result = await db.execute(text("""
            SELECT session_id, outcome
            FROM appeal_cases
        """))
        trend_rows = trend_result.mappings().all()

    total = row["total_appeals"] or 0
    submitted = row["submitted_count"] or 0
    approved = row["approved_count"] or 0
    approval_rate = round((approved / submitted * 100) if submitted > 0 else 0, 1)

    trend_buckets: dict[str, dict[str, int | str]] = {}
    for r in trend_rows:
        pseudo_date = display_created_at(r["session_id"])
        week_start = pseudo_date - timedelta(days=pseudo_date.weekday())
        week_key = week_start.date().isoformat()
        bucket = trend_buckets.setdefault(week_key, {
            "week": week_key,
            "appeals": 0,
            "approved": 0,
        })
        bucket["appeals"] += 1
        if r["outcome"] == "approved":
            bucket["approved"] += 1

    approval_trend = [trend_buckets[k] for k in sorted(trend_buckets)]

    return {
        "total_appeals": total,
        "avg_confidence": round((row["avg_confidence"] or 0) * 100, 1),
        "avg_quality": round((row["avg_quality"] or 0) * 100, 1),
        "escalated_count": row["escalated_count"] or 0,
        "approved_count": approved,
        "submitted_count": submitted,
        "pending_count": row["pending_count"] or 0,
        "approval_rate": approval_rate,
        "time_saved_hours": round(total * 2.5, 1),
        "appeals_by_payer": [dict(r) for r in payer_rows],
        "appeals_by_drug": [dict(r) for r in drug_rows],
        "approval_trend": approval_trend,
    }
