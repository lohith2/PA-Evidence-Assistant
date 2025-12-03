"""
Comprehensive payer policy documents for prior authorization criteria.

Covers 9 major payers × 6 drug classes = 54 policy documents.
Based on publicly available PA criteria patterns.

Payers: Anthem Blue Cross, Cigna, Humana, UnitedHealthcare, Aetna,
        BlueCross BlueShield, Molina, Centene, Kaiser
Drug classes: Psoriasis biologics, RA biologics, GLP-1 agonists,
              MS DMTs, Oncology immunotherapy, SGLT2 inhibitors
"""

import json
from pathlib import Path
import structlog

log = structlog.get_logger()


def _policy(id: str, payer: str, title: str, drug_class: str,
            condition: str, policy_id: str, *, text: str, url: str = "") -> dict:
    """Helper to build a policy document with consistent metadata."""
    return {
        "id": id,
        "source": "PAYER_POLICIES",
        "title": f"{payer}: {title} — Policy {policy_id}",
        "text": text,
        "url": url,
        "metadata": {
            "payer": payer,
            "drug_class": drug_class,
            "condition": condition,
            "policy_id": policy_id,
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
# PSORIASIS BIOLOGICS
# (ustekinumab, secukinumab, ixekizumab, guselkumab, risankizumab)
# ═══════════════════════════════════════════════════════════════════════════════

_PSORIASIS_POLICIES = [
    _policy(
        "ant_derm_bio_2024", "Anthem Blue Cross",
        "Biologic Agents for Psoriasis", "psoriasis_biologic", "psoriasis", "ANT-DERM-BIO-2024",
        text="""POLICY ANT-DERM-BIO-2024: BIOLOGIC AGENTS FOR MODERATE-TO-SEVERE PLAQUE PSORIASIS
Payer: Anthem Blue Cross

COVERED AGENTS: ustekinumab (Stelara), secukinumab (Cosentyx), ixekizumab (Taltz),
guselkumab (Tremfya), risankizumab (Skyrizi), brodalumab (Siliq)

STEP THERAPY REQUIREMENTS:
1. Documented diagnosis of moderate-to-severe plaque psoriasis: BSA ≥10% OR PASI ≥12 OR DLQI ≥10
2. Must have tried and failed, been intolerant to, or have contraindication to at least ONE of:
   a) Phototherapy (UVB or PUVA) for ≥3 months, OR
   b) Methotrexate at ≥15mg/week for ≥3 months, OR
   c) Cyclosporine at adequate dose for ≥3 months, OR
   d) Acitretin at adequate dose for ≥3 months
3. Failure defined as: <PASI 50 response, documented intolerance, or contraindication

DOCUMENTATION REQUIREMENTS:
- Dermatologist attestation required
- Baseline PASI, BSA, and DLQI scores
- Documentation of prior therapy trials with dates, doses, duration, and reason for discontinuation
- Photography if available

QUANTITY LIMITS:
- Initial authorization: 6 months
- Renewal requires documented PASI 75 response or ≥5-point DLQI improvement
- Ustekinumab: weight-based dosing (45mg if ≤100kg, 90mg if >100kg) q12 weeks after induction

EXCEPTION CRITERIA:
- Step therapy waived for erythrodermic or pustular psoriasis
- Step therapy waived if systemic agents contraindicated (hepatic disease, pregnancy, renal impairment)
- Patients with concomitant psoriatic arthritis may skip to biologic if joint involvement documented""",
    ),
    _policy(
        "cigna_derm_bio_2024", "Cigna",
        "Biologic Agents for Psoriasis", "psoriasis_biologic", "psoriasis", "CIG-DERM-BIO-2024",
        text="""POLICY CIG-DERM-BIO-2024: BIOLOGIC THERAPY FOR PLAQUE PSORIASIS
Payer: Cigna

COVERED AGENTS: ustekinumab (Stelara), secukinumab (Cosentyx), ixekizumab (Taltz),
guselkumab (Tremfya), risankizumab (Skyrizi)

CRITERIA FOR INITIAL AUTHORIZATION:
1. Moderate-to-severe plaque psoriasis confirmed by dermatologist
2. BSA ≥10% OR PASI ≥12 OR significant impact on quality of life (DLQI ≥10)
3. Inadequate response to at least ONE conventional systemic therapy:
   - Methotrexate (≥12 weeks at therapeutic dose)
   - Cyclosporine (≥12 weeks), OR
   - Apremilast (≥16 weeks)
   OR documented contraindication to all conventional systemics

DOCUMENTATION: Dermatologist attestation, baseline disease severity scores, prior therapy history
QUANTITY: 6-month initial, 12-month renewal with PASI 75 or DLQI improvement ≥5
EXCEPTIONS: Erythrodermic psoriasis, pustular psoriasis, or concomitant PsA bypass step therapy""",
    ),
    _policy(
        "humana_derm_bio_2024", "Humana",
        "Biologic Agents for Psoriasis", "psoriasis_biologic", "psoriasis", "HUM-DERM-BIO-2024",
        text="""POLICY HUM-DERM-BIO-2024: BIOLOGIC AGENTS FOR PLAQUE PSORIASIS
Payer: Humana

COVERED AGENTS: ustekinumab (Stelara), secukinumab (Cosentyx), ixekizumab (Taltz),
guselkumab (Tremfya), risankizumab (Skyrizi)

STEP THERAPY: Trial and failure of ONE systemic agent (methotrexate, cyclosporine, or acitretin)
for ≥3 months, OR phototherapy for ≥3 months. Contraindication documentation accepted.
DISEASE SEVERITY: BSA ≥10% or PASI ≥12 or DLQI ≥10
PRESCRIBER: Board-certified dermatologist
AUTHORIZATION: 6 months initial, renewable with documented clinical response
EXCEPTIONS: Step therapy waived for erythrodermic/pustular psoriasis or hepatic contraindication""",
    ),
    _policy(
        "uhc_derm_bio_2024", "UnitedHealthcare",
        "Biologic Agents for Psoriasis", "psoriasis_biologic", "psoriasis", "UHC-DERM-BIO-2024",
        text="""POLICY UHC-DERM-BIO-2024: BIOLOGIC AGENTS FOR MODERATE-TO-SEVERE PLAQUE PSORIASIS
Payer: UnitedHealthcare

COVERED AGENTS: ustekinumab (Stelara), secukinumab (Cosentyx), ixekizumab (Taltz),
guselkumab (Tremfya), risankizumab (Skyrizi)

REQUIREMENTS:
1. Diagnosis of moderate-to-severe plaque psoriasis (BSA ≥10% or PASI ≥12)
2. Failure of at least ONE systemic therapy: methotrexate (≥3 months), cyclosporine, or phototherapy
3. Dermatologist oversight required
QUANTITY: 6-month authorization, renewal with PASI 75 response documentation
FORMULARY: Step through preferred IL-17 inhibitors before non-preferred agents unless clinical justification
EXCEPTIONS: Erythrodermic psoriasis, pustular psoriasis, hepatic/renal contraindication""",
    ),
    _policy(
        "aetna_derm_bio_2024", "Aetna",
        "Biologic Agents for Psoriasis", "psoriasis_biologic", "psoriasis", "AET-DERM-BIO-2024",
        text="""AETNA CLINICAL POLICY: BIOLOGIC AGENTS FOR PLAQUE PSORIASIS
Policy ID: AET-DERM-BIO-2024
Payer: Aetna

COVERED AGENTS: ustekinumab (Stelara), secukinumab (Cosentyx), ixekizumab (Taltz),
guselkumab (Tremfya), risankizumab (Skyrizi)

CRITERIA:
A. Moderate-to-severe plaque psoriasis (BSA ≥10% or PASI ≥12 or DLQI ≥10)
B. Inadequate response to ONE conventional systemic (methotrexate ≥12 weeks or cyclosporine ≥12 weeks)
   OR contraindication to conventional therapies
C. Dermatologist attestation
AUTHORIZATION: 6 months initial, 12 months renewal with documented response
EXCEPTIONS: Step therapy waived for severe variants (erythrodermic, pustular) or hepatotoxicity risk""",
    ),
    _policy(
        "bcbs_derm_bio_2024", "BlueCross BlueShield",
        "Biologic Agents for Psoriasis", "psoriasis_biologic", "psoriasis", "BCBS-DERM-BIO-2024",
        text="""POLICY BCBS-DERM-BIO-2024: BIOLOGIC AGENTS FOR PLAQUE PSORIASIS
Payer: BlueCross BlueShield

COVERED AGENTS: ustekinumab (Stelara), secukinumab (Cosentyx), ixekizumab (Taltz),
guselkumab (Tremfya), risankizumab (Skyrizi)

STEP THERAPY:
1. Moderate-to-severe plaque psoriasis: BSA ≥10% OR PASI ≥12
2. Trial and failure of TWO conventional therapies: methotrexate AND one of (cyclosporine, acitretin, phototherapy) for ≥3 months each
3. Failure = <PASI 50 response, intolerance, or contraindication
PRESCRIBER: Dermatologist required
QUANTITY: 26-week authorization, renewable with PASI 75 documentation
EXCEPTIONS: Step therapy waived for erythrodermic/pustular psoriasis or hepatic/renal contraindication""",
    ),
    _policy(
        "molina_derm_bio_2024", "Molina",
        "Biologic Agents for Psoriasis", "psoriasis_biologic", "psoriasis", "MOL-DERM-BIO-2024",
        text="""POLICY MOL-DERM-BIO-2024: BIOLOGIC AGENTS FOR PLAQUE PSORIASIS
Payer: Molina

COVERED AGENTS: ustekinumab (Stelara), secukinumab (Cosentyx), ixekizumab (Taltz),
guselkumab (Tremfya), risankizumab (Skyrizi)

REQUIREMENTS:
1. Moderate-to-severe plaque psoriasis (BSA ≥10% or PASI ≥12 or DLQI ≥10)
2. Failure of ONE conventional systemic therapy (methotrexate ≥3 months preferred)
3. Dermatologist supervision
AUTHORIZATION: 6 months, renewable with PASI 75 response
EXCEPTIONS: Severe psoriasis variants bypass step therapy""",
    ),
    _policy(
        "centene_derm_bio_2024", "Centene",
        "Biologic Agents for Psoriasis", "psoriasis_biologic", "psoriasis", "CEN-DERM-BIO-2024",
        text="""POLICY CEN-DERM-BIO-2024: BIOLOGIC AGENTS FOR PLAQUE PSORIASIS
Payer: Centene

COVERED AGENTS: ustekinumab (Stelara), secukinumab (Cosentyx), ixekizumab (Taltz),
guselkumab (Tremfya), risankizumab (Skyrizi)

CRITERIA:
1. Moderate-to-severe plaque psoriasis confirmed by dermatologist (BSA ≥10% or PASI ≥12)
2. Trial and failure of ONE systemic agent (methotrexate, cyclosporine, or apremilast) for ≥12 weeks
3. Baseline PASI/BSA/DLQI documentation required
AUTHORIZATION: 6 months initial, renewable
EXCEPTIONS: Erythrodermic or pustular psoriasis, hepatic contraindication""",
    ),
    _policy(
        "kaiser_derm_bio_2024", "Kaiser",
        "Biologic Agents for Psoriasis", "psoriasis_biologic", "psoriasis", "KAI-DERM-BIO-2024",
        text="""POLICY KAI-DERM-BIO-2024: BIOLOGIC AGENTS FOR PLAQUE PSORIASIS
Payer: Kaiser

COVERED AGENTS: ustekinumab (Stelara), secukinumab (Cosentyx), ixekizumab (Taltz),
guselkumab (Tremfya), risankizumab (Skyrizi)

INTEGRATED CARE CRITERIA:
1. Moderate-to-severe plaque psoriasis (BSA ≥10% or PASI ≥12)
2. Failed ONE systemic therapy within Kaiser system (methotrexate, cyclosporine, or phototherapy)
3. Dermatology department referral and co-management
AUTHORIZATION: 6 months, renewal with documented PASI 75 or DLQI improvement
FORMULARY: Preferred agents: secukinumab, risankizumab. Non-preferred require additional justification.""",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════════
# RA BIOLOGICS
# (adalimumab, etanercept, infliximab, tocilizumab, abatacept)
# ═══════════════════════════════════════════════════════════════════════════════

_RA_POLICIES = [
    # BlueCross BlueShield — EXISTING (kept as-is)
    {
        "id": "bcbs_biologic_4.2.1b",
        "source": "PAYER",
        "title": "BlueCross BlueShield: Biologic DMARD Agents — Policy 4.2.1b",
        "text": """POLICY 4.2.1b: BIOLOGIC DISEASE-MODIFYING ANTIRHEUMATIC DRUGS (bDMARDs)
Payer: BlueCross BlueShield

COVERAGE CRITERIA — RHEUMATOID ARTHRITIS:
Prior authorization for biologic DMARDs (adalimumab/Humira, etanercept/Enbrel, infliximab/Remicade,
abatacept/Orencia, tocilizumab/Actemra, sarilumab/Kevzara) requires ALL of the following:

1. STEP THERAPY REQUIREMENT: Documentation of adequate trial and failure of TWO conventional
   synthetic DMARDs (csDMARDs) including methotrexate AND at least one of the following:
   hydroxychloroquine, sulfasalazine, or leflunomide. Minimum trial duration: 3 months each at
   maximally tolerated doses, unless contraindicated.

2. DIAGNOSIS: Confirmed diagnosis of moderate-to-severe rheumatoid arthritis (RA) with inadequate
   response defined as DAS28 > 3.2 despite csDMARD therapy.

3. PRESCRIBER: Must be prescribed or co-managed by a rheumatologist.

4. QUANTITY LIMITS: 26-week authorization, renewable with documentation of clinical response.

MEDICAL NECESSITY DEFINITION: Treatment is medically necessary when conventional therapy has been
tried and failed, and the patient meets the diagnostic criteria above.

EXCEPTIONS: Step therapy may be waived if conventional DMARDs are contraindicated due to renal
impairment, hepatic disease, pregnancy planning, or documented intolerance.""",
        "url": "https://www.bcbs.com/prior-authorization",
        "metadata": {"payer": "BlueCross BlueShield", "policy_code": "4.2.1b", "drug_class": "biologic_dmard", "condition": "rheumatoid_arthritis", "policy_id": "4.2.1b"},
    },
    # Aetna — EXISTING (kept as-is)
    {
        "id": "aetna_biologic_dmard",
        "source": "PAYER",
        "title": "Aetna: Biologic and Targeted Synthetic DMARDs — Rheumatoid Arthritis",
        "text": """AETNA CLINICAL POLICY BULLETIN: BIOLOGIC AND TARGETED SYNTHETIC DISEASE-MODIFYING
ANTIRHEUMATIC DRUGS (DMARDs) FOR RHEUMATOID ARTHRITIS

CRITERIA FOR INITIAL AUTHORIZATION:
Aetna considers biologic DMARDs medically necessary for treatment of moderate to severely active
rheumatoid arthritis when ALL of the following criteria are met:

A. DIAGNOSIS: Diagnosis of moderate-to-severely active RA confirmed by rheumatologist, with
   documentation of active disease (≥6 swollen joints OR ≥6 tender joints OR elevated CRP/ESR)

B. PRIOR THERAPY (Step Therapy Protocol):
   The member must have had an inadequate response, intolerance, or contraindication to ONE
   conventional DMARD (methotrexate preferred) at adequate doses for a minimum of 8 weeks.
   Note: Aetna's 2023 policy revision reduced step therapy from two DMARDs to one DMARD
   based on updated ACR guidelines.

C. PRESCRIBER: Rheumatologist attestation required.

QUANTITY: Initial 6-month authorization. Continuation requires documentation of clinical benefit
(ACR20 response or improvement in disease activity measures).

EXCLUSIONS: Not covered for mild RA, off-label indications without peer-reviewed evidence.""",
        "url": "https://www.aetna.com/cpb/medical/data/600_699/0676.html",
        "metadata": {"payer": "Aetna", "policy_code": "CPB_0676", "drug_class": "biologic_dmard", "condition": "rheumatoid_arthritis", "policy_id": "CPB_0676"},
    },
    # UnitedHealthcare — EXISTING
    {
        "id": "uhc_biologic_ra",
        "source": "PAYER",
        "title": "UnitedHealthcare: Biologic Agents for RA — Coverage Policy",
        "text": """UNITEDHEALTHCARE COVERAGE POLICY: BIOLOGIC AGENTS FOR RHEUMATOID ARTHRITIS

STEP THERAPY REQUIREMENTS:
Prior authorization required. Member must have tried and had inadequate response to:
- Methotrexate at ≥15mg/week (or maximum tolerated dose) for ≥12 weeks, AND
- At least one additional conventional DMARD (hydroxychloroquine, sulfasalazine, or leflunomide)
  for ≥12 weeks

DISEASE SEVERITY: Active disease defined as ≥6 swollen joints or ≥6 tender joints, plus elevated
inflammatory markers (CRP > 0.8 mg/dL or ESR > 28 mm/hr) or radiographic progression.

PRESCRIBER REQUIREMENT: Board-certified rheumatologist.

QUANTITY LIMITS AND AUTHORIZATION PERIOD: 6 months initial, 12 months renewal with response doc.

FORMULARY PREFERENCE: Step through preferred agents (etanercept, adalimumab) before non-preferred
biologics unless there is clinical justification.""",
        "url": "https://www.uhcprovider.com/prior-authorization",
        "metadata": {"payer": "UnitedHealthcare", "policy_code": "PA-RA-001", "drug_class": "biologic_dmard", "condition": "rheumatoid_arthritis", "policy_id": "PA-RA-001"},
    },
    # Cigna — EXISTING
    {
        "id": "cigna_biologic_dmard",
        "source": "PAYER",
        "title": "Cigna: Biologic DMARDs Coverage Policy",
        "text": """CIGNA MEDICAL COVERAGE POLICY: BIOLOGIC DMARDS FOR INFLAMMATORY CONDITIONS

RHEUMATOID ARTHRITIS CRITERIA:
Cigna covers biologic DMARDs when:
1. Diagnosis of moderate-to-severe RA by rheumatologist
2. Inadequate response to methotrexate alone (minimum 12-week trial at ≥15mg/week) —
   Cigna does not require failure of a second DMARD if methotrexate was truly inadequate
3. DAS28-CRP > 3.2 (moderate disease) or DAS28-CRP > 5.1 (severe) documented

PSORIATIC ARTHRITIS: Step therapy requires failure of at least one NSAID (8 weeks) plus one
conventional DMARD (methotrexate or leflunomide, 12 weeks), OR documented joint destruction.

ANKYLOSING SPONDYLITIS: Failure of two NSAIDs at maximum tolerated doses for 4 weeks each.

QUANTITY LIMITS: 6-month authorization renewable annually with clinical response documentation.""",
        "url": "https://www.cigna.com/static/www-cigna-com/docs/health-care-providers/clinical-coverage-policies",
        "metadata": {"payer": "Cigna", "policy_code": "CIGNA-DMARD-001", "drug_class": "biologic_dmard", "condition": "rheumatoid_arthritis", "policy_id": "CIGNA-DMARD-001"},
    },
    # Humana — EXISTING
    {
        "id": "humana_biologic_dmard",
        "source": "PAYER",
        "title": "Humana: Prior Authorization for Biologic Agents",
        "text": """HUMANA PHARMACY PRIOR AUTHORIZATION CRITERIA: BIOLOGIC AGENTS

TNF INHIBITORS (adalimumab, etanercept, infliximab, certolizumab, golimumab):

RHEUMATOID ARTHRITIS:
Required criteria:
- Moderate-to-severe RA diagnosis by rheumatologist
- Failed adequate trial of methotrexate (≥12 weeks at ≥15mg/week or max tolerated)
- Clinical documentation: tender joint count, swollen joint count, patient global assessment
- Humana requires failure of ONE csDMARD (methotrexate preferred); failure of TWO is NOT required
  per updated Humana policy aligned with 2021 ACR RA Guidelines

DURATION OF INITIAL AUTHORIZATION: 6 months
RENEWAL: Requires ACR20 response or CDAI/DAS28 improvement documentation

EXCEPTIONS: Conventional DMARD step therapy may be bypassed with:
- Documented contraindication (hepatotoxicity risk, pregnancy, renal insufficiency)
- High disease activity with poor prognostic factors (RF+, anti-CCP+, erosive disease)""",
        "url": "https://www.humana.com/provider/medical-resources/prior-authorization",
        "metadata": {"payer": "Humana", "policy_code": "HUM-PA-BIO-001", "drug_class": "biologic_dmard", "condition": "rheumatoid_arthritis", "policy_id": "HUM-PA-BIO-001"},
    },
    # Anthem Blue Cross — NEW
    _policy(
        "ant_ra_bio_2024", "Anthem Blue Cross",
        "Biologic DMARDs for RA", "biologic_dmard", "rheumatoid_arthritis", "ANT-RA-BIO-2024",
        text="""POLICY ANT-RA-BIO-2024: BIOLOGIC DMARDS FOR RHEUMATOID ARTHRITIS
Payer: Anthem Blue Cross

COVERED AGENTS: adalimumab (Humira), etanercept (Enbrel), infliximab (Remicade),
tocilizumab (Actemra), abatacept (Orencia), sarilumab (Kevzara)

STEP THERAPY:
1. Moderate-to-severe RA (DAS28 >3.2) confirmed by rheumatologist
2. Failure of methotrexate at ≥15mg/week for ≥12 weeks AND one additional csDMARD for ≥12 weeks
3. Documented active disease: ≥6 swollen joints or ≥6 tender joints, elevated CRP/ESR
PRESCRIBER: Rheumatologist required
AUTHORIZATION: 6 months initial, 12 months renewal with ACR20 response
EXCEPTIONS: Step therapy waived for hepatic disease, pregnancy, or documented intolerance""",
    ),
    # Molina — NEW
    _policy(
        "molina_ra_bio_2024", "Molina",
        "Biologic DMARDs for RA", "biologic_dmard", "rheumatoid_arthritis", "MOL-RA-BIO-2024",
        text="""POLICY MOL-RA-BIO-2024: BIOLOGIC DMARDS FOR RHEUMATOID ARTHRITIS
Payer: Molina

COVERED AGENTS: adalimumab, etanercept, infliximab, tocilizumab, abatacept
STEP THERAPY: Failure of ONE csDMARD (methotrexate preferred) at adequate dose for ≥12 weeks
DISEASE SEVERITY: Moderate-to-severe RA (DAS28 >3.2), rheumatologist confirmation
AUTHORIZATION: 6 months initial, renewable with clinical response documentation
EXCEPTIONS: csDMARD step waived for hepatic/renal contraindication or pregnancy""",
    ),
    # Centene — NEW
    _policy(
        "centene_ra_bio_2024", "Centene",
        "Biologic DMARDs for RA", "biologic_dmard", "rheumatoid_arthritis", "CEN-RA-BIO-2024",
        text="""POLICY CEN-RA-BIO-2024: BIOLOGIC DMARDS FOR RHEUMATOID ARTHRITIS
Payer: Centene

COVERED AGENTS: adalimumab, etanercept, infliximab, tocilizumab, abatacept
STEP THERAPY: Trial and failure of methotrexate (≥12 weeks) required; second csDMARD failure NOT required
DISEASE SEVERITY: DAS28 >3.2, rheumatologist attestation
AUTHORIZATION: 6 months, renewable with ACR20 response or DAS28 improvement
EXCEPTIONS: Step therapy waived for major contraindications""",
    ),
    # Kaiser — NEW
    _policy(
        "kaiser_ra_bio_2024", "Kaiser",
        "Biologic DMARDs for RA", "biologic_dmard", "rheumatoid_arthritis", "KAI-RA-BIO-2024",
        text="""POLICY KAI-RA-BIO-2024: BIOLOGIC DMARDS FOR RHEUMATOID ARTHRITIS
Payer: Kaiser

INTEGRATED CARE CRITERIA:
1. Moderate-to-severe RA (DAS28 >3.2) managed within Kaiser rheumatology
2. Failure of methotrexate AND one additional csDMARD within Kaiser system
3. Preferred formulary: adalimumab biosimilar, etanercept. Non-preferred require justification
AUTHORIZATION: 6 months, renewable with documented clinical response
EXCEPTIONS: Step therapy waived for hepatic/renal disease or pregnancy""",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════════
# GLP-1 AGONISTS
# (semaglutide, liraglutide, dulaglutide, tirzepatide)
# ═══════════════════════════════════════════════════════════════════════════════

_GLP1_POLICIES = [
    # BlueCross BlueShield — EXISTING
    {
        "id": "bcbs_glp1_rx_dm_2024",
        "source": "PAYER",
        "title": "BlueCross BlueShield: GLP-1 Receptor Agonists — Policy RX-DM-2024",
        "text": """POLICY RX-DM-2024: GLP-1 RECEPTOR AGONISTS (semaglutide, liraglutide, dulaglutide, exenatide)
Payer: BlueCross BlueShield

COVERAGE CRITERIA — TYPE 2 DIABETES:
1. DIAGNOSIS: Type 2 diabetes mellitus (ICD-10: E11.xx)
2. HbA1c THRESHOLD: HbA1c ≥ 8.0% OR HbA1c ≥ 7.5% with high cardiovascular risk (documented ASCVD)
3. STEP THERAPY: Must demonstrate inadequate glycemic control (HbA1c above threshold) on:
   a) Metformin at maximally tolerated dose (≥1000mg/day) for ≥3 months, AND
   b) One additional agent: sulfonylurea, DPP-4 inhibitor, or SGLT-2 inhibitor for ≥3 months
4. CONTRAINDICATIONS TO STEP THERAPY: Metformin may be bypassed if eGFR < 30, lactic acidosis
   history, or radiographic contrast study planned.

QUANTITY LIMITS: 90-day supply. Renewal requires HbA1c reduction of ≥0.5% or documented weight loss.

NOTE: For cardiovascular risk reduction indication (semaglutide/liraglutide), HbA1c threshold
may be waived with documented established ASCVD or CKD Stage 3+.""",
        "url": "https://www.bcbs.com/prior-authorization",
        "metadata": {"payer": "BlueCross BlueShield", "policy_code": "RX-DM-2024", "drug_class": "glp1", "condition": "type2_diabetes", "policy_id": "RX-DM-2024"},
    },
    # Aetna — EXISTING
    {
        "id": "aetna_glp1_rx_dm_2024_07",
        "source": "PAYER",
        "title": "Aetna: GLP-1 Receptor Agonists for Diabetes — Policy RX-DM-2024-07",
        "text": """AETNA PHARMACY BENEFIT POLICY: GLP-1 RECEPTOR AGONISTS
Policy ID: RX-DM-2024-07

COVERAGE CRITERIA:
Step 1: Member must have Type 2 diabetes diagnosis (E11.xx)
Step 2: HbA1c must be ≥ 8.0% at time of request
Step 3: Must document failure of metformin at maximum tolerated dose PLUS a sulfonylurea

EXCEPTIONS to HbA1c threshold:
- Established cardiovascular disease (prior MI, stroke, or peripheral arterial disease):
  HbA1c ≥ 7.0% is sufficient
- Heart failure or CKD Stage 3+: Covered at any HbA1c for semaglutide (cardiovascular indication)
- Metformin contraindication: Step therapy requirement for metformin is waived

WEIGHT MANAGEMENT (Wegovy/semaglutide 2.4mg):
Separate criteria apply — BMI ≥ 30 or BMI ≥ 27 with comorbidity, plus failure of behavioral
intervention for 6 months.""",
        "url": "https://www.aetna.com/prior-authorization",
        "metadata": {"payer": "Aetna", "policy_code": "RX-DM-2024-07", "drug_class": "glp1", "condition": "type2_diabetes", "policy_id": "RX-DM-2024-07"},
    },
    # Anthem Blue Cross — NEW
    _policy(
        "ant_glp1_2024", "Anthem Blue Cross",
        "GLP-1 Receptor Agonists", "glp1", "type2_diabetes", "ANT-GLP1-2024",
        text="""POLICY ANT-GLP1-2024: GLP-1 RECEPTOR AGONISTS
Payer: Anthem Blue Cross

COVERED AGENTS: semaglutide (Ozempic), liraglutide (Victoza), dulaglutide (Trulicity), tirzepatide (Mounjaro)

CRITERIA — TYPE 2 DIABETES:
1. Type 2 DM diagnosis (E11.xx), HbA1c ≥7.5%
2. Failure of metformin (≥3 months at max tolerated dose) AND one additional oral agent
3. Endocrinologist or PCP attestation
QUANTITY: 90-day supply, renewal with HbA1c reduction ≥0.5%
CARDIOVASCULAR INDICATION: HbA1c threshold waived with documented ASCVD
WEIGHT MANAGEMENT: Separate criteria — BMI ≥30 or ≥27 with comorbidity""",
    ),
    # Cigna — NEW
    _policy(
        "cigna_glp1_2024", "Cigna",
        "GLP-1 Receptor Agonists", "glp1", "type2_diabetes", "CIG-GLP1-2024",
        text="""POLICY CIG-GLP1-2024: GLP-1 RECEPTOR AGONISTS
Payer: Cigna

COVERED AGENTS: semaglutide (Ozempic), liraglutide (Victoza), dulaglutide (Trulicity), tirzepatide (Mounjaro)
CRITERIA: Type 2 DM, HbA1c ≥8.0%, failure of metformin monotherapy (≥12 weeks)
EXCEPTIONS: Metformin contraindication (eGFR <30, lactic acidosis history), ASCVD waives HbA1c threshold
QUANTITY: 90-day supply, renewable with documented glycemic improvement
WEIGHT MANAGEMENT: BMI ≥30 or ≥27 + comorbidity, behavioral intervention ≥6 months""",
    ),
    # Humana — NEW
    _policy(
        "humana_glp1_2024", "Humana",
        "GLP-1 Receptor Agonists", "glp1", "type2_diabetes", "HUM-GLP1-2024",
        text="""POLICY HUM-GLP1-2024: GLP-1 RECEPTOR AGONISTS
Payer: Humana

COVERED AGENTS: semaglutide, liraglutide, dulaglutide, tirzepatide
CRITERIA: T2DM, HbA1c ≥7.5%, failure of metformin + one additional oral agent
EXCEPTIONS: Metformin contraindication, ASCVD indication waives HbA1c threshold
AUTHORIZATION: 90-day supply, renewable with HbA1c improvement""",
    ),
    # UnitedHealthcare — NEW
    _policy(
        "uhc_glp1_2024", "UnitedHealthcare",
        "GLP-1 Receptor Agonists", "glp1", "type2_diabetes", "UHC-GLP1-2024",
        text="""POLICY UHC-GLP1-2024: GLP-1 RECEPTOR AGONISTS
Payer: UnitedHealthcare

COVERED AGENTS: semaglutide (Ozempic), liraglutide (Victoza), dulaglutide (Trulicity), tirzepatide (Mounjaro)
CRITERIA: T2DM, HbA1c ≥8.0%, failure of metformin AND one additional oral agent (≥3 months each)
FORMULARY: Preferred — dulaglutide, semaglutide. Non-preferred require prior auth
CARDIOVASCULAR: ASCVD waives HbA1c threshold for semaglutide/liraglutide
QUANTITY: 90-day supply, renewal requires HbA1c reduction documentation""",
    ),
    # Molina — NEW
    _policy(
        "molina_glp1_2024", "Molina",
        "GLP-1 Receptor Agonists", "glp1", "type2_diabetes", "MOL-GLP1-2024",
        text="""POLICY MOL-GLP1-2024: GLP-1 RECEPTOR AGONISTS
Payer: Molina

COVERED AGENTS: semaglutide, liraglutide, dulaglutide, tirzepatide
CRITERIA: T2DM, HbA1c ≥8.0%, failure of metformin at max dose for ≥3 months
EXCEPTIONS: Metformin bypass for eGFR <30 or documented intolerance
AUTHORIZATION: 90-day supply, renewable""",
    ),
    # Centene — NEW
    _policy(
        "centene_glp1_2024", "Centene",
        "GLP-1 Receptor Agonists", "glp1", "type2_diabetes", "CEN-GLP1-2024",
        text="""POLICY CEN-GLP1-2024: GLP-1 RECEPTOR AGONISTS
Payer: Centene

COVERED AGENTS: semaglutide, liraglutide, dulaglutide, tirzepatide
CRITERIA: T2DM, HbA1c ≥7.5%, failure of metformin + one oral agent
CARDIOVASCULAR INDICATION: Semaglutide/liraglutide covered at any HbA1c with ASCVD
AUTHORIZATION: 90-day supply, renewable with glycemic improvement""",
    ),
    # Kaiser — NEW
    _policy(
        "kaiser_glp1_2024", "Kaiser",
        "GLP-1 Receptor Agonists", "glp1", "type2_diabetes", "KAI-GLP1-2024",
        text="""POLICY KAI-GLP1-2024: GLP-1 RECEPTOR AGONISTS
Payer: Kaiser

COVERED AGENTS: semaglutide, liraglutide, dulaglutide, tirzepatide
INTEGRATED CARE CRITERIA: T2DM managed within Kaiser, HbA1c ≥8.0%
STEP THERAPY: Metformin + one additional agent within Kaiser formulary
PREFERRED: dulaglutide, semaglutide
AUTHORIZATION: 90-day supply, renewable with documented response""",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════════
# MS DMTs
# (ocrelizumab, natalizumab, fingolimod)
# ═══════════════════════════════════════════════════════════════════════════════

_MS_POLICIES = [
    # UnitedHealthcare — EXISTING
    {
        "id": "uhc_ms_biologic_ms_bio_2024",
        "source": "PAYER",
        "title": "UnitedHealthcare: Multiple Sclerosis Disease-Modifying Therapies — Policy MS-BIO-2024",
        "text": """UNITEDHEALTHCARE COVERAGE DETERMINATION: MULTIPLE SCLEROSIS DISEASE-MODIFYING THERAPIES
Policy: MS-BIO-2024

COVERED INDICATIONS — HIGH-EFFICACY DMTs (ocrelizumab/Ocrevus, natalizumab/Tysabri,
alemtuzumab/Lemtrada, cladribine/Mavenclad):

RELAPSING-REMITTING MS (RRMS):
Required: ONE of the following:
a) Two or more clinical relapses in the preceding 12 months, OR
b) Failure of at least one first-line DMT (interferon beta-1a, interferon beta-1b,
   glatiramer acetate, dimethyl fumarate, teriflunomide) for minimum 6 months, OR
c) Highly active disease on MRI: ≥2 new T2 lesions in 12 months despite first-line therapy, OR
d) Rapidly evolving severe RRMS: 2+ disabling relapses in 1 year AND ≥1 gadolinium-enhancing
   or significant new T2 lesion

PRIMARY PROGRESSIVE MS (PPMS):
Ocrelizumab is covered for PPMS with evidence of disease activity (MRI or clinical).

NOTE: The FDA label for ocrelizumab (Ocrevus) specifies use in both RRMS AND PPMS.
The 2+ relapses in 12 months criterion is ONE pathway, not the only pathway for coverage.""",
        "url": "https://www.uhcprovider.com/prior-authorization",
        "metadata": {"payer": "UnitedHealthcare", "policy_code": "MS-BIO-2024", "drug_class": "ms_dmt", "condition": "multiple_sclerosis", "policy_id": "MS-BIO-2024"},
    },
    # Anthem Blue Cross — NEW
    _policy(
        "ant_ms_dmt_2024", "Anthem Blue Cross",
        "MS Disease-Modifying Therapies", "ms_dmt", "multiple_sclerosis", "ANT-MS-DMT-2024",
        text="""POLICY ANT-MS-DMT-2024: DISEASE-MODIFYING THERAPIES FOR MULTIPLE SCLEROSIS
Payer: Anthem Blue Cross

COVERED AGENTS: ocrelizumab (Ocrevus), natalizumab (Tysabri), fingolimod (Gilenya), siponimod (Mayzent)

HIGH-EFFICACY DMT CRITERIA:
1. Confirmed MS diagnosis by neurologist (McDonald criteria)
2. RRMS: Failure of ONE first-line DMT (interferon, glatiramer, dimethyl fumarate) for ≥6 months
   OR ≥2 relapses in 12 months OR highly active MRI disease
3. PPMS: Ocrelizumab covered with evidence of inflammatory activity
PRESCRIBER: Neurologist specializing in MS
AUTHORIZATION: 12 months, renewable with documented clinical stability
JCV TESTING: Required before natalizumab initiation""",
    ),
    _policy(
        "cigna_ms_dmt_2024", "Cigna",
        "MS Disease-Modifying Therapies", "ms_dmt", "multiple_sclerosis", "CIG-MS-DMT-2024",
        text="""POLICY CIG-MS-DMT-2024: MS DISEASE-MODIFYING THERAPIES
Payer: Cigna

COVERED AGENTS: ocrelizumab, natalizumab, fingolimod
CRITERIA: MS diagnosis (McDonald criteria), neurologist attestation
STEP THERAPY: Failure of ONE first-line DMT for ≥6 months OR high disease activity
PPMS: Ocrelizumab covered with inflammatory activity evidence
AUTHORIZATION: 12 months, renewable""",
    ),
    _policy(
        "humana_ms_dmt_2024", "Humana",
        "MS Disease-Modifying Therapies", "ms_dmt", "multiple_sclerosis", "HUM-MS-DMT-2024",
        text="""POLICY HUM-MS-DMT-2024: MS DISEASE-MODIFYING THERAPIES
Payer: Humana

COVERED AGENTS: ocrelizumab, natalizumab, fingolimod
CRITERIA: Confirmed MS, neurologist management, failure of first-line DMT or high activity
AUTHORIZATION: 12 months, renewable with clinical stability documentation""",
    ),
    _policy(
        "aetna_ms_dmt_2024", "Aetna",
        "MS Disease-Modifying Therapies", "ms_dmt", "multiple_sclerosis", "AET-MS-DMT-2024",
        text="""AETNA CLINICAL POLICY: MS DISEASE-MODIFYING THERAPIES
Policy ID: AET-MS-DMT-2024
Payer: Aetna

COVERED AGENTS: ocrelizumab (Ocrevus), natalizumab (Tysabri), fingolimod (Gilenya)
CRITERIA: MS diagnosis, neurologist attestation, failure of ONE first-line DMT or high activity
PPMS: Ocrelizumab approved with inflammatory activity evidence
AUTHORIZATION: 12 months, renewable with EDSS stability documentation""",
    ),
    _policy(
        "bcbs_ms_dmt_2024", "BlueCross BlueShield",
        "MS Disease-Modifying Therapies", "ms_dmt", "multiple_sclerosis", "BCBS-MS-DMT-2024",
        text="""POLICY BCBS-MS-DMT-2024: MS DISEASE-MODIFYING THERAPIES
Payer: BlueCross BlueShield

COVERED AGENTS: ocrelizumab, natalizumab, fingolimod
STEP THERAPY: Failure of ONE first-line DMT (≥6 months) OR ≥2 relapses in 12 months
PPMS: Ocrelizumab covered with MRI/clinical disease activity
PRESCRIBER: MS-specialized neurologist
AUTHORIZATION: 12 months, renewable""",
    ),
    _policy(
        "molina_ms_dmt_2024", "Molina",
        "MS Disease-Modifying Therapies", "ms_dmt", "multiple_sclerosis", "MOL-MS-DMT-2024",
        text="""POLICY MOL-MS-DMT-2024: MS DISEASE-MODIFYING THERAPIES
Payer: Molina

COVERED AGENTS: ocrelizumab, natalizumab, fingolimod
CRITERIA: MS diagnosis, neurologist, failure of first-line DMT or high disease activity
AUTHORIZATION: 12 months, renewable""",
    ),
    _policy(
        "centene_ms_dmt_2024", "Centene",
        "MS Disease-Modifying Therapies", "ms_dmt", "multiple_sclerosis", "CEN-MS-DMT-2024",
        text="""POLICY CEN-MS-DMT-2024: MS DISEASE-MODIFYING THERAPIES
Payer: Centene

COVERED AGENTS: ocrelizumab, natalizumab, fingolimod
CRITERIA: Confirmed MS, neurologist oversight, first-line DMT failure or highly active disease
AUTHORIZATION: 12 months, renewable with EDSS documentation""",
    ),
    _policy(
        "kaiser_ms_dmt_2024", "Kaiser",
        "MS Disease-Modifying Therapies", "ms_dmt", "multiple_sclerosis", "KAI-MS-DMT-2024",
        text="""POLICY KAI-MS-DMT-2024: MS DISEASE-MODIFYING THERAPIES
Payer: Kaiser

INTEGRATED CARE: MS managed within Kaiser neurology department
COVERED AGENTS: ocrelizumab, natalizumab, fingolimod
CRITERIA: First-line DMT failure within Kaiser system or high disease activity
PREFERRED: ocrelizumab for RRMS and PPMS
AUTHORIZATION: 12 months, renewable""",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════════
# ONCOLOGY IMMUNOTHERAPY
# (pembrolizumab, nivolumab, atezolizumab)
# ═══════════════════════════════════════════════════════════════════════════════

_ONCOLOGY_POLICIES = [
    _policy(
        "ant_onc_io_2024", "Anthem Blue Cross",
        "Oncology Immunotherapy Agents", "oncology_immunotherapy", "oncology", "ANT-ONC-IO-2024",
        text="""POLICY ANT-ONC-IO-2024: IMMUNE CHECKPOINT INHIBITORS
Payer: Anthem Blue Cross

COVERED AGENTS: pembrolizumab (Keytruda), nivolumab (Opdivo), atezolizumab (Tecentriq)

CRITERIA:
1. FDA-approved indication with NCCN Category 1 or 2A recommendation
2. Pathology confirmation of eligible tumor type
3. PD-L1 testing where required by FDA label (pembrolizumab: TPS ≥1% for NSCLC first-line mono)
4. ECOG performance status 0-2
5. Oncologist attestation
AUTHORIZATION: Per treatment cycle, renewable with documented response/stability
EXCEPTIONS: Expanded access for NCCN Category 2B with tumor board recommendation""",
    ),
    _policy(
        "cigna_onc_io_2024", "Cigna",
        "Oncology Immunotherapy Agents", "oncology_immunotherapy", "oncology", "CIG-ONC-IO-2024",
        text="""POLICY CIG-ONC-IO-2024: IMMUNE CHECKPOINT INHIBITORS
Payer: Cigna

COVERED AGENTS: pembrolizumab, nivolumab, atezolizumab
CRITERIA: FDA-approved indication, NCCN recommendation, pathology confirmation, PD-L1 testing where applicable
AUTHORIZATION: Per cycle, renewable with response documentation""",
    ),
    _policy(
        "humana_onc_io_2024", "Humana",
        "Oncology Immunotherapy Agents", "oncology_immunotherapy", "oncology", "HUM-ONC-IO-2024",
        text="""POLICY HUM-ONC-IO-2024: IMMUNE CHECKPOINT INHIBITORS
Payer: Humana

COVERED AGENTS: pembrolizumab, nivolumab, atezolizumab
CRITERIA: FDA-approved indication, NCCN Cat 1/2A, oncologist attestation, PD-L1 where required
AUTHORIZATION: Per cycle, renewable""",
    ),
    _policy(
        "uhc_onc_io_2024", "UnitedHealthcare",
        "Oncology Immunotherapy Agents", "oncology_immunotherapy", "oncology", "UHC-ONC-IO-2024",
        text="""POLICY UHC-ONC-IO-2024: IMMUNE CHECKPOINT INHIBITORS
Payer: UnitedHealthcare

COVERED AGENTS: pembrolizumab (Keytruda), nivolumab (Opdivo), atezolizumab (Tecentriq)
CRITERIA: FDA-approved indication, NCCN recommendation, pathology, PD-L1 testing as required
FORMULARY: Preferred — pembrolizumab for first-line eligible indications
AUTHORIZATION: Per cycle, renewable with response/stability documentation""",
    ),
    _policy(
        "aetna_onc_io_2024", "Aetna",
        "Oncology Immunotherapy Agents", "oncology_immunotherapy", "oncology", "AET-ONC-IO-2024",
        text="""AETNA POLICY AET-ONC-IO-2024: IMMUNE CHECKPOINT INHIBITORS
Payer: Aetna

COVERED AGENTS: pembrolizumab, nivolumab, atezolizumab
CRITERIA: FDA-approved indication, NCCN Cat 1/2A, oncologist attestation
AUTHORIZATION: Per cycle, renewable""",
    ),
    _policy(
        "bcbs_onc_io_2024", "BlueCross BlueShield",
        "Oncology Immunotherapy Agents", "oncology_immunotherapy", "oncology", "BCBS-ONC-IO-2024",
        text="""POLICY BCBS-ONC-IO-2024: IMMUNE CHECKPOINT INHIBITORS
Payer: BlueCross BlueShield

COVERED AGENTS: pembrolizumab, nivolumab, atezolizumab
CRITERIA: FDA-approved indication, NCCN recommendation, pathology confirmation, PD-L1 where required
AUTHORIZATION: Per treatment cycle, renewable with documented response""",
    ),
    _policy(
        "molina_onc_io_2024", "Molina",
        "Oncology Immunotherapy Agents", "oncology_immunotherapy", "oncology", "MOL-ONC-IO-2024",
        text="""POLICY MOL-ONC-IO-2024: IMMUNE CHECKPOINT INHIBITORS
Payer: Molina

COVERED AGENTS: pembrolizumab, nivolumab, atezolizumab
CRITERIA: FDA-approved indication, NCCN recommendation, oncologist attestation
AUTHORIZATION: Per cycle, renewable""",
    ),
    _policy(
        "centene_onc_io_2024", "Centene",
        "Oncology Immunotherapy Agents", "oncology_immunotherapy", "oncology", "CEN-ONC-IO-2024",
        text="""POLICY CEN-ONC-IO-2024: IMMUNE CHECKPOINT INHIBITORS
Payer: Centene

COVERED AGENTS: pembrolizumab, nivolumab, atezolizumab
CRITERIA: FDA-approved indication, NCCN Cat 1/2A, PD-L1 testing where applicable
AUTHORIZATION: Per cycle, renewable with response documentation""",
    ),
    _policy(
        "kaiser_onc_io_2024", "Kaiser",
        "Oncology Immunotherapy Agents", "oncology_immunotherapy", "oncology", "KAI-ONC-IO-2024",
        text="""POLICY KAI-ONC-IO-2024: IMMUNE CHECKPOINT INHIBITORS
Payer: Kaiser

COVERED AGENTS: pembrolizumab, nivolumab, atezolizumab
INTEGRATED CARE: Oncology department within Kaiser system
CRITERIA: FDA-approved indication, NCCN recommendation, tumor board review for complex cases
AUTHORIZATION: Per cycle, renewable""",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════════
# SGLT2 INHIBITORS
# (empagliflozin, dapagliflozin)
# ═══════════════════════════════════════════════════════════════════════════════

_SGLT2_POLICIES = [
    _policy(
        "ant_sglt2_2024", "Anthem Blue Cross",
        "SGLT2 Inhibitors", "sglt2", "type2_diabetes", "ANT-SGLT2-2024",
        text="""POLICY ANT-SGLT2-2024: SGLT2 INHIBITORS
Payer: Anthem Blue Cross

COVERED AGENTS: empagliflozin (Jardiance), dapagliflozin (Farxiga)

DIABETES CRITERIA: T2DM, HbA1c ≥7.5%, failure of metformin at max dose for ≥3 months
HEART FAILURE INDICATION: Covered for HFrEF (EF ≤40%) regardless of diabetes status (dapagliflozin/empagliflozin)
CKD INDICATION: Covered for CKD with eGFR 20-90 and UACR ≥200 (dapagliflozin)
AUTHORIZATION: 12 months, renewable""",
    ),
    _policy(
        "cigna_sglt2_2024", "Cigna",
        "SGLT2 Inhibitors", "sglt2", "type2_diabetes", "CIG-SGLT2-2024",
        text="""POLICY CIG-SGLT2-2024: SGLT2 INHIBITORS
Payer: Cigna

COVERED AGENTS: empagliflozin (Jardiance), dapagliflozin (Farxiga)
DIABETES: T2DM, HbA1c ≥8.0%, metformin failure
HEART FAILURE/CKD: Covered per FDA label indications
AUTHORIZATION: 12 months, renewable""",
    ),
    _policy(
        "humana_sglt2_2024", "Humana",
        "SGLT2 Inhibitors", "sglt2", "type2_diabetes", "HUM-SGLT2-2024",
        text="""POLICY HUM-SGLT2-2024: SGLT2 INHIBITORS
Payer: Humana

COVERED AGENTS: empagliflozin, dapagliflozin
CRITERIA: T2DM with HbA1c ≥7.5%, metformin failure; or HFrEF; or CKD per FDA label
AUTHORIZATION: 12 months, renewable""",
    ),
    _policy(
        "uhc_sglt2_2024", "UnitedHealthcare",
        "SGLT2 Inhibitors", "sglt2", "type2_diabetes", "UHC-SGLT2-2024",
        text="""POLICY UHC-SGLT2-2024: SGLT2 INHIBITORS
Payer: UnitedHealthcare

COVERED AGENTS: empagliflozin (Jardiance), dapagliflozin (Farxiga)
DIABETES: T2DM, HbA1c ≥8.0%, metformin + one agent failure
HF/CKD: Covered per FDA indications
PREFERRED: empagliflozin
AUTHORIZATION: 12 months, renewable""",
    ),
    _policy(
        "aetna_sglt2_2024", "Aetna",
        "SGLT2 Inhibitors", "sglt2", "type2_diabetes", "AET-SGLT2-2024",
        text="""AETNA POLICY AET-SGLT2-2024: SGLT2 INHIBITORS
Payer: Aetna

COVERED AGENTS: empagliflozin, dapagliflozin
CRITERIA: T2DM with HbA1c ≥7.5%, metformin failure; HFrEF; CKD per label
AUTHORIZATION: 12 months, renewable""",
    ),
    _policy(
        "bcbs_sglt2_2024", "BlueCross BlueShield",
        "SGLT2 Inhibitors", "sglt2", "type2_diabetes", "BCBS-SGLT2-2024",
        text="""POLICY BCBS-SGLT2-2024: SGLT2 INHIBITORS
Payer: BlueCross BlueShield

COVERED AGENTS: empagliflozin, dapagliflozin
DIABETES: T2DM, HbA1c ≥8.0%, metformin + one additional agent failure
HF/CKD: Covered per FDA-approved indications
AUTHORIZATION: 12 months, renewable with clinical response""",
    ),
    _policy(
        "molina_sglt2_2024", "Molina",
        "SGLT2 Inhibitors", "sglt2", "type2_diabetes", "MOL-SGLT2-2024",
        text="""POLICY MOL-SGLT2-2024: SGLT2 INHIBITORS
Payer: Molina

COVERED AGENTS: empagliflozin, dapagliflozin
CRITERIA: T2DM + metformin failure, or HF/CKD per FDA indications
AUTHORIZATION: 12 months, renewable""",
    ),
    _policy(
        "centene_sglt2_2024", "Centene",
        "SGLT2 Inhibitors", "sglt2", "type2_diabetes", "CEN-SGLT2-2024",
        text="""POLICY CEN-SGLT2-2024: SGLT2 INHIBITORS
Payer: Centene

COVERED AGENTS: empagliflozin, dapagliflozin
CRITERIA: T2DM with metformin failure; or HFrEF; or CKD per label
AUTHORIZATION: 12 months, renewable""",
    ),
    _policy(
        "kaiser_sglt2_2024", "Kaiser",
        "SGLT2 Inhibitors", "sglt2", "type2_diabetes", "KAI-SGLT2-2024",
        text="""POLICY KAI-SGLT2-2024: SGLT2 INHIBITORS
Payer: Kaiser

COVERED AGENTS: empagliflozin, dapagliflozin
INTEGRATED CARE: T2DM managed within Kaiser, metformin failure required
HF/CKD: Covered per FDA indications within Kaiser cardiology/nephrology
PREFERRED: empagliflozin
AUTHORIZATION: 12 months, renewable""",
    ),
]


# ═══════════════════════════════════════════════════════════════════════════════
# COMBINED LIST
# ═══════════════════════════════════════════════════════════════════════════════

PAYER_POLICIES = (
    _PSORIASIS_POLICIES
    + _RA_POLICIES
    + _GLP1_POLICIES
    + _MS_POLICIES
    + _ONCOLOGY_POLICIES
    + _SGLT2_POLICIES
)


async def download(out_dir: Path) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "payer_policies.json").write_text(json.dumps(PAYER_POLICIES, indent=2))
    log.info("payer_policies.complete", total=len(PAYER_POLICIES))
    return PAYER_POLICIES
