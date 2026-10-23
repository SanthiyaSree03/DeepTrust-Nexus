"""
ai/test_marksheet_report_regression.py - Regression tests for marksheet diagnostic reporting

Verifies that print_evaluation_summary() properly handles all QR detection states,
payload types, and readability flags without raising NameError or crashing.
"""

import os
import sys
import io
from contextlib import redirect_stdout

# Ensure ai directory is on python path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from test_marksheet_pipeline import print_evaluation_summary


def _create_mock_result(detection_state, payload_type, qr_fields=None, detected=True):
    """Builds a minimal mock result matching evaluate_marksheet schema."""
    return {
        "image_path": "mock_marksheet.jpeg",
        "quality": {
            "width": 1118,
            "height": 1599,
            "sharpness": 1867.4,
            "estimated_dpi": 135,
            "resolution_adequate": False,
            "character_height_adequate": False,
        },
        "ocr_metrics": {
            "total_boxes": 121,
            "average_confidence": 0.56,
            "average_confidence_percentage": "56.3%",
        },
        "extracted_fields": {
            "candidate_name": "LGoul",
            "candidate_name_confidence": 0.23,
            "candidate_name_raw": "LGoul",
            "certificate_number": "24299829",
            "registration_number": None,
            "total_marks": "449",
            "board": "State Board of School Examinations, Tamil Nadu",
            "course": "Higher Secondary Examination (12th)",
            "examination_year": "APR 2023",
            "field_status": {
                "candidate_name": "UNCERTAIN",
                "certificate_number": "UNCERTAIN",
                "registration_number": "MISSING",
                "total_marks": "UNCERTAIN",
                "board": "CONFIDENT",
                "course": "CONFIDENT",
                "examination_year": "CONFIDENT",
            },
        },
        "qr_analysis": {
            "detected": detected,
            "detection_state": detection_state,
            "payload_type": payload_type,
            "qr_fields": qr_fields,
        },
        "tamper_analysis": {
            "indicators": [],
            "review_recommended": False,
        },
    }


def test_decoded_external_url_unstructured():
    """Regression test: Decoded external URL with is_readable=False should NOT crash with NameError."""
    res = _create_mock_result(
        detection_state="DECODED_RECOGNIZED",
        payload_type="EXTERNAL_URL",
        qr_fields={
            "candidate_name": None,
            "registration_number": None,
            "certificate_number": None,
            "total_marks": None,
            "board": None,
            "course": None,
            "examination_year": None,
            "is_readable": False,
            "raw_attributes": {},
        },
    )
    buf = io.StringIO()
    with redirect_stdout(buf):
        print_evaluation_summary(res)
    output = buf.getvalue()

    assert "• QR Detected         : True" in output
    assert "• QR Detection State  : DECODED_RECOGNIZED" in output
    assert "• Payload Type        : EXTERNAL_URL" in output
    assert "• Payload Decodable   : YES (Decoded URL / unstructured payload)" in output
    assert "SECTION 4: AUTHENTICITY VERIFICATION STATUS & LIMITATIONS" in output
    print("  [PASS] Decoded external URL / unstructured payload handled correctly.")


def test_decoded_structured_credentials():
    """Test: Decoded QR with parsed structured credentials (is_readable=True)."""
    res = _create_mock_result(
        detection_state="DECODED_RECOGNIZED",
        payload_type="JSON_CREDENTIAL",
        qr_fields={
            "candidate_name": "PRIYA SHARMA",
            "registration_number": "9876543210",
            "certificate_number": "CERT-1234",
            "total_marks": "485",
            "board": "CBSE",
            "course": "Class X",
            "examination_year": "2023",
            "is_readable": True,
            "raw_attributes": {"name": "PRIYA SHARMA"},
        },
    )
    buf = io.StringIO()
    with redirect_stdout(buf):
        print_evaluation_summary(res)
    output = buf.getvalue()

    assert "• Payload Decodable   : YES (Structured student credentials parsed)" in output
    print("  [PASS] Decoded structured student credentials handled correctly.")


def test_detected_unreadable_qr():
    """Test: Visually detected QR with unreadable bitstream."""
    res = _create_mock_result(
        detection_state="DETECTED_UNREADABLE",
        payload_type="UNREADABLE_IMAGE",
        qr_fields={"is_readable": False},
    )
    buf = io.StringIO()
    with redirect_stdout(buf):
        print_evaluation_summary(res)
    output = buf.getvalue()

    assert "• Payload Decodable   : NO (Visually detected, but unreadable bitstream at current scan resolution)" in output
    print("  [PASS] Detected unreadable QR handled correctly.")


def test_not_detected_qr():
    """Test: Document without any detected QR."""
    res = _create_mock_result(
        detection_state="NOT_DETECTED",
        payload_type="NONE",
        qr_fields={"is_readable": False},
        detected=False,
    )
    buf = io.StringIO()
    with redirect_stdout(buf):
        print_evaluation_summary(res)
    output = buf.getvalue()

    assert "• QR Detected         : False" in output
    assert "• Payload Decodable   : N/A (No QR detected on document)" in output
    print("  [PASS] Non-detected QR handled correctly.")


def test_missing_or_none_qr_fields():
    """Test resilience against missing or None qr_fields."""
    res = _create_mock_result(
        detection_state="DECODED",
        payload_type="EXTERNAL_URL",
        qr_fields=None,
    )
    buf = io.StringIO()
    with redirect_stdout(buf):
        print_evaluation_summary(res)
    output = buf.getvalue()

    assert "• Payload Decodable   : YES (Decoded URL / unstructured payload)" in output
    print("  [PASS] Missing/None qr_fields handled safely without exceptions.")


def test_error_result_handling():
    """Test graceful handling of error return dictionary."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        print_evaluation_summary({"error": "Could not load image at invalid.jpg"})
    output = buf.getvalue()

    assert "Error: Could not load image at invalid.jpg" in output
    print("  [PASS] Error result dictionary handled safely.")


def run_all_tests():
    print("=== Marksheet Evaluation Summary Reporting Regression Suite ===")
    test_decoded_external_url_unstructured()
    test_decoded_structured_credentials()
    test_detected_unreadable_qr()
    test_not_detected_qr()
    test_missing_or_none_qr_fields()
    test_error_result_handling()
    print("\nAll 6 reporting regression tests passed successfully!")


if __name__ == "__main__":
    run_all_tests()
