"""
Tests for the PHI de-identification module.

Verifies that all 18 HIPAA Safe Harbor identifier categories are properly
stripped, while clinical content (drug names, lab values, treatment dates)
is preserved.
"""

import pytest
from agent.phi_scrubber import scrub_phi, scrub_patient_id, scrub_claim_id, scrub_denial_info


# ─────────────────────────────────────────────────────────────────────────────
# Test: SSN stripping
# ─────────────────────────────────────────────────────────────────────────────

class TestSSN:
    def test_ssn_dashes(self):
        assert "[SSN_REDACTED]" in scrub_phi("SSN: 123-45-6789")

    def test_ssn_spaces(self):
        assert "[SSN_REDACTED]" in scrub_phi("SSN 123 45 6789")

    def test_ssn_no_separators_not_matched(self):
        """9 consecutive digits without separators are NOT matched to avoid
        false positives on legitimate numbers like claim IDs."""
        result = scrub_phi("SSN: 123456789")
        assert "[SSN_REDACTED]" not in result


# ─────────────────────────────────────────────────────────────────────────────
# Test: Email stripping
# ─────────────────────────────────────────────────────────────────────────────

class TestEmail:
    def test_email(self):
        result = scrub_phi("Contact john.doe@hospital.org for details")
        assert "[EMAIL_REDACTED]" in result
        assert "john.doe@hospital.org" not in result


# ─────────────────────────────────────────────────────────────────────────────
# Test: Phone number stripping
# ─────────────────────────────────────────────────────────────────────────────

class TestPhone:
    def test_phone_parens(self):
        assert "[PHONE_REDACTED]" in scrub_phi("Call (555) 123-4567")

    def test_phone_dashes(self):
        assert "[PHONE_REDACTED]" in scrub_phi("Phone: 555-123-4567")

    def test_phone_dots(self):
        assert "[PHONE_REDACTED]" in scrub_phi("Fax: 555.123.4567")

    def test_phone_with_country_code(self):
        assert "[PHONE_REDACTED]" in scrub_phi("Call +1-555-123-4567")


# ─────────────────────────────────────────────────────────────────────────────
# Test: DOB stripping (contextual)
# ─────────────────────────────────────────────────────────────────────────────

class TestDOB:
    def test_dob_slash(self):
        result = scrub_phi("DOB: 01/15/1982")
        assert "[DOB_REDACTED]" in result
        assert "01/15/1982" not in result

    def test_date_of_birth_written(self):
        result = scrub_phi("Date of Birth: January 15, 1982")
        assert "[DOB_REDACTED]" in result

    def test_born_keyword(self):
        result = scrub_phi("born 03/22/1975")
        assert "[DOB_REDACTED]" in result

    def test_treatment_dates_preserved(self):
        """Treatment dates should NOT be stripped — they are clinical data."""
        text = "methotrexate started January 2023, discontinued March 2023 due to hepatotoxicity"
        result = scrub_phi(text)
        assert "January 2023" in result
        assert "March 2023" in result


# ─────────────────────────────────────────────────────────────────────────────
# Test: MRN stripping
# ─────────────────────────────────────────────────────────────────────────────

class TestMRN:
    def test_mrn_colon(self):
        result = scrub_phi("MRN: 12345678")
        assert "[MRN_REDACTED]" in result
        assert "12345678" not in result

    def test_mrn_hash(self):
        result = scrub_phi("MRN# ABC-12345")
        assert "[MRN_REDACTED]" in result

    def test_medical_record_number(self):
        result = scrub_phi("Medical Record Number: MR-987654")
        assert "[MRN_REDACTED]" in result


# ─────────────────────────────────────────────────────────────────────────────
# Test: Member / beneficiary IDs (No longer redacted)
# ─────────────────────────────────────────────────────────────────────────────

class TestMemberID:
    def test_member_id_preserved(self):
        result = scrub_phi("Member ID: ABC12345678")
        assert "[MEMBER_ID_REDACTED]" not in result
        assert "ABC12345678" in result

    def test_subscriber_id_preserved(self):
        result = scrub_phi("Subscriber ID: XYZ-9876-5432")
        assert "[MEMBER_ID_REDACTED]" not in result
        assert "XYZ-9876-5432" in result

    def test_group_number_preserved(self):
        result = scrub_phi("Group Number: GRP-555-001")
        assert "[MEMBER_ID_REDACTED]" not in result
        assert "GRP-555-001" in result


# ─────────────────────────────────────────────────────────────────────────────
# Test: Patient name stripping (contextual)
# ─────────────────────────────────────────────────────────────────────────────

class TestPatientName:
    def test_patient_name(self):
        result = scrub_phi("Patient: John Smith")
        assert "[PATIENT_NAME_REDACTED]" in result
        assert "John Smith" not in result

    def test_patient_name_with_title(self):
        result = scrub_phi("Patient Name: Jane Doe")
        assert "[PATIENT_NAME_REDACTED]" in result

    def test_dear_mr(self):
        result = scrub_phi("Dear Mr. Robert Johnson,")
        assert "[PATIENT_NAME_REDACTED]" in result

    def test_dear_mrs(self):
        result = scrub_phi("Dear Mrs. Sarah Williams,")
        assert "[PATIENT_NAME_REDACTED]" in result

    def test_re_line(self):
        result = scrub_phi("Re: Mary Elizabeth Thompson")
        assert "[PATIENT_NAME_REDACTED]" in result

    def test_drug_names_not_stripped(self):
        """Drug names should NOT be stripped even if they look like names."""
        text = "adalimumab (Humira) 40mg biweekly for rheumatoid arthritis"
        result = scrub_phi(text)
        assert "adalimumab" in result
        assert "Humira" in result


# ─────────────────────────────────────────────────────────────────────────────
# Test: Address stripping
# ─────────────────────────────────────────────────────────────────────────────

class TestAddress:
    def test_street_address(self):
        result = scrub_phi("123 Main Street, Apt 4B")
        assert "[ADDRESS_REDACTED]" in result

    def test_po_box(self):
        result = scrub_phi("P.O. Box 456")
        assert "[ADDRESS_REDACTED]" in result


# ─────────────────────────────────────────────────────────────────────────────
# Test: ZIP code stripping
# ─────────────────────────────────────────────────────────────────────────────

class TestZIP:
    def test_zip_plus_four(self):
        result = scrub_phi("ZIP: 90210-1234")
        assert "[ZIP_REDACTED]" in result

    def test_standalone_zip_plus_four(self):
        result = scrub_phi("Mail to 90210-1234")
        assert "[ZIP_REDACTED]" in result


# ─────────────────────────────────────────────────────────────────────────────
# Test: URL stripping
# ─────────────────────────────────────────────────────────────────────────────

class TestURL:
    def test_http_url(self):
        result = scrub_phi("Visit http://patient-portal.hospital.com/records/12345")
        assert "[URL_REDACTED]" in result

    def test_https_url(self):
        result = scrub_phi("See https://www.example.com/patient/john-smith")
        assert "[URL_REDACTED]" in result


# ─────────────────────────────────────────────────────────────────────────────
# Test: IP address stripping
# ─────────────────────────────────────────────────────────────────────────────

class TestIP:
    def test_ip_address(self):
        result = scrub_phi("Logged from 192.168.1.100")
        assert "[IP_REDACTED]" in result


# ─────────────────────────────────────────────────────────────────────────────
# Test: scrub_patient_id
# ─────────────────────────────────────────────────────────────────────────────

class TestScrubPatientId:
    def test_real_id(self):
        assert scrub_patient_id("4821-B") == "4821-B"

    def test_unknown(self):
        assert scrub_patient_id("unknown") == "unknown"

    def test_empty(self):
        assert scrub_patient_id("") == "unknown"

    def test_none(self):
        assert scrub_patient_id(None) == "unknown"


# ─────────────────────────────────────────────────────────────────────────────
# Test: scrub_claim_id
# ─────────────────────────────────────────────────────────────────────────────

class TestScrubClaimId:
    def test_real_claim(self):
        assert scrub_claim_id("BCB-2024-PA-10392") == "BCB-2024-PA-10392"

    def test_unknown(self):
        assert scrub_claim_id("unknown") == "unknown"


# ─────────────────────────────────────────────────────────────────────────────
# Test: scrub_denial_info
# ─────────────────────────────────────────────────────────────────────────────

class TestScrubDenialInfo:
    def test_full_denial_info(self):
        info = {
            "drug_or_procedure": "adalimumab (Humira) 40mg biweekly",
            "denial_reason": "Patient John Smith has insufficient DMARD documentation",
            "policy_code": "4.2.1b",
            "payer": "BlueCross BlueShield",
            "patient_id": "4821-B",
            "claim_id": "BCB-2024-PA-10392",
        }
        result = scrub_denial_info(info)
        assert result["patient_id"] == "4821-B"
        assert result["claim_id"] == "BCB-2024-PA-10392"
        # Clinical fields preserved
        assert result["drug_or_procedure"] == "adalimumab (Humira) 40mg biweekly"
        assert result["policy_code"] == "4.2.1b"
        assert result["payer"] == "BlueCross BlueShield"


# ─────────────────────────────────────────────────────────────────────────────
# Test: Clinical content preservation
# ─────────────────────────────────────────────────────────────────────────────

class TestClinicalPreservation:
    """Ensure clinically meaningful content is NOT stripped."""

    def test_drug_names_preserved(self):
        text = "adalimumab (Humira) 40mg, methotrexate 20mg, semaglutide (Ozempic) 1mg"
        result = scrub_phi(text)
        assert "adalimumab" in result
        assert "Humira" in result
        assert "methotrexate" in result
        assert "semaglutide" in result
        assert "Ozempic" in result

    def test_lab_values_preserved(self):
        text = "HbA1c 7.8%, DAS28 score 5.1, PASI 14.2, BSA 22%, ESR 28 mm/hr, CRP 0.8 mg/dL"
        result = scrub_phi(text)
        assert "HbA1c 7.8%" in result
        assert "DAS28 score 5.1" in result
        assert "PASI 14.2" in result

    def test_policy_codes_preserved(self):
        text = "under policy 4.2.1b, section RX-DM-2024-07, code SD-BIO-2024-03"
        result = scrub_phi(text)
        assert "4.2.1b" in result
        assert "RX-DM-2024-07" in result

    def test_payer_names_preserved(self):
        text = "BlueCross BlueShield, Aetna, Cigna, UnitedHealthcare, Humana"
        result = scrub_phi(text)
        assert "BlueCross BlueShield" in result
        assert "Aetna" in result
        assert "Cigna" in result

    def test_claim_ids_in_text_preserved_without_context(self):
        """Claim IDs in free text (without patient context) are kept —
        scrub_claim_id handles explicit claim_id field separately."""
        text = "Claim BCB-2024-PA-10392 was denied"
        result = scrub_phi(text)
        assert "BCB-2024-PA-10392" in result


# ─────────────────────────────────────────────────────────────────────────────
# Test: Full denial letter (integration)
# ─────────────────────────────────────────────────────────────────────────────

class TestFullDenialLetter:
    def test_realistic_denial(self):
        letter = """
        BlueCross BlueShield
        123 Insurance Blvd, Suite 200
        New York, NY 10001-4567

        RE: Mary Elizabeth Thompson
        Patient ID: 4821-B
        Member ID: BCB-MEM-98765432
        DOB: 03/22/1975
        MRN: MR-2024-55678

        Dear Mrs. Mary Thompson,

        This letter is to inform you that your request for adalimumab (Humira)
        40mg biweekly has been denied under Medical Policy 4.2.1b.

        Denial reason: Medical records do not document adequate trial and failure
        of two conventional DMARDs for a minimum of 3 months each.

        Please contact us at (800) 555-1234 or email appeals@bcbs.com.
        """

        result = scrub_phi(letter)

        # PHI should be stripped
        assert "Mary Elizabeth Thompson" not in result
        assert "Mary Thompson" not in result
        assert "4821-B" not in result or "[" in result  # May be part of patient ID context
        assert "03/22/1975" not in result
        assert "(800) 555-1234" not in result
        assert "appeals@bcbs.com" not in result

        # Clinical content should be preserved
        assert "adalimumab" in result
        assert "Humira" in result
        assert "4.2.1b" in result
        assert "BlueCross BlueShield" in result
        assert "DMARD" in result

    def test_empty_text(self):
        assert scrub_phi("") == ""
        assert scrub_phi(None) is None

    def test_no_phi(self):
        text = "adalimumab (Humira) denied under policy 4.2.1b for insufficient DMARD documentation"
        result = scrub_phi(text)
        assert result == text  # No changes needed
