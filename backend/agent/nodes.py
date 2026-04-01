"""
7 LangGraph nodes for the Prior Authorization Appeal Agent.

Node execution order:
  denial_reader → policy_retriever → evidence_retriever →
  contradiction_finder → [appeal_drafter | escalation_node] →
  quality_checker (loops back to appeal_drafter if quality < threshold)

Key design choices:
- Haiku for extraction/scoring (speed), Sonnet for reasoning (quality)
- contradicts_denial is computed per-chunk by a separate LLM call, not
  inferred from retrieval score alone — a chunk can be highly relevant
  but still support (not contradict) the denial
- quality_checker loops max 2 times to prevent infinite revision
- escalation_node produces a specific gap list, not a generic "needs review",
  because a vague escalation is as useless as no escalation
"""

import re
import json
import asyncio
import structlog
from typing import Optional
from google import genai
from google.genai import types

from config import settings
from agent.state import AgentState, DenialInfo, EvidenceItem
from agent.phi_scrubber import scrub_phi, scrub_denial_info
from agent.utils import parse_llm_json
from retrieval.hybrid import HybridRetriever
from retrieval.fda_live import fetch_fda_label, fetch_pubmed_abstracts

log = structlog.get_logger()
client = genai.Client(api_key=settings.gemini_api_key)
retriever = HybridRetriever()

# ─────────────────────────────────────────────────────────────────────────────
# Drug-class detection for scoped policy retrieval
# ─────────────────────────────────────────────────────────────────────────────

_DRUG_CLASS_KEYWORDS: dict[str, list[str]] = {
    "psoriasis_biologic": [
        "ustekinumab", "stelara", "secukinumab", "cosentyx",
        "ixekizumab", "taltz", "guselkumab", "tremfya",
        "risankizumab", "skyrizi", "brodalumab", "siliq",
    ],
    "biologic_dmard": [
        "adalimumab", "humira", "infliximab", "remicade", "etanercept", "enbrel",
        "abatacept", "orencia", "tocilizumab", "actemra", "sarilumab", "kevzara",
        "certolizumab", "cimzia", "golimumab", "simponi", "baricitinib", "olumiant",
        "tofacitinib", "xeljanz", "upadacitinib", "rinvoq",
    ],
    "glp1": [
        "semaglutide", "ozempic", "wegovy", "rybelsus", "liraglutide", "victoza",
        "saxenda", "dulaglutide", "trulicity", "exenatide", "byetta", "bydureon",
        "tirzepatide", "mounjaro", "zepbound",
    ],
    "ms_dmt": [
        "ocrelizumab", "ocrevus", "natalizumab", "tysabri", "fingolimod", "gilenya",
        "siponimod", "mayzent", "ofatumumab", "kesimpta", "alemtuzumab", "lemtrada",
        "dimethyl fumarate", "tecfidera", "interferon beta", "avonex", "rebif",
        "cladribine", "mavenclad",
    ],
    "oncology_immunotherapy": [
        "pembrolizumab", "keytruda", "nivolumab", "opdivo",
        "atezolizumab", "tecentriq", "durvalumab", "imfinzi",
        "ipilimumab", "yervoy", "avelumab", "bavencio",
    ],
    "sglt2": [
        "empagliflozin", "jardiance", "dapagliflozin", "farxiga",
        "canagliflozin", "invokana", "ertugliflozin", "steglatro",
    ],
    "ad_biologic": [
        "dupilumab", "dupixent", "tralokinumab", "adbry",
        "lebrikizumab", "ebglyss",
    ],
}

# Clinical evidence sources — excludes PAYER to prevent policy docs from
# appearing in the "what guidelines say" evidence panel
_CLINICAL_SOURCES = ["FDA", "GUIDELINES", "USPSTF", "ASCO", "ACR", "AHA", "ADA", "AAN"]
_CLINICAL_FILTER = {"source": {"$in": _CLINICAL_SOURCES}}


def _detect_drug_class(drug_name: str) -> Optional[str]:
    """Map a drug name to its coverage policy class using keyword matching."""
    drug_lower = drug_name.lower()
    for drug_class, keywords in _DRUG_CLASS_KEYWORDS.items():
        if any(kw in drug_lower for kw in keywords):
            return drug_class
    return None


# Brand name → generic name (Pinecone 'drug' field value).
# Pinecone indexes policies by generic drug name (lowercase).
_BRAND_TO_GENERIC: dict[str, str] = {
    "dupixent": "dupilumab", "adbry": "tralokinumab", "ebglyss": "lebrikizumab",
    "humira": "adalimumab", "remicade": "infliximab", "enbrel": "etanercept",
    "orencia": "abatacept", "actemra": "tocilizumab", "kevzara": "sarilumab",
    "cimzia": "certolizumab", "simponi": "golimumab", "olumiant": "baricitinib",
    "xeljanz": "tofacitinib", "rinvoq": "upadacitinib",
    "stelara": "ustekinumab", "cosentyx": "secukinumab", "taltz": "ixekizumab",
    "tremfya": "guselkumab", "skyrizi": "risankizumab", "siliq": "brodalumab",
    "ozempic": "semaglutide", "wegovy": "semaglutide", "rybelsus": "semaglutide",
    "victoza": "liraglutide", "saxenda": "liraglutide", "trulicity": "dulaglutide",
    "byetta": "exenatide", "bydureon": "exenatide",
    "mounjaro": "tirzepatide", "zepbound": "tirzepatide",
    "ocrevus": "ocrelizumab", "tysabri": "natalizumab", "gilenya": "fingolimod",
    "mayzent": "siponimod", "kesimpta": "ofatumumab", "lemtrada": "alemtuzumab",
    "tecfidera": "dimethyl fumarate", "mavenclad": "cladribine",
    "keytruda": "pembrolizumab", "opdivo": "nivolumab", "tecentriq": "atezolizumab",
    "imfinzi": "durvalumab", "yervoy": "ipilimumab", "bavencio": "avelumab",
    "jardiance": "empagliflozin", "farxiga": "dapagliflozin",
    "invokana": "canagliflozin", "steglatro": "ertugliflozin",
}


def _canonical_drug_name(drug_name: str) -> Optional[str]:
    """
    Return the canonical generic drug name used as the Pinecone 'drug' field value.
    Maps brand names to generics; returns the lowercased name for known generics.
    Returns None if the drug name is unknown or too generic to filter on.
    """
    if not drug_name or drug_name.lower() in ("unknown", ""):
        return None
    drug_lower = drug_name.lower().strip()
    # Check brand→generic map first
    for brand, generic in _BRAND_TO_GENERIC.items():
        if brand in drug_lower:
            return generic
    # If the name itself appears as a generic in any keyword list, use it directly
    for keywords in _DRUG_CLASS_KEYWORDS.values():
        if any(kw == drug_lower for kw in keywords):
            return drug_lower
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Regex fallbacks for denial_reader (used when LLM returns incomplete JSON)
# ─────────────────────────────────────────────────────────────────────────────

KNOWN_PAYERS = [
    "BlueCross BlueShield", "Blue Cross Blue Shield",
    "Blue Cross", "BlueShield",
    "Aetna", "CVS Aetna",
    "UnitedHealthcare", "United Healthcare", "UHC",
    "Cigna", "Cigna Healthcare",
    "Humana",
    "Anthem", "Anthem Blue Cross",
    "Kaiser", "Kaiser Permanente",
    "Molina", "Molina Healthcare",
    "Centene", "WellCare",
    "Medicare", "Medicaid",
    "Highmark",
    "BCBS", "HCSC",
    "Elevance", "Elevance Health",
    "CVS Health", "Aetna CVS",
]


def extract_payer_from_text(text: str) -> Optional[str]:
    for payer in KNOWN_PAYERS:
        if payer.lower() in text.lower():
            return payer
    return None


def extract_drug_from_text(text: str) -> Optional[str]:
    patterns = [
        r'(?:prior authorization|authorization|coverage)\s+for\s+([a-zA-Z]+(?:\s+\([A-Za-z-]+\))?)\s+\d+',
        r'(?:prior authorization|authorization|coverage)\s+for\s+([a-zA-Z-]+\s+\([A-Za-z-]+\))',
        r'denying\s+(?:prior authorization\s+)?for\s+([a-zA-Z-]+(?:\s+\([A-Za-z-]+\))?)',
        r'request\s+for\s+([a-zA-Z-]+(?:\s+\([A-Za-z-]+\))?)\s+\d+mg',
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def extract_policy_from_text(text: str) -> Optional[str]:
    # Only match codes that contain hyphens and digits — e.g. PULM-BIO-2024-03.
    # The word "Policy" must appear immediately before the code (with optional
    # "number"), so "under Pulmonology Policy PULM-BIO-2024-03" captures the
    # code not the condition name.
    pattern = re.compile(
        r'[Pp]olicy\s+(?:number\s+)?([A-Z][A-Z0-9]{1,10}-[A-Z0-9][A-Z0-9\-]{2,20})',
        re.IGNORECASE,
    )
    m = pattern.search(text)
    if m:
        code = m.group(1)
        if "-" in code and any(c.isdigit() for c in code):
            return code
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Node 1: Denial Reader
# ─────────────────────────────────────────────────────────────────────────────

async def denial_reader(state: AgentState) -> dict:
    """
    Extract structured denial info from raw text.
    Uses Haiku — this is pure extraction, no reasoning needed.
    The output (policy_code, payer, drug) drives ALL subsequent retrieval.
    """
    log.info("node.start", node="denial_reader", session_id=state["session_id"])

    # PHI scrub before sending to external LLM
    scrubbed_text = scrub_phi(state["raw_denial_text"])

    response = await client.aio.models.generate_content(
        model=settings.model_fast,
        contents=scrubbed_text,
        config=types.GenerateContentConfig(
            max_output_tokens=512,
            temperature=0,
            system_instruction="""You are a medical billing specialist. Extract structured information from this
insurance denial letter. Output JSON only, no markdown fences:
{
  "drug_or_procedure": "exact name of what was denied",
  "denial_reason": "the specific reason given for denial",
  "policy_code": "the policy section number cited (e.g. 4.2.1b), or 'unknown'",
  "payer": "insurance company name",
  "patient_id": "patient ID if present, else 'unknown'",
  "claim_id": "claim ID if present, else 'unknown'"
}"""
        )
    )

    denial_info: DenialInfo = parse_llm_json(
        response.text,
        fallback={
            "drug_or_procedure": "unknown",
            "denial_reason": "not specified",
            "policy_code": "unknown",
            "payer": "unknown",
            "patient_id": "unknown",
            "claim_id": "unknown",
            "is_admin_error": False,
        },
    )
    # Scrub any PHI the LLM extracted (patient_id, claim_id)
    denial_info = scrub_denial_info(denial_info)

    # Regex fallbacks: recover fields the LLM failed to extract from raw text
    denial_text = state["raw_denial_text"]
    if not denial_info.get("payer") or denial_info["payer"] in ("unknown", "", None):
        fallback = extract_payer_from_text(denial_text)
        if fallback:
            denial_info["payer"] = fallback
            log.info("denial_reader.payer_fallback", payer=fallback)

    if not denial_info.get("drug_or_procedure") or \
            denial_info["drug_or_procedure"] in ("unknown", "", None):
        fallback = extract_drug_from_text(denial_text)
        if fallback:
            denial_info["drug_or_procedure"] = fallback
            log.info("denial_reader.drug_fallback", drug=fallback)

    if not denial_info.get("policy_code") or \
            denial_info["policy_code"] in ("unknown", "", None):
        fallback = extract_policy_from_text(denial_text)
        if fallback:
            denial_info["policy_code"] = fallback
            log.info("denial_reader.policy_fallback", policy=fallback)

    # Enforce all required keys always present (partial parse may omit fields)
    denial_info = {
        "drug_or_procedure": denial_info.get("drug_or_procedure", "unknown"),
        "denial_reason": denial_info.get("denial_reason", ""),
        "policy_code": denial_info.get("policy_code", "unknown"),
        "payer": denial_info.get("payer", "unknown"),
        "patient_id": denial_info.get("patient_id", "unknown"),
        "claim_id": denial_info.get("claim_id", "unknown"),
        "is_admin_error": denial_info.get("is_admin_error", False),
    }
    log.info("node.done", node="denial_reader", denial_info=denial_info)
    return {"denial_info": denial_info}


# ─────────────────────────────────────────────────────────────────────────────
# Node 1b: Admin Error Checker
# ─────────────────────────────────────────────────────────────────────────────

_CODE_MISMATCH_PATTERN = re.compile(
    r'diagnosis\s+code\s+([A-Z]\d+\.?\d*)\s+'
    r'(?:\([^)]+\)\s+)?is\s+not\s+(?:a\s+)?covered',
    re.IGNORECASE,
)
_ICD_CODE_PATTERN = re.compile(
    r'([A-Z]\d+(?:\.\d+)?(?:-[A-Z]?\d+(?:\.\d+)?)?)',
)


def _quick_admin_check(denial_text: str) -> Optional[dict]:
    """
    Pre-LLM regex check for explicit ICD-10 mismatch language.

    If the denial letter itself says "diagnosis code X is not a covered indication"
    AND lists the correct alternatives, this is always an admin error — no LLM needed.
    """
    match = _CODE_MISMATCH_PATTERN.search(denial_text)
    if not match:
        return None

    wrong_code = match.group(1)

    # Extract all ICD-like codes from the full denial text
    all_codes = _ICD_CODE_PATTERN.findall(denial_text)
    # Filter out the wrong code and deduplicate
    alternatives = list(dict.fromkeys(c for c in all_codes if c != wrong_code))

    return {
        "is_admin_error": True,
        "error_type": "icd10_mismatch",
        "explanation": (
            f"Denial explicitly states diagnosis code {wrong_code} "
            "is not a covered indication for the requested drug."
        ),
        "suggested_fix": (
            f"Change diagnosis code from {wrong_code} to the correct code for "
            f"the patient's actual diagnosis. Covered codes per denial: "
            f"{', '.join(alternatives[:5]) if alternatives else 'see denial letter'}"
        ),
        "correct_code": alternatives[0] if alternatives else None,
        "confidence": 0.95,
    }


async def admin_error_checker(state: AgentState) -> dict:
    """
    Detect administrative errors before running the full clinical pipeline.

    Two-pass approach:
    1. Quick regex check for explicit ICD-10 mismatch language (instant, 100% reliable)
    2. LLM check for subtler admin errors (slower, requires reasoning)
    """
    log.info("node.start", node="admin_error_checker", session_id=state["session_id"])

    # ── Pass 1: Quick regex check for explicit code mismatch ────────────
    if not state.get("skip_admin_check", False):
        quick_result = _quick_admin_check(state["raw_denial_text"])
        if quick_result and quick_result.get("confidence", 0) >= 0.90:
            log.info("admin_error.quick_match",
                     error_type=quick_result["error_type"],
                     wrong_code=quick_result.get("correct_code"))
            return {
                "admin_error": True,
                "admin_error_type": quick_result["error_type"],
                "admin_explanation": quick_result["explanation"],
                "admin_suggestion": quick_result["suggested_fix"],
                "admin_correct_code": quick_result.get("correct_code"),
            }

    # ── Pass 2: LLM check for subtler admin errors ─────────────────────
    # PHI scrub before sending to external LLM
    scrubbed_text = scrub_phi(state["raw_denial_text"])

    response = await client.aio.models.generate_content(
        model=settings.model_reasoning,
        contents=scrubbed_text,
        config=types.GenerateContentConfig(
            max_output_tokens=600,
            temperature=0,
            system_instruction="""You are a medical billing specialist with deep knowledge of ICD-10 codes and FDA-approved drug indications.

Analyze this denial and determine if it was caused by an administrative or coding error.

━━ PATTERN — EXPLICIT CODE MISMATCH IN DENIAL ━━

If the denial letter itself states that a submitted code is not a covered indication AND
lists what the covered codes are, this is ALWAYS an administrative ICD-10 mismatch error.

Look for language like:
- "diagnosis code X is not a covered indication"
- "submitted code X does not match covered indications"
- "X is not approved under this policy"
- "covered indications include Y, Z but not X"

When this pattern is found:
  is_admin_error: true
  error_type: "icd10_mismatch"
  confidence: 0.95
  suggested_fix: "Change diagnosis code from [wrong code] to one of the covered codes listed in the denial: [list them]"
  correct_code: most likely correct code based on the drug and listed alternatives

━━ ICD-10 MISMATCH RULES ━━

For biologic DMARDs (adalimumab/Humira, infliximab/Remicade, etanercept/Enbrel, tocilizumab/Actemra, abatacept/Orencia):
  COVERED codes: M05.x (seropositive RA), M06.x (seronegative RA), M45.x (ankylosing spondylitis),
    L40.5x (psoriatic arthritis), K50.x/K51.x (Crohn's/UC — for some agents), L40.x (plaque psoriasis — for some)
  WRONG codes (flag as mismatch): M35.xx (Sjogren/overlap syndromes), M32.xx (lupus), M79.x (soft tissue),
    M54.x (dorsalgia/low back pain), M08.x (juvenile idiopathic arthritis — only specific agents approved),
    any non-rheumatologic code

For GLP-1 agonists (semaglutide/Ozempic/Wegovy, liraglutide/Victoza/Saxenda, dulaglutide/Trulicity):
  COVERED: E11.x (type 2 DM), E66.x (obesity — for weight-indicated formulations)
  WRONG: E10.x (type 1 DM), non-metabolic codes

For MS biologics (ocrelizumab/Ocrevus, natalizumab/Tysabri, fingolimod/Gilenya):
  COVERED: G35 (MS), G36.x (NMO spectrum)
  WRONG: Any non-neurologic or non-demyelinating code

━━ OTHER ADMIN ERRORS ━━

- OUT OF NETWORK: denial mentions provider/facility not in network
- DUPLICATE: PA already active for same drug
- EXPIRED PA: wrong or expired authorization number
- WRONG MODIFIER: billing modifier error
- PLAN MISMATCH: not covered under this specific plan (not a clinical issue)

━━ WHAT IS NOT AN ADMIN ERROR ━━

Genuine clinical denials look like:
- "insufficient step therapy documentation"
- "DMARD failure not documented"
- "medical necessity criteria not met" without a specific code mismatch
- "frequency/quantity exceeds policy limits"
These are clinical disputes — do NOT flag as admin errors.

Output JSON only:
{
  "is_admin_error": true,
  "error_type": "icd10_mismatch|out_of_network|duplicate|expired_pa|missing_modifier|plan_mismatch|null",
  "explanation": "specific explanation of what is wrong",
  "suggested_fix": "exact actionable correction",
  "correct_code": "the correct ICD-10 or CPT code if applicable, else null",
  "confidence": 0.0
}"""
        )
    )

    result = parse_llm_json(
        response.text,
        fallback={
            "is_admin_error": False,
            "error_type": None,
            "explanation": "",
            "suggested_fix": None,
            "correct_code": None,
            "confidence": 0.0,
        },
    )

    is_admin = (
        not state.get("skip_admin_check", False)
        and result.get("is_admin_error", False)
        and result.get("confidence", 0) >= 0.80
    )

    log.info("node.done", node="admin_error_checker",
             is_admin_error=is_admin, confidence=result.get("confidence"),
             error_type=result.get("error_type"))
    return {
        "admin_error": is_admin,
        "admin_error_type": result.get("error_type") if is_admin else None,
        "admin_explanation": result.get("explanation") if is_admin else None,
        "admin_suggestion": result.get("suggested_fix") if is_admin else None,
        "admin_correct_code": result.get("correct_code") if is_admin else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Node 2: Policy Retriever
# ─────────────────────────────────────────────────────────────────────────────

async def policy_retriever(state: AgentState) -> dict:
    """
    Retrieve the payer's coverage policy using hybrid search.

    WHY hybrid (BM25 + semantic):
    - Policy codes like "4.2.1b" are opaque strings — semantic search embeds them
      as generic tokens and returns wrong sections. BM25 exact match is critical.
    - The denial reason ("insufficient DMARD failure") needs semantic search
      because the policy may use different wording ("step therapy requirements").

    Two queries run in parallel, results merged via Reciprocal Rank Fusion.
    """
    log.info("node.start", node="policy_retriever", session_id=state["session_id"])
    info = state["denial_info"]

    exact_query = f"{info.get('payer', 'unknown')} policy {info.get('policy_code', 'unknown')} {info.get('drug_or_procedure', 'unknown')}"
    semantic_query = f"{info.get('payer', 'unknown')} coverage criteria {info.get('drug_or_procedure', 'unknown')} {info.get('denial_reason', '')}"

    # Build scoped filter: payer policy source + drug class + payer name.
    # Payer policy docs are indexed with `drug_class`, not `drug`, so filtering
    # on canonical drug name can silently exclude the correct policy.
    drug_class = _detect_drug_class(info.get("drug_or_procedure", ""))
    canonical_drug = _canonical_drug_name(info.get("drug_or_procedure", ""))
    payer_name = info.get("payer", "")

    # Generate payer name variations for partial matching.
    # denial_reader may extract "Anthem" when the chunk is indexed as "Anthem Blue Cross",
    # or extract "Anthem Blue Cross Blue Shield" when indexed as "Anthem Blue Cross".
    # Try progressively shorter prefixes so at least one matches the stored value.
    payer_parts = payer_name.split()
    payer_variations: list[str] = []
    for n in range(len(payer_parts), 0, -1):
        v = " ".join(payer_parts[:n])
        if v not in payer_variations:
            payer_variations.append(v)
    # Also include the first word alone if not already there (e.g. "Anthem")
    if payer_parts and payer_parts[0] not in payer_variations:
        payer_variations.append(payer_parts[0])

    def _build_filter(payer_variant: str) -> dict:
        f: dict = {"source": {"$in": ["PAYER_POLICIES", "PAYER"]}}
        if drug_class:
            f["drug_class"] = {"$eq": drug_class}
        if payer_variant:
            f["payer"] = {"$eq": payer_variant}
        return f

    log.debug("policy_retriever.filter", drug_class=drug_class, canonical_drug=canonical_drug,
              payer=payer_name, variations=payer_variations)

    chunks1, chunks2 = [], []
    matched_variation: Optional[str] = None
    for variation in payer_variations:
        f = _build_filter(variation)
        c1, c2 = await asyncio.gather(
            retriever.search(exact_query, top_k=settings.top_k_policy, metadata_filter=f),
            retriever.search(semantic_query, top_k=settings.top_k_policy, metadata_filter=f),
        )
        if c1 or c2:
            chunks1, chunks2 = c1, c2
            matched_variation = variation
            log.info("policy_retriever.payer_matched", variation=variation)
            break

    # Fallback: if no payer variation matched, drop payer filter and use drug class
    # only so we still surface comparable peer-payer policies rather than nothing.
    if not chunks1 and not chunks2:
        log.warning("policy_retriever.payer_not_found", payer=payer_name,
                    tried=payer_variations, fallback="drug_class_only")
        fallback_filter: dict = {"source": {"$in": ["PAYER_POLICIES", "PAYER"]}}
        if drug_class:
            fallback_filter["drug_class"] = {"$eq": drug_class}
        chunks1, chunks2 = await asyncio.gather(
            retriever.search(exact_query, top_k=settings.top_k_policy, metadata_filter=fallback_filter),
            retriever.search(semantic_query, top_k=settings.top_k_policy, metadata_filter=fallback_filter),
        )

    # Deduplicate and merge
    seen, merged = set(), []
    for chunk in chunks1 + chunks2:
        if chunk["title"] not in seen:
            seen.add(chunk["title"])
            merged.append(chunk)

    # ── Post-retrieval payer filter ─────────────────────────────────────────
    # When the fallback (drug_class-only) fires, it may return policies from
    # the wrong payer.  Filter those out so the frontend never shows them.
    def _payer_matches(chunk: dict, payer: str) -> bool:
        chunk_payer = chunk.get("payer", "") or ""
        chunk_title = chunk.get("title", "").lower()
        chunk_text  = chunk.get("text", "")[:200].lower()
        payer_lower = payer.lower()
        payer_first = payer_lower.split()[0] if payer_lower else ""
        return (
            payer_lower in chunk_payer.lower()
            or payer_lower in chunk_title
            or payer_first in chunk_payer.lower()
            or payer_first in chunk_title
        )

    matching = [c for c in merged if _payer_matches(c, payer_name)]
    payer_found = bool(matching)

    if matching:
        final_chunks = matching[:settings.top_k_policy]
        log.info("policy_retriever.payer_filter", kept=len(final_chunks), dropped=len(merged) - len(matching))
    else:
        # Return empty — let the frontend show a warning instead of wrong policies
        final_chunks = []
        log.warning("policy_retriever.payer_not_in_results", payer=payer_name,
                    candidates=[c.get("payer", "") for c in merged[:5]])

    payer_not_found_message = (
        f"{payer_name} policy not found in database. "
        "Letter drafted using general biologic coverage criteria."
        if not payer_found else ""
    )

    policy_text = "\n\n---\n\n".join(c["text"] for c in final_chunks)
    policy_chunks: list[EvidenceItem] = [
        EvidenceItem(
            source=c.get("source", "PAYER"),
            title=c.get("title", ""),
            text=c.get("text", ""),
            relevance_score=c.get("score", 0.0),
            contradicts_denial=False,  # policy chunks describe requirements, not contradictions
            url=c.get("url", ""),
        )
        for c in final_chunks
    ]

    log.info("node.done", node="policy_retriever",
             chunks_found=len(policy_chunks), payer_found=payer_found)
    return {
        "payer_policy_text": policy_text,
        "policy_chunks": policy_chunks,
        "payer_found": payer_found,
        "payer_not_found_message": payer_not_found_message,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Node 3: Evidence Retriever
# ─────────────────────────────────────────────────────────────────────────────

async def _score_contradicts(chunk_text: str, denial_reason: str) -> bool:
    """
    Per-chunk contradiction scoring via Haiku.

    WHY per-chunk, not per-session:
    A single session may retrieve 7 chunks where 3 support the denial, 2 are
    neutral, and 2 contradict it. Aggregating to a session-level boolean would
    lose the granularity needed to write targeted appeal arguments. The
    contradiction_finder node needs per-chunk truth values to rank arguments.
    """
    response = await client.aio.models.generate_content(
        model=settings.model_fast,
        contents=(
            f"Denial reason: {denial_reason}\n\n"
            f"Evidence: {chunk_text[:800]}\n\n"
            "Does this evidence contradict or argue against the denial reason?"
        ),
        config=types.GenerateContentConfig(
            max_output_tokens=16,
            temperature=0,
            system_instruction="Answer only 'true' or 'false'. No explanation."
        )
    )
    return (response.text or "").strip().lower() == "true"


async def evidence_retriever(state: AgentState) -> dict:
    """
    Three parallel semantic queries targeting different appeal angles:
    1. Clinical guidelines — establishes clinical appropriateness
    2. FDA approval — establishes approved indications
    3. Medical necessity — establishes why this specific patient qualifies

    Each retrieved chunk gets a per-chunk contradicts_denial score (see above).
    """
    log.info("node.start", node="evidence_retriever", session_id=state["session_id"])
    info = state["denial_info"]

    q_guidelines = f"{info.get('drug_or_procedure', 'unknown')} clinical guidelines indications {info.get('denial_reason', '')}"
    # Drug-specific FDA query prevents cross-drug label contamination (e.g. bevacizumab
    # appearing in a semaglutide denial). The denial_reason anchors it further.
    q_fda = f"FDA label {info.get('drug_or_procedure', 'unknown')} approved indications uses {info.get('denial_reason', '')}"
    q_necessity = f"{info.get('denial_reason', '')} medical necessity criteria {info.get('drug_or_procedure', 'unknown')}"

    # _CLINICAL_FILTER restricts guidelines/necessity queries to clinical sources only
    # (FDA, ACR, AHA, USPSTF, ASCO, etc.) — prevents payer policy docs from appearing
    # in the evidence panel's "what guidelines say" column.
    # Queries run sequentially with 500ms gaps to avoid Voyage AI rate limits.
    guidelines_raw = await retriever.search(q_guidelines, top_k=settings.top_k_evidence, metadata_filter=_CLINICAL_FILTER)
    await asyncio.sleep(0.5)
    fda_raw = await retriever.search(q_fda, top_k=4, filter_source="FDA")
    await asyncio.sleep(0.5)
    necessity_raw = await retriever.search(q_necessity, top_k=settings.top_k_evidence, metadata_filter=_CLINICAL_FILTER)

    # Pre-filter chunks that are obviously off-topic (e.g. CSCO breast cancer guidelines
    # appearing in a psoriasis denial). FDA chunks must mention the drug by first word;
    # guideline/necessity chunks are filtered against a cancer-condition blocklist when
    # the denial itself is not oncology-related.
    _CANCER_CONDITIONS = [
        "breast cancer", "lung cancer", "colorectal", "melanoma", "leukemia",
        "lymphoma", "ovarian cancer", "prostate cancer", "pancreatic cancer",
        "gastric cancer", "hepatocellular", "renal cell carcinoma", "bladder cancer",
    ]
    drug_keyword = info.get("drug_or_procedure", "unknown").split()[0].lower()
    is_cancer_denial = any(
        t in info.get("denial_reason", "").lower() or t in info.get("drug_or_procedure", "").lower()
        for t in ["cancer", "oncol", "tumor", "malign", "carcinoma", "sarcoma"]
    )

    # Psoriasis biologics that have no IBD/RA indication — chunks about those conditions
    # are irrelevant when treating psoriasis and should be filtered.
    _PSORIASIS_BIOLOGICS = {
        "ustekinumab", "stelara", "secukinumab", "cosentyx",
        "ixekizumab", "taltz", "guselkumab", "tremfya",
        "risankizumab", "skyrizi",
    }
    _PSORIASIS_IRRELEVANT = [
        "inflammatory bowel disease", "crohn", "ulcerative colitis",
        "abatacept", "orencia", "rheumatoid arthritis",
    ]
    is_psoriasis_drug = any(kw in drug_keyword or kw in info.get("drug_or_procedure", "").lower()
                            for kw in _PSORIASIS_BIOLOGICS)

    def _is_relevant(chunk: dict, source_type: str) -> bool:
        combined = (chunk.get("text", "") + " " + chunk.get("title", "")).lower()
        if source_type == "fda":
            return drug_keyword in combined
        # Drop cancer guidelines when the denial has nothing to do with cancer
        if not is_cancer_denial:
            if any(cond in combined for cond in _CANCER_CONDITIONS):
                return False
        # Drop IBD/RA/abatacept chunks for psoriasis-specific biologics
        # unless the chunk also explicitly mentions psoriasis
        if is_psoriasis_drug:
            if any(term in combined for term in _PSORIASIS_IRRELEVANT):
                return "psoriasis" in combined
        return True

    guidelines_raw = [c for c in guidelines_raw if _is_relevant(c, "guideline")]
    fda_raw = [c for c in fda_raw if _is_relevant(c, "fda")]
    necessity_raw = [c for c in necessity_raw if _is_relevant(c, "guideline")]

    # Score contradicts_denial for each chunk in parallel
    all_clinical_raw = guidelines_raw + necessity_raw
    contradiction_tasks = [
        _score_contradicts(c["text"], info.get("denial_reason", ""))
        for c in all_clinical_raw + fda_raw
    ]
    contradiction_scores = await asyncio.gather(*contradiction_tasks)

    split = len(all_clinical_raw)
    clinical_evidence: list[EvidenceItem] = [
        EvidenceItem(
            source=c.get("source", "GUIDELINES"),
            title=c.get("title", ""),
            text=c.get("text", ""),
            relevance_score=c.get("score", 0.0),
            contradicts_denial=contradiction_scores[i],
            url=c.get("url", ""),
        )
        for i, c in enumerate(all_clinical_raw)
    ]
    fda_evidence: list[EvidenceItem] = [
        EvidenceItem(
            source="FDA",
            title=c.get("title", ""),
            text=c.get("text", ""),
            relevance_score=c.get("score", 0.0),
            contradicts_denial=contradiction_scores[split + i],
            url=c.get("url", ""),
        )
        for i, c in enumerate(fda_raw)
    ]

    # On-demand live fetch when no retrieved chunk actually mentions the drug.
    # Pinecone may return 12 chunks that are all off-topic (e.g. generic biologic
    # guidelines that never name the specific drug). Count-based check is
    # insufficient — we need at least one chunk that contains the drug keyword.
    drug = info.get("drug_or_procedure", "unknown")
    denial_reason = info.get("denial_reason", "")
    drug_keyword = drug.split("(")[0].strip().lower().split()[0] if drug not in ("unknown", "") else ""

    all_clinical = clinical_evidence + fda_evidence
    total_chunks = len(all_clinical)
    relevant_chunks = [
        e for e in all_clinical
        if e.get("source") not in ("PAYER_POLICIES",)
        and drug_keyword
        and (
            drug_keyword in e.get("text", "").lower()
            or drug_keyword in e.get("title", "").lower()
        )
    ]

    if len(relevant_chunks) == 0:
        log.info("evidence_retriever.live_fallback",
                 drug=drug_keyword, total_chunks=total_chunks,
                 reason="no_drug_specific_chunks")

        live_fda = await fetch_fda_label(drug)
        if live_fda:
            live_fda_scores = await asyncio.gather(*[
                _score_contradicts(chunk["text"], info.get("denial_reason", ""))
                for chunk in live_fda
            ])
            live_fda = [
                {**chunk, "contradicts_denial": live_fda_scores[i]}
                for i, chunk in enumerate(live_fda)
            ]
            fda_evidence.extend(live_fda)
            log.info("evidence_retriever.live_added",
                     count=len(live_fda), drug=drug_keyword)

        if len(live_fda) < 2:
            live_pubmed = await fetch_pubmed_abstracts(
                drug, denial_reason, max_results=2
            )
            if live_pubmed:
                live_pubmed_scores = await asyncio.gather(*[
                    _score_contradicts(chunk["text"], info.get("denial_reason", ""))
                    for chunk in live_pubmed
                ])
                live_pubmed = [
                    {**chunk, "contradicts_denial": live_pubmed_scores[i]}
                    for i, chunk in enumerate(live_pubmed)
                ]
                clinical_evidence.extend(live_pubmed)
                log.info("evidence_retriever.live_pubmed_added",
                         count=len(live_pubmed), drug=drug_keyword)

    contradicting = sum(1 for e in clinical_evidence + fda_evidence if e["contradicts_denial"])
    log.info("node.done", node="evidence_retriever",
             evidence_found=len(clinical_evidence) + len(fda_evidence),
             contradicting=contradicting)
    return {"clinical_evidence": clinical_evidence, "fda_evidence": fda_evidence}


# ─────────────────────────────────────────────────────────────────────────────
# Node 4: Contradiction Finder
# ─────────────────────────────────────────────────────────────────────────────

async def contradiction_finder(state: AgentState) -> dict:
    """
    Uses Sonnet (reasoning model) to synthesize contradictions.

    Confidence formula (three weighted factors):
    - evidence_count_score (0.4): number of contradicting evidence items
    - strength_score (0.4): source authority (FDA/CMS > specialty society > PubMed)
    - diversity_score (0.2): independent sources vs same source repeated

    WHY three factors: retrieval score alone conflates relevance with authority.
    A highly relevant but weak source (blog post) should score lower than a
    moderately relevant authoritative source (FDA label). Diversity prevents
    one strong source from inflating the score — an appeal needs corroboration.
    """
    log.info("node.start", node="contradiction_finder", session_id=state["session_id"])
    info = state["denial_info"]
    patient_context = scrub_phi(state.get("patient_context", "").strip())

    all_evidence = state.get("clinical_evidence", []) + state.get("fda_evidence", [])
    contradicting = [e for e in all_evidence if e.get("contradicts_denial")]
    policy_text = state.get("payer_policy_text", "No policy retrieved.")

    evidence_summary = "\n".join([
        f"[{e['source']}] {e['title']}: {e['text'][:300]}"
        for e in all_evidence[:12]
    ])

    patient_context_block = (
        f"\nPATIENT CLINICAL CONTEXT:\n{patient_context}\n"
        if patient_context else
        "\nPATIENT CLINICAL CONTEXT: None provided.\n"
    )

    system = """You are a medical appeals specialist analyzing whether clinical evidence and patient history support overturning a PA denial.

Evaluate TWO dimensions:
1. Does the retrieved clinical evidence contradict the payer's policy requirements?
2. Does the patient's clinical context satisfy the payer's step therapy or documentation requirements?

Confidence scoring rules:
- BOTH evidence contradicts policy AND patient context satisfies requirements → 0.80-0.95
- Evidence contradicts policy but patient context is missing or incomplete → 0.50-0.72
- Patient context satisfies requirements but evidence is weak → 0.45-0.60
- Neither evidence nor patient context supports appeal → 0.10-0.40

For each contradiction, explicitly evaluate whether the patient's documented history satisfies that specific policy requirement.

SCORING GUIDANCE — apply these when patient_context is present with specific clinical details:

HIGH confidence boosters (each adds 0.10-0.15 to the base score):
+ Patient tried each required therapy for minimum documented duration
+ Discontinuation was due to documented toxicity (lab values, objective findings) not just preference
+ Lab values provided (transaminases, creatinine, BP, ESR, CRP, etc.)
+ Disease severity scores provided (PASI, DAS28, EDSS, BSA, DLQI)
+ FDA label directly supports the exact indication being requested
+ Multiple independent physicians or guidelines recommend the drug

CONFIDENCE FLOOR RULES:
- Patient context satisfies ALL step therapy requirements with documented toxicity → minimum 0.80
- FDA label directly approves the exact indication AND patient meets FDA criteria → minimum 0.75
- Payer policy not found in database but clinical case is strong → do not penalize below 0.70

OUTPUT CONSTRAINTS (required to avoid truncation):
- Return at most 5 contradictions, prioritized by strength.
- Keep every string value under 100 characters. Do not write paragraphs inside JSON fields.
- The appeal_drafter will expand on these points — be concise here."""

    prompt = f"""Payer: {info.get('payer', 'unknown')}
Drug/Procedure: {info.get('drug_or_procedure', 'unknown')}
Denial reason: {info.get('denial_reason', '')}
Policy code: {info.get('policy_code', 'unknown')}

PAYER POLICY TEXT:
{policy_text[:1500]}
{patient_context_block}
RETRIEVED CLINICAL EVIDENCE ({len(contradicting)} of {len(all_evidence)} chunks contradict denial):
{evidence_summary}

Identify contradictions between the payer policy and the combination of clinical evidence + patient history.
Output JSON only:
{{
  "contradictions": [
    {{
      "payer_says": "exact requirement from policy",
      "evidence_says": "what guidelines/FDA say instead",
      "patient_satisfies": true,
      "how_patient_satisfies": "specific detail from patient context that meets this requirement",
      "source": "source name",
      "strength": "strong|moderate|weak"
    }}
  ],
  "confidence_score": 0.0,
  "confidence_reason": "specific explanation referencing both evidence and patient context",
  "appeal_viable": true
}}

Confidence weight: evidence authority (FDA/CMS=1.0, ACR/AHA/ADA=0.8) × 0.4 + patient context completeness × 0.4 + source diversity × 0.2."""

    response = await client.aio.models.generate_content(
        model=settings.model_reasoning,
        contents=prompt,
        config=types.GenerateContentConfig(
            max_output_tokens=4096,
            temperature=0,
            system_instruction=system
        )
    )

    result = parse_llm_json(
        response.text,
        fallback={
            "confidence_score": 0.5,
            "confidence_reason": "Could not fully analyze — using moderate confidence",
            "contradictions": [],
            "appeal_viable": True,
        },
    )
    contradictions = result.get("contradictions", [])
    log.info("node.done", node="contradiction_finder",
             confidence=result.get("confidence_score"),
             contradictions=len(contradictions))

    # Build a set of source names that the LLM identified as contradicting
    contradicting_sources = {
        c.get("source", "").strip().upper()
        for c in contradictions
        if c.get("source")
    }

    def _writeback(items: list) -> list:
        updated = []
        for e in items:
            src = (e.get("source") or "").strip().upper()
            title = (e.get("title") or "").upper()
            hit = (
                src in contradicting_sources
                or any(cs in title for cs in contradicting_sources)
                or any(cs in src for cs in contradicting_sources)
            )
            if hit and not e.get("contradicts_denial"):
                e = {**e, "contradicts_denial": True}
            updated.append(e)
        return updated

    updated_clinical = _writeback(state.get("clinical_evidence") or [])
    updated_fda      = _writeback(state.get("fda_evidence") or [])

    written_back = sum(1 for e in updated_clinical + updated_fda if e.get("contradicts_denial"))
    log.info("contradiction_finder.writeback",
             contradicting_sources=list(contradicting_sources),
             written_back=written_back)

    return {
        "clinical_evidence": updated_clinical,
        "fda_evidence": updated_fda,
        "contradictions": contradictions,
        "confidence_score": result.get("confidence_score", 0.0),
        "confidence_reason": result.get("confidence_reason", ""),
        "appeal_viable": result.get("appeal_viable", False),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Node 5a: Appeal Drafter
# ─────────────────────────────────────────────────────────────────────────────

async def appeal_drafter(state: AgentState) -> dict:
    """
    Draft the complete appeal letter grounded in retrieved evidence.
    Uses Sonnet for quality prose generation.

    When called after quality_checker loop-back, quality_issues are injected
    as additional context so the model fixes specific problems, not rewrites blindly.
    """
    log.info("node.start", node="appeal_drafter", session_id=state["session_id"])
    info = state["denial_info"]
    all_evidence = state.get("clinical_evidence", []) + state.get("fda_evidence", [])

    evidence_block = "\n".join([
        f"[{e['source']}] {e['title']}: {e['text'][:400]}"
        for e in all_evidence[:10]
    ])
    contradictions_block = "\n".join([
        f"- {c.get('payer_says', '')} → {c.get('evidence_says', '')} [{c.get('source', '')}]"
        for c in state.get("contradictions", [])
    ])

    quality_context = ""
    if state.get("quality_issues"):
        quality_context = (
            "\n\nPREVIOUS DRAFT HAD THESE ISSUES — FIX THEM:\n" +
            "\n".join(f"- {issue}" for issue in state["quality_issues"])
        )

    partial_flag = ""
    if state.get("confidence_score", 1.0) < settings.confidence_threshold_high:
        partial_flag = "\nNOTE: Evidence is partial. Draft only what is strongly supported. Omit sections where evidence is insufficient rather than adding placeholder text."

    patient_context_block = ""
    scrubbed_patient_ctx = scrub_phi(state.get("patient_context", "").strip())
    if scrubbed_patient_ctx:
        patient_context_block = (
            "\n\nPATIENT-SPECIFIC CONTEXT PROVIDED BY PHYSICIAN:\n"
            + scrubbed_patient_ctx
            + "\n\nIncorporate this context into the letter where relevant. "
            "Reference specific prior treatments and lab values by name."
        )

    system = """You are an expert medical appeal writer. Write a formal prior authorization
appeal letter based ONLY on the provided evidence.

Rules:
1. Every factual claim must be cited. Two citation formats are valid:
   a) Retrieved evidence — use the exact source title from the context chunks:
      CORRECT: [FDA Label: Ustekinumab-aekn]
      CORRECT: [ACR RA Treatment Guidelines 2023]
      WRONG:   [FDA Label: Ustekinumab-aekn, Section 1]
      WRONG:   [FDA Label: Ustekinumab-aekn, p.3]
      Never add section numbers, page numbers, or sub-references not in the chunk metadata.
   b) Physician-provided patient context — cite as [Per treating physician]:
      CORRECT: 'PASI score 14.2, BSA 22%, DLQI 18 [Per treating physician]'
      CORRECT: 'Methotrexate 20mg weekly July 2022, discontinued February 2023 due to
                pneumonitis [Per treating physician]'
      Use [Per treating physician] for all clinical values, lab results, dates, prior
      treatment details, and disease scores that came from the patient context block.
2. When the denial lists drug options with "or" (e.g. "methotrexate, cyclosporine, or
   acitretin"), treat this as an OR list — the patient must satisfy ANY combination of
   the required number, not ALL items on the list. Never argue against a drug that was
   listed as an option but not specifically required. Only argue against requirements
   that are genuinely unmet.
3. Quote the payer's own policy language, then show how the criteria are met
3. Structure: Opening → Clinical Necessity → Policy Compliance → Supporting Evidence → Conclusion
4. Tone: Professional, firm, evidence-based. Not emotional.
5. Length: 400-600 words. Concise and complete — finish every sentence and section.
6. Never make claims not supported by the retrieved evidence or physician-provided patient context.
7. CRITICAL: Never use placeholder text, brackets, or [PHYSICIAN TO CONFIRM] blocks.
   If you cannot verify specific policy language either write around it using what you
   DO know, or omit that claim entirely. The letter must read as complete and professional
   with zero placeholder text of any kind.
8. The letter must end cleanly with a signature block.

The goal: make it impossible for the reviewer to uphold the denial without
contradicting published clinical guidelines."""

    prompt = f"""Drug/Procedure: {info.get('drug_or_procedure', 'unknown')}
Patient ID: {info.get('patient_id', 'unknown')}
Claim ID: {info.get('claim_id', 'unknown')}
Payer: {info.get('payer', 'unknown')}
Policy Code: {info.get('policy_code', 'unknown')}
Denial Reason: {info.get('denial_reason', '')}

PAYER POLICY LANGUAGE:
{state.get('payer_policy_text', '')[:800]}

CONTRADICTIONS FOUND:
{contradictions_block}

SUPPORTING EVIDENCE:
{evidence_block}
{quality_context}{partial_flag}{patient_context_block}

Write the complete appeal letter now. Use this exact structure:

---
Re: Appeal of Prior Authorization Denial
Claim ID: {info.get('claim_id', 'unknown')}
Patient: {info.get('patient_id', 'unknown')}
Drug/Procedure: {info.get('drug_or_procedure', 'unknown')}

Dear Medical Director,

Write a 1-2 sentence opening that identifies the denial under policy {info.get('policy_code', 'unknown')} and states you are appealing on behalf of your patient.

CLINICAL NECESSITY:
Write 2-3 sentences establishing medical necessity, citing specific evidence sources in [SOURCE] brackets.

POLICY COMPLIANCE:
Write 2-3 sentences showing the payer's own criteria are satisfied, quoting exact policy language where available.

SUPPORTING EVIDENCE:
Write 2-3 sentences citing specific contradictions between the denial rationale and published guidelines, with [SOURCE] brackets.

CONCLUSION:
Write 1-2 sentences requesting overturn and stating the specific action requested (approval of {info.get('drug_or_procedure', 'unknown')}).

Sincerely,
Attending Physician
---

Do not add placeholder text in brackets. Fill in every section fully. End the letter cleanly after the signature."""

    response = await client.aio.models.generate_content(
        model=settings.model_reasoning,
        contents=prompt,
        config=types.GenerateContentConfig(
            max_output_tokens=4096,
            temperature=0.3,
            system_instruction=system
        )
    )

    import re

    def _remove_placeholders(text: str) -> str:
        """Strip any placeholder blocks the model emitted despite instructions."""
        text = re.sub(r'\[PHYSICIAN TO CONFIRM:[^\]]*\]', '', text)
        text = re.sub(r'\[ADD:[^\]]*\]', '', text)
        text = re.sub(r'\[INSERT:[^\]]*\]', '', text)
        text = re.sub(r'\[TO CONFIRM:[^\]]*\]', '', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'  +', ' ', text)
        return text.strip()

    letter = _remove_placeholders(response.text or "")

    # Extract citations used
    _skip = {"PHYSICIAN", "SOURCE", "CONCLUSION", "CLINICAL", "POLICY", "SUPPORTING", "EVIDENCE"}
    citations_used = [
        {"source": m, "text": ""}
        for m in set(re.findall(r'\[([A-Z]{2,}[^\]]*)\]', letter))
        if not any(m.startswith(s) for s in _skip)
    ]

    log.info("node.done", node="appeal_drafter", letter_length=len(letter.split()))
    return {"appeal_letter": letter, "citations_used": citations_used}


# ─────────────────────────────────────────────────────────────────────────────
# Node 5b: Escalation Node
# ─────────────────────────────────────────────────────────────────────────────

async def escalation_node(state: AgentState) -> dict:
    """
    When confidence < 0.40, generate a specific gap list instead of a weak letter.

    WHY specific gaps instead of generic escalation:
    "Needs physician review" tells the physician nothing actionable.
    "Provide documentation of DMARD trials (drug name, dates, duration,
    discontinuation reason)" tells them exactly what to gather. The specificity
    comes from comparing what we DID retrieve against what the policy requires.
    """
    log.info("node.start", node="escalation_node", session_id=state["session_id"])
    info = state["denial_info"]
    all_evidence = state.get("clinical_evidence", []) + state.get("fda_evidence", [])

    found_items = [e for e in all_evidence if e.get("contradicts_denial")]
    not_found = [e for e in all_evidence if not e.get("contradicts_denial")]

    found_summary = "\n".join(f"✓ {e['title']} [{e['source']}]" for e in found_items[:5])
    if not found_summary:
        found_summary = "✗ No supporting evidence found in current knowledge base."

    prompt = f"""Drug: {info.get('drug_or_procedure', 'unknown')}
Payer: {info.get('payer', 'unknown')}
Denial reason: {info.get('denial_reason', '')}
Policy code: {info.get('policy_code', 'unknown')}

Evidence found that supports appeal:
{found_summary}

Policy requires: {state.get('payer_policy_text', '')[:600]}

Generate a specific escalation notice listing:
1. What evidence WAS found
2. What SPECIFIC documents/data the physician must provide
3. WHY each item is needed (which policy requirement it satisfies)

Output JSON only:
{{
  "escalation_reason": "one-sentence summary of why auto-draft failed",
  "missing_evidence": [
    "Specific item 1 — what it is and why needed",
    "Specific item 2 — what it is and why needed"
  ],
  "found_summary": "what was found"
}}"""

    response = await client.aio.models.generate_content(
        model=settings.model_fast,
        contents=prompt,
        config=types.GenerateContentConfig(
            max_output_tokens=800,
            temperature=0
        )
    )

    result = parse_llm_json(
        response.text,
        fallback={
            "escalation_reason": "Insufficient evidence to auto-draft appeal",
            "missing_evidence": ["Physician review required"],
            "found_summary": "",
        },
    )
    log.info("node.done", node="escalation_node", escalated=True)
    return {
        "escalated": True,
        "escalation_reason": result.get("escalation_reason", ""),
        "missing_evidence": result.get("missing_evidence", []),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Node 6: Quality Checker
# ─────────────────────────────────────────────────────────────────────────────

async def quality_checker(state: AgentState) -> dict:
    """
    Review the drafted letter against the retrieved evidence.

    WHY this node exists: The appeal_drafter may hallucinate citations or
    miss addressing the specific denial reason. The quality_checker cross-checks
    every clinical claim against the evidence_items list and flags discrepancies.

    Max 2 loops (quality_loop_count) to prevent infinite revision cycles.
    The loop count is tracked in state — routing logic reads it.
    """
    log.info("node.start", node="quality_checker", session_id=state["session_id"])
    letter = state.get("appeal_letter", "")
    all_evidence = state.get("clinical_evidence", []) + state.get("fda_evidence", [])
    evidence_titles = [e["title"] for e in all_evidence]
    patient_context = scrub_phi(state.get("patient_context", "").strip())

    physician_context_block = (
        f"\nPHYSICIAN-PROVIDED PATIENT CONTEXT (verified ground truth — do NOT flag these as hallucinations):\n{patient_context}\n"
        if patient_context else
        "\nPHYSICIAN-PROVIDED PATIENT CONTEXT: None provided.\n"
    )

    prompt = f"""Review this appeal letter for quality. Check:
1. Every clinical claim has a citation in [brackets]
2. Payer's policy language is quoted accurately (not paraphrased inaccurately)
3. Letter addresses the specific denial reason: "{state['denial_info']['denial_reason']}"
4. No hallucinated facts — cross-check against the evidence titles AND physician context below
5. Professional tone throughout
6. OR requirements are not misrepresented as AND requirements — if the denial says
   "drug A, drug B, or drug C", the letter must not imply all three were required or
   argue against drugs that were only listed as options

IMPORTANT: Two sources of ground truth exist. Only flag a claim as hallucinated if it
cannot be traced to EITHER source:
  A) The physician-provided patient context below (demographics, lab values, prior
     treatments, dates — anything the physician typed is verified and must not be flagged)
  B) The retrieved evidence chunk titles listed below
{physician_context_block}
Available evidence sources (only these exist):
{chr(10).join(f"- {t}" for t in evidence_titles[:15])}

Letter to review:
{letter[:5000]}

Output JSON only (keep quality_issues to max 3 short strings):
{{
  "quality_score": 0.0,
  "quality_issues": ["issue 1", "issue 2"]
}}

Score 0.0-1.0. Above 0.85 = excellent. Below 0.70 = needs revision."""

    response = await client.aio.models.generate_content(
        model=settings.model_fast,
        contents=prompt,
        config=types.GenerateContentConfig(
            max_output_tokens=1024,
            temperature=0
        )
    )

    result = parse_llm_json(
        response.text,
        fallback={"quality_score": 0.7, "quality_issues": ["Review letter manually before submitting"]},
    )
    loop_count = state.get("quality_loop_count", 0)

    log.info("node.done", node="quality_checker",
             quality_score=result.get("quality_score"),
             loop_count=loop_count,
             issues=result.get("quality_issues"))

    return {
        "quality_score": result.get("quality_score", 0.0),
        "quality_issues": result.get("quality_issues", []),
        "quality_loop_count": loop_count + 1,
    }
