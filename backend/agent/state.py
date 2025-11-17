from typing import TypedDict, Annotated, Optional
from langgraph.graph.message import add_messages


class DenialInfo(TypedDict):
    drug_or_procedure: str   # what was denied
    denial_reason: str       # exact reason from letter
    policy_code: str         # e.g. "4.2.1b"
    payer: str               # insurance company name
    patient_id: str          # redacted by phi_scrubber before storage
    claim_id: str


class EvidenceItem(TypedDict, total=False):
    # Required fields (always present)
    source: str              # "CMS" | "AHA" | "FDA" | "USPSTF" | "ACR"
    title: str
    text: str
    relevance_score: float
    contradicts_denial: bool  # does this fight the denial?
    url: str
    # Optional — True only for items retrieved live (not from Pinecone)
    live_fetch: bool


class AgentState(TypedDict):
    # ── Input ──────────────────────────────────────────────
    raw_denial_text: str
    session_id: str
    user_id: str
    patient_context: str

    # ── Node 1: Denial Reader ──────────────────────────────
    denial_info: DenialInfo

    # ── Node 1b: Admin Error Checker ──────────────────────
    skip_admin_check: bool
    admin_error: bool
    admin_error_type: Optional[str]
    admin_explanation: Optional[str]
    admin_suggestion: Optional[str]
    admin_correct_code: Optional[str]

    # ── Node 2: Policy Retriever ───────────────────────────
    # Must run before Node 3: we need the policy code for exact BM25 match,
    # and the payer name to scope semantic search. Node 3's queries are
    # formulated using denial_info + payer_policy_text.
    payer_policy_text: str
    policy_chunks: list[EvidenceItem]
    payer_found: bool
    payer_not_found_message: str

    # ── Node 3: Evidence Retriever ─────────────────────────
    clinical_evidence: list[EvidenceItem]
    fda_evidence: list[EvidenceItem]

    # ── Node 4: Contradiction Finder ──────────────────────
    contradictions: list[dict]
    confidence_score: float
    confidence_reason: str
    appeal_viable: bool

    # ── Node 5a: Appeal Drafter ────────────────────────────
    appeal_letter: str
    citations_used: list[dict]

    # ── Node 5b: Escalation Node ───────────────────────────
    escalated: bool
    escalation_reason: str
    missing_evidence: list[str]

    # ── Node 6: Quality Checker ────────────────────────────
    quality_score: float
    quality_issues: list[str]
    quality_loop_count: int  # prevent infinite loops — max 2

    # ── Streaming ──────────────────────────────────────────
    messages: Annotated[list, add_messages]

    # ── Eval ───────────────────────────────────────────────
    faithfulness_score: Optional[float]
    eval_logged: bool
