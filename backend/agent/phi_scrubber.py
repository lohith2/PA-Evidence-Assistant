"""
HIPAA Safe Harbor PHI De-Identification Module.

Strips Protected Health Information (PHI) from text before it is sent to
external LLM APIs, stored in the database, or returned via API responses.

Covers the 18 HIPAA Safe Harbor identifier categories using regex-based
pattern matching. Uses contextual patterns for names (e.g. "Patient: John Smith")
rather than NER to avoid heavy dependencies.

Design choice: Treatment dates like "methotrexate started Jan 2023" are
preserved because they are clinically essential for appeal drafting. Only
DOB-context dates are stripped.

Usage:
    from agent.phi_scrubber import scrub_phi
    clean_text = scrub_phi(raw_denial_text)
"""

import re
import structlog
from typing import List, Tuple

log = structlog.get_logger()


# ─────────────────────────────────────────────────────────────────────────────
# Pattern definitions: (compiled_regex, replacement_tag)
# Order matters — more specific patterns should come before generic ones.
# ─────────────────────────────────────────────────────────────────────────────

def _build_patterns() -> List[Tuple[re.Pattern, str]]:
    """Build and compile all PHI detection patterns."""
    patterns: List[Tuple[str, str, int]] = []

    # ── 0. ZIP+4 (must come BEFORE SSN to avoid false match) ─────────────
    # Standalone ZIP+4 (the +4 extension is the signal it's a ZIP)
    patterns.append((
        r'\b\d{5}-\d{4}\b',
        '[ZIP_REDACTED]',
        0,
    ))

    # ── 1. SSN ────────────────────────────────────────────────────────────
    # Matches XXX-XX-XXXX only (strict 3-2-4 grouping with separators)
    patterns.append((
        r'\b\d{3}[-\s]\d{2}[-\s]\d{4}\b',
        '[SSN_REDACTED]',
        0,
    ))

    # ── 2. Email addresses ────────────────────────────────────────────────
    patterns.append((
        r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b',
        '[EMAIL_REDACTED]',
        0,
    ))

    # ── 3. IP addresses ──────────────────────────────────────────────────
    patterns.append((
        r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
        '[IP_REDACTED]',
        0,
    ))

    # ── 4. Phone / fax numbers ────────────────────────────────────────────
    # US formats: (555) 555-5555, 555-555-5555, 555.555.5555, +1-555-555-5555
    patterns.append((
        r'(?:\+?1[-.\s]?)?(?:\(\d{3}\)|\d{3})[-.\s]?\d{3}[-.\s]?\d{4}\b',
        '[PHONE_REDACTED]',
        0,
    ))

    # ── 5. Dates of birth (contextual — only near DOB/birth keywords) ────
    # Matches: DOB: 01/15/1982, Date of Birth: January 15, 1982, born 1/15/82
    # Does NOT strip treatment dates like "started methotrexate Jan 2023"
    patterns.append((
        r'(?:(?:DOB|D\.O\.B|date\s+of\s+birth|birth\s*date|born)\s*[:=]?\s*)'
        r'(?:\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}'   # MM/DD/YYYY
        r'|(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?'
        r'|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?'
        r'|Dec(?:ember)?)\s+\d{1,2},?\s+\d{4}'       # Month DD, YYYY
        r'|\d{4}[/\-\.]\d{1,2}[/\-\.]\d{1,2})',      # YYYY-MM-DD
        '[DOB_REDACTED]',
        re.IGNORECASE,
    ))

    # ── 6. Ages over 89 (HIPAA requires aggregation to 90+) ──────────────
    patterns.append((
        r'\b(?:age[d]?\s*[:=]?\s*)(?:9\d|1\d{2})\b',
        'age [AGE_REDACTED]',
        re.IGNORECASE,
    ))

    # ── 7. Medical Record Numbers (MRN) ──────────────────────────────────
    # Matches: MRN: 12345678, MRN# 123-456-789, Medical Record: ABC12345
    patterns.append((
        r'(?:MRN|medical\s+record(?:\s+number)?)\s*[#:=]?\s*[A-Za-z0-9\-]{4,15}',
        '[MRN_REDACTED]',
        re.IGNORECASE,
    ))

    # ── 8. Health plan beneficiary numbers ────────────────────────────────
    # [REMOVED] Claim IDs and Patient/Member IDs are administrative references
    # needed for appeals, not PHI. They should not be redacted.

    # ── 9. Account / certificate numbers ─────────────────────────────────
    patterns.append((
        r'(?:account\s*(?:number|#|no\.?)|certificate\s*(?:number|#|no\.?))'
        r'\s*[#:=]?\s*[A-Za-z0-9\-]{4,20}',
        '[ACCOUNT_REDACTED]',
        re.IGNORECASE,
    ))

    # ── 10. Patient names (contextual — near identifiers) ────────────────
    # Matches text after Patient:, Member:, Re:, Dear Mr./Mrs./Ms./Dr.,
    # Name:, Enrollee:, Insured:
    # The name capture is: 2-4 capitalized words following the keyword.
    patterns.append((
        r'(?:Patient(?:\s+Name)?|Member(?:\s+Name)?|Enrollee|Insured|'
        r'(?:Re|RE)\s*:|Dear\s+(?:Mr|Mrs|Ms|Miss|Dr|Prof)\.?)'
        r'\s*[,:=]?\s*'
        r'([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:\s+(?:Jr|Sr|II|III|IV)\.?)?)',
        '[PATIENT_NAME_REDACTED]',
        0,
    ))

    # ── 11. Street addresses ─────────────────────────────────────────────
    # Matches: 123 Main Street, 4567 Elm Ave Apt 5B, PO Box 123
    patterns.append((
        r'\b\d{1,5}\s+[A-Z][a-z]+(?:\s+[A-Z]?[a-z]+)*'
        r'\s+(?:Street|St|Avenue|Ave|Boulevard|Blvd|Drive|Dr|Road|Rd'
        r'|Lane|Ln|Way|Court|Ct|Circle|Cir|Place|Pl|Terrace|Ter)'
        r'\.?(?:\s*(?:,|\.)\s*(?:Apt|Suite|Ste|Unit|#)\s*\w+)?\b',
        '[ADDRESS_REDACTED]',
        re.IGNORECASE,
    ))

    # PO Box
    patterns.append((
        r'\bP\.?\s*O\.?\s*Box\s+\d+\b',
        '[ADDRESS_REDACTED]',
        re.IGNORECASE,
    ))

    # ── 12. ZIP codes ────────────────────────────────────────────────────
    # Full 5-digit or ZIP+4, but only when near address context
    patterns.append((
        r'(?:zip\s*(?:code)?|postal\s*code)\s*[#:=]?\s*\d{5}(?:-\d{4})?\b',
        '[ZIP_REDACTED]',
        re.IGNORECASE,
    ))
    # (standalone ZIP+4 already handled at the top of the pattern list)

    # ── 13. Vehicle / device identifiers (rare in denials) ───────────────
    patterns.append((
        r'(?:VIN|vehicle\s+identification)\s*[#:=]?\s*[A-HJ-NPR-Z0-9]{17}\b',
        '[VEHICLE_ID_REDACTED]',
        re.IGNORECASE,
    ))

    # ── 14. Device serial / identifiers ──────────────────────────────────
    patterns.append((
        r'(?:serial\s*(?:number|#|no\.?)|device\s*(?:ID|#))'
        r'\s*[#:=]?\s*[A-Za-z0-9\-]{6,20}',
        '[DEVICE_ID_REDACTED]',
        re.IGNORECASE,
    ))

    # ── 15. URL / web addresses (may contain patient portals) ────────────
    patterns.append((
        r'https?://[^\s<>"\']+',
        '[URL_REDACTED]',
        0,
    ))

    # Compile all patterns
    return [
        (re.compile(pattern, flags), replacement)
        for pattern, replacement, flags in patterns
    ]


_PATTERNS = _build_patterns()


# ─────────────────────────────────────────────────────────────────────────────
# Standalone patient ID pattern — used separately because it needs special
# handling (used to redact the patient_id extracted by denial_reader)
# ─────────────────────────────────────────────────────────────────────────────

_PATIENT_ID_PATTERN = re.compile(
    r'(?:Patient\s*(?:ID|#|No\.?|Number))\s*[#:=]?\s*([A-Za-z0-9\-]{2,20})',
    re.IGNORECASE,
)


def scrub_phi(text: str) -> str:
    """
    Remove Protected Health Information from text using HIPAA Safe Harbor patterns.

    Replaces PHI with category-tagged placeholders (e.g. [SSN_REDACTED]).
    Preserves clinical content (drug names, doses, lab values, treatment dates).

    Args:
        text: Raw text potentially containing PHI.

    Returns:
        De-identified text with PHI replaced by tagged placeholders.
    """
    if not text or not text.strip():
        return text

    scrubbed = text
    redaction_count = 0

    for pattern, replacement in _PATTERNS:
        new_text = pattern.sub(replacement, scrubbed)
        if new_text != scrubbed:
            # Count how many substitutions were made
            matches = pattern.findall(scrubbed)
            redaction_count += len(matches)
            scrubbed = new_text

    if redaction_count > 0:
        log.info("phi_scrubber.redacted", count=redaction_count)

    return scrubbed


def scrub_patient_id(patient_id: str) -> str:
    """
    Pass-through function for patient_id.
    Patient/Member IDs are administrative references, not PHI.
    """
    if not patient_id or patient_id.lower() in ("unknown", "n/a", "none"):
        return "unknown"
    return patient_id


def scrub_claim_id(claim_id: str) -> str:
    """
    Pass-through function for claim_id.
    Claim IDs are required for processing the appeal.
    """
    if not claim_id or claim_id.lower() in ("unknown", "n/a", "none"):
        return "unknown"
    return claim_id


def scrub_denial_info(info: dict) -> dict:
    """
    Scrub PHI from the extracted denial_info dictionary.
    Preserves clinical fields (drug, denial_reason, policy_code, payer).
    """
    if not info:
        return info

    scrubbed = dict(info)
    scrubbed["patient_id"] = scrub_patient_id(info.get("patient_id", ""))
    scrubbed["claim_id"] = scrub_claim_id(info.get("claim_id", ""))
    # Scrub denial_reason in case it contains patient name references
    scrubbed["denial_reason"] = scrub_phi(info.get("denial_reason", ""))
    return scrubbed
