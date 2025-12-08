"""
Agent tests. Uses mocked LLM/retrieval responses to test graph routing logic.
Run: pytest tests/ -v
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock


# ── Sample test data ──────────────────────────────────────────────────────────

HUMIRA_DENIAL = """BlueCross BlueShield is denying prior authorization for adalimumab
(Humira) 40mg biweekly for patient ID 4821-B under Medical Policy 4.2.1b —
Biologic DMARD Agents. Denial reason: Medical records do not document adequate
trial and failure of two conventional DMARDs (methotrexate and at least one
additional agent) for a minimum of 3 months each. Claim ID: BCB-2024-PA-10392."""

VAGUE_DENIAL = "Insurance denied the medication."

EXTRACTED_DENIAL_INFO = {
    "drug_or_procedure": "adalimumab (Humira)",
    "denial_reason": "insufficient DMARD failure documentation",
    "policy_code": "4.2.1b",
    "payer": "BlueCross BlueShield",
    "patient_id": "4821-B",
    "claim_id": "BCB-2024-PA-10392",
}


# ── Unit tests for routing functions ──────────────────────────────────────────

def test_route_high_confidence():
    from agent.graph import route_after_contradiction_finder
    state = {"confidence_score": 0.85}
    assert route_after_contradiction_finder(state) == "appeal_drafter"


def test_route_medium_confidence():
    from agent.graph import route_after_contradiction_finder
    state = {"confidence_score": 0.55}
    assert route_after_contradiction_finder(state) == "appeal_drafter"


def test_route_low_confidence():
    from agent.graph import route_after_contradiction_finder
    state = {"confidence_score": 0.20}
    assert route_after_contradiction_finder(state) == "escalation_node"


def test_route_quality_done():
    from agent.graph import route_after_quality_check
    state = {"quality_score": 0.85, "quality_loop_count": 1}
    assert route_after_quality_check(state) == "done"


def test_route_quality_revise():
    from agent.graph import route_after_quality_check
    state = {"quality_score": 0.55, "quality_loop_count": 1}
    assert route_after_quality_check(state) == "revise"


def test_route_quality_max_loops():
    """After max loops, always return done regardless of score."""
    from agent.graph import route_after_quality_check
    state = {"quality_score": 0.40, "quality_loop_count": 2}
    assert route_after_quality_check(state) == "done"


# ── Integration-style tests (mocked LLM) ─────────────────────────────────────

@pytest.mark.asyncio
async def test_denial_reader_parses_structured_output():
    """denial_reader should extract structured info from denial text."""
    import json
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps(EXTRACTED_DENIAL_INFO))]

    with patch("agent.nodes.client") as mock_client:
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        from agent.nodes import denial_reader
        state = {
            "raw_denial_text": HUMIRA_DENIAL,
            "session_id": "test-123",
            "user_id": "test",
        }
        result = await denial_reader(state)

    assert result["denial_info"]["drug_or_procedure"] == "adalimumab (Humira)"
    assert result["denial_info"]["policy_code"] == "4.2.1b"
    assert result["denial_info"]["payer"] == "BlueCross BlueShield"


@pytest.mark.asyncio
async def test_contradiction_finder_high_confidence():
    """contradiction_finder should produce high confidence with strong evidence."""
    import json
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps({
        "contradictions": [
            {
                "payer_says": "Two DMARDs must fail",
                "evidence_says": "ACR 2023: one DMARD failure is sufficient",
                "source": "ACR 2023",
                "strength": "strong",
            }
        ],
        "confidence_score": 0.87,
        "confidence_reason": "ACR guidelines directly contradict two-DMARD requirement",
        "appeal_viable": True,
    }))]

    with patch("agent.nodes.client") as mock_client:
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        from agent.nodes import contradiction_finder
        state = {
            "session_id": "test-456",
            "denial_info": EXTRACTED_DENIAL_INFO,
            "payer_policy_text": "Two DMARDs must fail before biologic approval.",
            "clinical_evidence": [
                {
                    "source": "ACR",
                    "title": "ACR 2023 RA Guidelines",
                    "text": "Biologics appropriate after one DMARD failure.",
                    "relevance_score": 0.9,
                    "contradicts_denial": True,
                    "url": "https://rheumatology.org",
                }
            ],
            "fda_evidence": [],
        }
        result = await contradiction_finder(state)

    assert result["confidence_score"] == 0.87
    assert result["appeal_viable"] is True
    assert len(result["contradictions"]) == 1


@pytest.mark.asyncio
async def test_escalation_node_generates_specific_gaps():
    """escalation_node should produce specific missing evidence items, not generic notice."""
    import json
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps({
        "escalation_reason": "Cannot find DMARD trial history in knowledge base",
        "missing_evidence": [
            "Documentation of previous DMARD trials with dates and duration",
            "Clinical notes with disease severity score (DAS28)",
        ],
        "found_summary": "FDA label confirms Humira indicated for RA",
    }))]

    with patch("agent.nodes.client") as mock_client:
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        from agent.nodes import escalation_node
        state = {
            "session_id": "test-789",
            "denial_info": EXTRACTED_DENIAL_INFO,
            "payer_policy_text": "Two DMARDs required.",
            "clinical_evidence": [],
            "fda_evidence": [],
        }
        result = await escalation_node(state)

    assert result["escalated"] is True
    assert len(result["missing_evidence"]) >= 1
    # Should be specific, not empty
    assert any(result["missing_evidence"])


@pytest.mark.asyncio
async def test_quality_checker_flags_missing_citations():
    """quality_checker should return quality_issues when citations are absent."""
    import json
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps({
        "quality_score": 0.55,
        "quality_issues": [
            "Clinical claim about DMARD failure has no citation",
            "Letter does not address specific denial reason",
        ],
    }))]

    with patch("agent.nodes.client") as mock_client:
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        from agent.nodes import quality_checker
        state = {
            "session_id": "test-qc",
            "denial_info": EXTRACTED_DENIAL_INFO,
            "appeal_letter": "Dear Medical Director, we appeal this denial. Adalimumab is effective.",
            "clinical_evidence": [],
            "fda_evidence": [],
            "quality_loop_count": 0,
        }
        result = await quality_checker(state)

    assert result["quality_score"] == 0.55
    assert len(result["quality_issues"]) == 2
    assert result["quality_loop_count"] == 1  # incremented


# ── API endpoint tests ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sync_appeal_endpoint():
    """POST /appeals/ should return structured response."""
    from fastapi.testclient import TestClient
    from api.main import app

    final_mock_state = {
        "denial_info": EXTRACTED_DENIAL_INFO,
        "appeal_letter": "Dear Medical Director...",
        "confidence_score": 0.87,
        "quality_score": 0.90,
        "escalated": False,
        "escalation_reason": None,
        "missing_evidence": [],
        "citations_used": [{"source": "ACR 2023", "text": ""}],
        "contradictions": [],
        "clinical_evidence": [],
        "fda_evidence": [],
        "payer_policy_text": "",
        "policy_chunks": [],
    }

    # Patch at the import site in the route module, not at the definition site
    with patch("api.routes.appeals.appeal_graph") as mock_graph, \
         patch("api.routes.appeals._persist_case", new_callable=AsyncMock):
        mock_graph.ainvoke = AsyncMock(return_value=final_mock_state)

        client = TestClient(app)
        response = client.post("/appeals/", json={
            "denial_text": HUMIRA_DENIAL,
            "user_id": "test-user",
        })

    assert response.status_code == 200
    data = response.json()
    assert "appeal_letter" in data
    assert "confidence_score" in data
    assert data["escalated"] is False
