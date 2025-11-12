"""
Appeal endpoints:
  POST /appeals/stream  — SSE streaming (production path)
  POST /appeals/        — sync (testing / CI)
"""

import json
import uuid
import structlog
from fastapi import APIRouter, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text
from typing import Optional

from agent.graph import appeal_graph
from agent.state import AgentState
from agent.phi_scrubber import scrub_phi
from api.db import AsyncSessionLocal
from config import settings

log = structlog.get_logger()
router = APIRouter()

NODE_LABELS = {
    "denial_reader": "Reading denial letter",
    "admin_error_checker": "Checking for administrative errors",
    "policy_retriever": "Retrieving payer policy",
    "evidence_retriever": "Searching clinical guidelines",
    "contradiction_finder": "Analyzing evidence vs policy",
    "appeal_drafter": "Drafting appeal letter",
    "escalation_node": "Generating escalation notice",
    "quality_checker": "Checking letter quality",
}


class AppealRequest(BaseModel):
    denial_text: str
    patient_context: str = ""
    skip_admin_check: bool = False
    user_id: str = "anonymous"
    session_id: Optional[str] = None


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def _persist_case(session_id: str, request: AppealRequest, final_state: AgentState):
    """Write or update the appeal case in Postgres. Idempotent via ON CONFLICT."""
    info = final_state.get("denial_info") or {}
    all_evidence = (
        (final_state.get("clinical_evidence") or []) + 
        (final_state.get("fda_evidence") or []) +
        (final_state.get("policy_chunks") or [])
    )

    async with AsyncSessionLocal() as db:
        await db.execute(text("""
            INSERT INTO appeal_cases (
                session_id, user_id, raw_denial_text,
                drug_or_procedure, payer, denial_reason, policy_code,
                appeal_letter, confidence_score, quality_score,
                escalated, escalation_reason,
                citations, node_trace, status
            ) VALUES (
                :session_id, :user_id, :raw_denial_text,
                :drug, :payer, :denial_reason, :policy_code,
                :appeal_letter, :confidence_score, :quality_score,
                :escalated, :escalation_reason,
                CAST(:citations AS jsonb), CAST(:node_trace AS jsonb), :status
            )
            ON CONFLICT (session_id) DO UPDATE SET
                appeal_letter = EXCLUDED.appeal_letter,
                confidence_score = EXCLUDED.confidence_score,
                quality_score = EXCLUDED.quality_score,
                escalated = EXCLUDED.escalated,
                escalation_reason = EXCLUDED.escalation_reason,
                citations = EXCLUDED.citations,
                node_trace = EXCLUDED.node_trace,
                status = EXCLUDED.status
        """), {
            "session_id": session_id,
            "user_id": request.user_id,
            "raw_denial_text": scrub_phi(request.denial_text),
            "drug": info.get("drug_or_procedure"),
            "payer": info.get("payer"),
            "denial_reason": info.get("denial_reason"),
            "policy_code": info.get("policy_code"),
            "appeal_letter": final_state.get("appeal_letter"),
            "confidence_score": final_state.get("confidence_score"),
            "quality_score": final_state.get("quality_score"),
            "escalated": final_state.get("escalated", False),
            "escalation_reason": final_state.get("escalation_reason"),
            "citations": json.dumps(final_state.get("citations_used") or []),
            "node_trace": json.dumps([]),
            "status": "draft",
        })

        # Insert evidence items
        for ev in all_evidence:
            await db.execute(text("""
                INSERT INTO evidence_items (session_id, source, title, text, relevance_score, contradicts_denial, url)
                VALUES (:session_id, :source, :title, :text, :relevance_score, :contradicts_denial, :url)
            """), {
                "session_id": session_id,
                "source": ev.get("source"),
                "title": ev.get("title"),
                "text": ev.get("text"),
                "relevance_score": ev.get("relevance_score"),
                "contradicts_denial": ev.get("contradicts_denial"),
                "url": ev.get("url"),
            })

        await db.commit()


@router.post("/stream")
async def stream_appeal(request: AppealRequest):
    session_id = request.session_id or str(uuid.uuid4())
    log.info("appeal.stream.start", session_id=session_id, user_id=request.user_id)

    initial_state: AgentState = {
        "raw_denial_text": scrub_phi(request.denial_text),
        "patient_context": scrub_phi(request.patient_context),
        "skip_admin_check": request.skip_admin_check,
        "session_id": session_id,
        "user_id": request.user_id,
        "denial_info": {},
        "admin_error": False,
        "admin_error_type": None,
        "admin_explanation": None,
        "admin_suggestion": None,
        "admin_correct_code": None,
        "payer_policy_text": "",
        "policy_chunks": [],
        "payer_found": True,
        "payer_not_found_message": "",
        "clinical_evidence": [],
        "fda_evidence": [],
        "contradictions": [],
        "confidence_score": 0.0,
        "confidence_reason": "",
        "appeal_viable": False,
        "appeal_letter": "",
        "citations_used": [],
        "escalated": False,
        "escalation_reason": "",
        "missing_evidence": [],
        "quality_score": 0.0,
        "quality_issues": [],
        "quality_loop_count": 0,
        "messages": [],
        "faithfulness_score": None,
        "eval_logged": False,
    }

    async def event_generator():
        final_state = initial_state.copy()
        try:
            # Emit immediately so the frontend can show a loading state
            # instead of waiting ~2s for the first Gemini API roundtrip
            yield _sse("stream_started", {"session_id": session_id})

            async for event in appeal_graph.astream(initial_state, stream_mode="updates"):
                for node_name, node_output in event.items():
                    if node_name == "__end__":
                        continue

                    # Emit node_start before (we emit it after for simplicity with astream)
                    yield _sse("node_start", {
                        "node": node_name,
                        "label": NODE_LABELS.get(node_name, node_name),
                    })

                    # Merge into final state
                    final_state.update(node_output)

                    # Build node-specific summary data
                    summary = {}
                    if node_name == "denial_reader":
                        info = node_output.get("denial_info", {})
                        summary = {
                            "drug": info.get("drug_or_procedure"),
                            "payer": info.get("payer"),
                            "policy_code": info.get("policy_code"),
                        }
                    elif node_name == "admin_error_checker":
                        summary = {
                            "admin_error": node_output.get("admin_error", False),
                            "error_type": node_output.get("admin_error_type"),
                        }
                    elif node_name == "policy_retriever":
                        chunks = node_output.get("policy_chunks", [])
                        summary = {
                            "chunks_found": len(chunks),
                            "policy_chunks": chunks,
                            "payer_found": node_output.get("payer_found", True),
                            "payer_not_found_message": node_output.get("payer_not_found_message", ""),
                        }
                    elif node_name == "evidence_retriever":
                        raw_ev = node_output.get("clinical_evidence", []) + node_output.get("fda_evidence", [])
                        # Deduplicate by title+source so counts match the frontend panel
                        seen_titles: set[str] = set()
                        ev = []
                        for e in raw_ev:
                            key = f"{e.get('source', '')}:{e.get('title', '')}".lower()
                            if key not in seen_titles:
                                seen_titles.add(key)
                                ev.append(e)
                        source_counts: dict[str, int] = {}
                        for chunk in ev:
                            src = chunk.get("source") or "OTHER"
                            source_counts[src] = source_counts.get(src, 0) + 1
                        breakdown = ", ".join(
                            f"{src}: {cnt}"
                            for src, cnt in source_counts.items()
                            if src != "PAYER_POLICIES"
                        )
                        evidence_label = f"{len(ev)} evidence items retrieved"
                        if breakdown:
                            evidence_label += f" ({breakdown})"
                        summary = {
                            "evidence_found": len(ev),
                            "evidence_label": evidence_label,
                            "items": ev,
                        }
                    elif node_name == "contradiction_finder":
                        summary = {
                            "confidence": round(node_output.get("confidence_score", 0) * 100),
                            "contradictions": len(node_output.get("contradictions", [])),
                            "viable": node_output.get("appeal_viable"),
                        }
                    elif node_name == "appeal_drafter":
                        letter = node_output.get("appeal_letter", "")
                        summary = {"letter_length": len(letter.split())}
                    elif node_name == "quality_checker":
                        summary = {
                            "quality_score": round(node_output.get("quality_score", 0) * 100),
                            "issues": len(node_output.get("quality_issues", [])),
                        }

                    yield _sse("node_done", {"node": node_name, "data": summary})

            # Persist to Postgres
            await _persist_case(session_id, request, final_state)

            # Final done event
            all_evidence = (
                final_state.get("clinical_evidence") or []
            ) + (final_state.get("fda_evidence") or [])

            contradicting_count = sum(1 for e in all_evidence if e.get("contradicts_denial"))
            log.info("sse.contradicting_count",
                     count=contradicting_count,
                     total=len(all_evidence))

            # Build citations from evidence items by matching source/title against
            # the letter text. More reliable than the regex-bracket approach in
            # appeal_drafter, which misses sources the LLM cites in prose.
            appeal_letter = final_state.get("appeal_letter") or ""
            citations: list[dict] = []
            seen_citation_titles: set[str] = set()
            for chunk in all_evidence:
                source = (chunk.get("source") or "").strip()
                title = (chunk.get("title") or "").strip()
                if not source or not title or title in seen_citation_titles:
                    continue
                source_in_letter = (
                    f"[{source}" in appeal_letter
                    or source in appeal_letter
                )
                title_words = [w for w in title.split()[:3] if len(w) > 4]
                title_in_letter = any(w in appeal_letter for w in title_words)
                if chunk.get("contradicts_denial") or source_in_letter or title_in_letter:
                    citations.append({
                        "source": source,
                        "title": title,
                        "url": chunk.get("url", ""),
                        "contradicts_denial": chunk.get("contradicts_denial", False),
                    })
                    seen_citation_titles.add(title)
            # Fall back to regex-extracted citations if evidence scan found nothing
            if not citations:
                citations = final_state.get("citations_used") or []
            log.info("sse.citations_built",
                     count=len(citations),
                     sources=list({c["source"] for c in citations}))

            yield _sse("done", {
                "session_id": session_id,
                "appeal_letter": appeal_letter,
                "citations": citations,
                "confidence_score": final_state.get("confidence_score"),
                "quality_score": final_state.get("quality_score"),
                "quality_issues": final_state.get("quality_issues") or [],
                "escalated": final_state.get("escalated", False),
                "escalation_reason": final_state.get("escalation_reason"),
                "missing_evidence": final_state.get("missing_evidence") or [],
                "denial_info": final_state.get("denial_info"),
                "evidence_items": all_evidence,
                "policy_chunks": final_state.get("policy_chunks") or [],
                "payer_found": final_state.get("payer_found", True),
                "payer_not_found_message": final_state.get("payer_not_found_message", ""),
                "contradictions": final_state.get("contradictions") or [],
                "admin_error": final_state.get("admin_error", False),
                "admin_error_type": final_state.get("admin_error_type"),
                "admin_explanation": final_state.get("admin_explanation"),
                "admin_suggestion": final_state.get("admin_suggestion"),
                "admin_correct_code": final_state.get("admin_correct_code"),
            })

        except Exception as e:
            log.error("appeal.stream.error", error=str(e), session_id=session_id)
            yield _sse("error", {"message": str(e)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/")
async def sync_appeal(request: AppealRequest):
    """Synchronous version for testing. Runs the full graph and returns results."""
    session_id = request.session_id or str(uuid.uuid4())
    log.info("appeal.sync.start", session_id=session_id)

    initial_state: AgentState = {
        "raw_denial_text": scrub_phi(request.denial_text),
        "patient_context": scrub_phi(request.patient_context),
        "skip_admin_check": request.skip_admin_check,
        "session_id": session_id,
        "user_id": request.user_id,
        "denial_info": {},
        "admin_error": False,
        "admin_error_type": None,
        "admin_explanation": None,
        "admin_suggestion": None,
        "admin_correct_code": None,
        "payer_policy_text": "",
        "policy_chunks": [],
        "payer_found": True,
        "payer_not_found_message": "",
        "clinical_evidence": [],
        "fda_evidence": [],
        "contradictions": [],
        "confidence_score": 0.0,
        "confidence_reason": "",
        "appeal_viable": False,
        "appeal_letter": "",
        "citations_used": [],
        "escalated": False,
        "escalation_reason": "",
        "missing_evidence": [],
        "quality_score": 0.0,
        "quality_issues": [],
        "quality_loop_count": 0,
        "messages": [],
        "faithfulness_score": None,
        "eval_logged": False,
    }

    try:
        final_state = await appeal_graph.ainvoke(initial_state)
    except Exception as e:
        log.error("appeal.sync.agent_failed", error=str(e), session_id=session_id)
        return {
            "session_id": session_id,
            "appeal_letter": "",
            "confidence_score": 0.0,
            "quality_score": 0.0,
            "escalated": True,
            "escalation_reason": f"Agent encountered an error: {str(e)}. Please try again.",
            "missing_evidence": [],
            "denial_info": {},
            "contradictions": [],
            "citations": [],
            "admin_error": False,
            "admin_error_type": None,
            "admin_explanation": None,
            "admin_suggestion": None,
            "admin_correct_code": None,
            "error": str(e),
        }

    await _persist_case(session_id, request, final_state)

    return {
        "session_id": session_id,
        "appeal_letter": final_state.get("appeal_letter"),
        "confidence_score": final_state.get("confidence_score"),
        "quality_score": final_state.get("quality_score"),
        "escalated": final_state.get("escalated", False),
        "escalation_reason": final_state.get("escalation_reason"),
        "missing_evidence": final_state.get("missing_evidence") or [],
        "denial_info": final_state.get("denial_info"),
        "contradictions": final_state.get("contradictions") or [],
        "citations": final_state.get("citations_used") or [],
        "admin_error": final_state.get("admin_error", False),
        "admin_error_type": final_state.get("admin_error_type"),
        "admin_explanation": final_state.get("admin_explanation"),
        "admin_suggestion": final_state.get("admin_suggestion"),
        "admin_correct_code": final_state.get("admin_correct_code"),
    }


@router.post("/{session_id}/upload-pdf")
async def upload_pdf(session_id: str, file: UploadFile = File(...)):
    """Parse PDF denial letter and return extracted text."""
    from pypdf import PdfReader
    import io

    content = await file.read()
    reader = PdfReader(io.BytesIO(content))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return {"session_id": session_id, "extracted_text": text.strip()}
