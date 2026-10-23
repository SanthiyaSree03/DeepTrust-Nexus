import json
import re
import sys

# Test suite for Phase 3A extraction and arithmetic verification logic in ai/extract_cli.py
from extract_cli import parse_extracted_fields

def run_tests():
    print("=== Phase 3A Python OCR & Parsing Test Suite ===")

    # Test 1: Synthetic CBSE Class 10 with Grading Scheme (CGPA)
    raw_cbse_10 = [
        {"text": "CENTRAL BOARD OF SECONDARY EDUCATION", "confidence": 0.95},
        {"text": "SECONDARY SCHOOL EXAMINATION", "confidence": 0.92},
        {"text": "NAME OF THE CANDIDATE", "confidence": 0.90},
        {"text": "ANANYA VERMA", "confidence": 0.94},
        {"text": "ROLL NO : 87654321", "confidence": 0.91},
        {"text": "CERTIFICATE NO: CBSE202201", "confidence": 0.89},
        {"text": "MARCH 2022", "confidence": 0.88},
        {"text": "CUMULATIVE GRADE POINT AVERAGE CGPA 9.2", "confidence": 0.85},
        {"text": "ENGLISH", "confidence": 0.90},
        {"text": "091", "confidence": 0.85},
        {"text": "MATHEMATICS", "confidence": 0.88},
        {"text": "095", "confidence": 0.84},
        {"text": "SCIENCE", "confidence": 0.87},
        {"text": "090", "confidence": 0.83}
    ]
    parsed_1 = parse_extracted_fields(raw_cbse_10)
    assert parsed_1["board"] == "Central Board of Secondary Education (CBSE)"
    assert parsed_1["course"] == "Secondary School Leaving Certificate (10th)"
    assert parsed_1["candidate_name"] == "ANANYA VERMA"
    assert parsed_1["registration_number"] == "87654321"
    assert parsed_1["examination_year"] == "MARCH 2022"
    assert parsed_1["arithmetic_check"]["applicable"] == False
    assert parsed_1["arithmetic_check"]["status"] == "NOT_APPLICABLE"
    assert parsed_1["field_status"]["candidate_name"] == "CONFIDENT"
    assert parsed_1["field_status"]["board"] == "CONFIDENT"
    print("  [PASS] Test 1: CBSE Class 10 CGPA grading scheme correctly parsed & direct sum marked NOT_APPLICABLE.")

    # Test 2: Synthetic Tamil Nadu Class 12 with Valid Marks Sum
    raw_tn_12_valid = [
        {"text": "STATE BOARD OF SCHOOL EXAMINATIONS, TAMILNADU", "confidence": 0.92},
        {"text": "HIGHER SECONDARY COURSE CERTIFICATE", "confidence": 0.89},
        {"text": "NAME OF THE CANDIDATE", "confidence": 0.95},
        {"text": "KUMAR R", "confidence": 0.91},
        {"text": "PERMANENT REG NO : 2414123456", "confidence": 0.90},
        {"text": "CERTIFICATE NO : 12345678", "confidence": 0.92},
        {"text": "MAR 2024", "confidence": 0.85},
        {"text": "TAMIL", "confidence": 0.89},
        {"text": "085", "confidence": 0.88},
        {"text": "ENGLISH", "confidence": 0.90},
        {"text": "080", "confidence": 0.85},
        {"text": "PHYSICS", "confidence": 0.86},
        {"text": "090", "confidence": 0.87},
        {"text": "CHEMISTRY", "confidence": 0.88},
        {"text": "085", "confidence": 0.86},
        {"text": "MATHEMATICS", "confidence": 0.91},
        {"text": "090", "confidence": 0.89},
        {"text": "TOTAL MARKS", "confidence": 0.93},
        {"text": "0430", "confidence": 0.95} # 85+80+90+85+90 = 430
    ]
    parsed_2 = parse_extracted_fields(raw_tn_12_valid)
    assert parsed_2["board"] == "State Board of School Examinations, Tamil Nadu"
    assert parsed_2["candidate_name"] == "KUMAR R"
    assert parsed_2["certificate_number"] == "12345678"
    assert parsed_2["registration_number"] == "2414123456"
    assert parsed_2["total_marks"] == "430"
    assert parsed_2["arithmetic_check"]["applicable"] == True
    assert parsed_2["arithmetic_check"]["consistent"] == True
    assert parsed_2["arithmetic_check"]["status"] == "VERIFIED_CONSISTENT"
    assert parsed_2["arithmetic_check"]["calculated_sum"] == 430
    print("  [PASS] Test 2: Tamil Nadu Class 12 with matching marks sum (430 == 430) VERIFIED_CONSISTENT.")

    # Test 3: Synthetic Tampered Marks Total Mismatch
    raw_tampered = [
        {"text": "CENTRAL BOARD OF SECONDARY EDUCATION", "confidence": 0.95},
        {"text": "SENIOR SCHOOL CERTIFICATE EXAMINATION", "confidence": 0.92},
        {"text": "NAME OF THE CANDIDATE", "confidence": 0.90},
        {"text": "PRIYANKA SEN", "confidence": 0.91},
        {"text": "ENGLISH", "confidence": 0.90},
        {"text": "080", "confidence": 0.85},
        {"text": "PHYSICS", "confidence": 0.86},
        {"text": "080", "confidence": 0.87},
        {"text": "CHEMISTRY", "confidence": 0.88},
        {"text": "080", "confidence": 0.86},
        {"text": "TOTAL MARKS", "confidence": 0.90},
        {"text": "0300", "confidence": 0.92} # Actual sum is 240, but recorded total is forged to 300
    ]
    parsed_3 = parse_extracted_fields(raw_tampered)
    assert parsed_3["arithmetic_check"]["applicable"] == True
    assert parsed_3["arithmetic_check"]["consistent"] == False
    assert parsed_3["arithmetic_check"]["status"] == "ARITHMETIC_MISMATCH"
    assert parsed_3["arithmetic_check"]["calculated_sum"] == 240
    assert parsed_3["arithmetic_check"]["recorded_total"] == 300
    print("  [PASS] Test 3: Tampered marks sum (240 != 300) properly detected as ARITHMETIC_MISMATCH.")

    # Test 4: Field Status Classification
    raw_partial = [
        {"text": "CENTRAL BOARD OF SECONDARY EDUCATION", "confidence": 0.95},
        {"text": "NO OTHER DETAILS RECOGNIZED", "confidence": 0.10}
    ]
    parsed_4 = parse_extracted_fields(raw_partial)
    assert parsed_4["field_status"]["board"] == "CONFIDENT"
    assert parsed_4["field_status"]["candidate_name"] == "MISSING"
    assert parsed_4["field_status"]["certificate_number"] == "MISSING"
    assert parsed_4["field_status"]["total_marks"] == "MISSING"
    print("  [PASS] Test 4: Field confidence properly classifies CONFIDENT vs MISSING fields.")

    # Test 5: Candidate Name Confidence Propagation and UNCERTAIN Classification
    raw_low_conf_name = [
        {"text": "NAME OF THE CANDIDATE", "confidence": 0.88},
        {"text": "nilina Sree", "confidence": 0.06},
        {"text": "ROLL NO : 12345678", "confidence": 0.90}
    ]
    parsed_5 = parse_extracted_fields(raw_low_conf_name)
    assert parsed_5["candidate_name"] == "nilina Sree"
    assert parsed_5["candidate_name_confidence"] == 0.06
    assert parsed_5["candidate_name_raw"] == "nilina Sree"
    assert parsed_5["field_status"]["candidate_name"] == "UNCERTAIN", (
        f"Expected UNCERTAIN for 0.06 confidence, got {parsed_5['field_status']['candidate_name']}"
    )
    print("  [PASS] Test 5: 6%-confidence name correctly marked UNCERTAIN (not CONFIDENT) and raw OCR preserved.")

    # Test 6: High-Confidence Candidate Name correctly marked CONFIDENT
    raw_high_conf_name = [
        {"text": "NAME OF THE CANDIDATE", "confidence": 0.88},
        {"text": "SANTHIYA SREE S", "confidence": 0.95},
        {"text": "ROLL NO : 12345678", "confidence": 0.90}
    ]
    parsed_6 = parse_extracted_fields(raw_high_conf_name)
    assert parsed_6["candidate_name"] == "SANTHIYA SREE S"
    assert parsed_6["candidate_name_confidence"] == 0.95
    assert parsed_6["field_status"]["candidate_name"] == "CONFIDENT"
    print("  [PASS] Test 6: 95%-confidence name correctly marked CONFIDENT.")

    # Test 7: Real Marksheet Observed Failure Regression (ai/santhiya 12th ms.jpeg)
    # Verifies that low-confidence corrupted name (0.06) is cleaned without hardcoding,
    # raw OCR text is preserved, field_status is UNCERTAIN, and clear numeric fields remain CONFIDENT.
    raw_santhiya_observed = [
        {"text": "36260174", "confidence": 1.0, "box": [[313, 34], [377, 34], [377, 50], [313, 50]]},
        {"text": "STATE Board Of SchOoL EXAMINANIONS; TamilMadu", "confidence": 0.1},
        {"text": "Hioher secondart Colre - Seconid Year Mark 5", "confidence": 0.05},
        {"text": "Geutr  uue/neoF TFeCIDIL", "confidence": 0.0},
        {"text": "Ja @ 0", "confidence": 0.11},
        {"text": "84nilina Sree $", "confidence": 0.06},
        {"text": "2414265216", "confidence": 0.79},
        {"text": "IoialMaRES ;", "confidence": 0.12},
        {"text": "0527", "confidence": 1.0}
    ]
    parsed_7 = parse_extracted_fields(raw_santhiya_observed)
    assert parsed_7["candidate_name"] == "nilina Sree", f"Expected cleaned 'nilina Sree', got {parsed_7['candidate_name']}"
    assert parsed_7["candidate_name_confidence"] == 0.06
    assert parsed_7["candidate_name_raw"] == "84nilina Sree $"
    assert parsed_7["field_status"]["candidate_name"] == "UNCERTAIN"
    assert parsed_7["certificate_number"] == "36260174"
    # No label ties this number to "certificate number": it is a candidate, not a confirmed value.
    assert parsed_7["field_status"]["certificate_number"] == "UNCERTAIN"
    assert parsed_7["certificate_number_source"] == "UNLABELLED_NUMERIC"
    assert parsed_7["registration_number"] == "2414265216"
    assert parsed_7["field_status"]["registration_number"] == "UNCERTAIN"  # unlabelled 10-digit number
    assert parsed_7["registration_source"] == "UNLABELLED_10_DIGIT"
    assert parsed_7["total_marks"] == "527"
    # The only anchor is a garbled label read at 0.12 confidence, and no total-in-words agrees.
    assert parsed_7["field_status"]["total_marks"] == "UNCERTAIN"
    assert parsed_7["board"] == "State Board of School Examinations, Tamil Nadu"
    assert parsed_7["course"] == "Higher Secondary Examination (12th)"
    print("  [PASS] Test 7: Real marksheet observed failure regression correctly extracts raw values, flags the name AND the unlabelled/weakly-anchored numeric fields as UNCERTAIN (a field being found is not the same as it being confirmed).")

    print("\nALL PHASE 3A PYTHON TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()


