"""
ai/test_qr_validator.py - Comprehensive Unit Test Suite for QR Validator
------------------------------------------------------------------------
Tests QR detection, payload classification, field extraction, and OCR
cross-consistency checks without relying on live network access.
"""

import os
import sys
import numpy as np
import cv2
import qrcode

from qr_validator import (
    is_trusted_domain,
    classify_payload,
    parse_qr_fields,
    compare_qr_with_ocr,
    detect_and_decode_qr,
    analyze_certificate_qr
)

def run_tests():
    print("=== DeepTrust Nexus QR Validator Test Suite ===")

    # Test 1: Trusted vs Untrusted Domain Classification
    print("\n--- Test 1: Domain Classification & URL Security ---")
    assert is_trusted_domain("cbse.gov.in") == True
    assert is_trusted_domain("dge.tn.gov.in") == True
    assert is_trusted_domain("results.digilocker.gov.in") == True
    assert is_trusted_domain("apisetu.gov.in") == True
    # Spoof attempts
    assert is_trusted_domain("cbse.gov.in.attacker.com") == False
    assert is_trusted_domain("fake-digilocker.org") == False
    assert is_trusted_domain("cbse-verify.xyz") == False
    print("  [PASS] Domain security check correctly verifies official gov domains and rejects spoofed subdomains.")

    # Test 2: Payload Classification
    print("\n--- Test 2: Payload Classification ---")
    c1 = classify_payload("https://dge.tn.gov.in/verify?regno=2414265216&cert=36260174")
    assert c1["payload_type"] == "OFFICIAL_GOV_URL"
    assert c1["is_official_domain"] == True

    c2 = classify_payload("http://phishing-portal.com/marksheet?id=999")
    assert c2["payload_type"] == "EXTERNAL_URL"
    assert c2["is_official_domain"] == False
    assert "UNVERIFIED_THIRD_PARTY_DOMAIN" in c2["security_flags"]
    assert "INSECURE_HTTP_PROTOCOL" in c2["security_flags"]

    c3 = classify_payload("CBSE-MSTN-2024890123")
    assert c3["payload_type"] == "DIGILOCKER_URI"
    assert c3["is_official_domain"] == False  # a printable text pattern is not issuer evidence
    assert "UNVALIDATED_TEXT_PATTERN" in c3["security_flags"]

    c4 = classify_payload("REG:2414265216|NAME:SANTHIYA SREE S|TOTAL:527|CERT:36260174")
    assert c4["payload_type"] == "STRUCTURED_DELIMITED"

    c5 = classify_payload('{"name": "PRIYA SHARMA", "roll": "9876543210", "total": "485"}')
    assert c5["payload_type"] == "JSON_CREDENTIAL"

    c6 = classify_payload("eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3OCIsIm5hbWUiOiJLT05BIn0.abc123sig")
    assert c6["payload_type"] == "SIGNED_TOKEN"

    c7 = classify_payload("a9f8b4c2d1e038475628190384756201928374650192837465abcdef12345678")
    assert c7["payload_type"] == "ENCRYPTED_OR_OPAQUE_BLOB"
    print("  [PASS] Payload classifier correctly distinguishes all 7 structural payload types.")

    # Test 3: Field Parsing
    print("\n--- Test 3: Credential Field Extraction ---")
    fields_delim = parse_qr_fields(
        "REG:2414265216|NAME:SANTHIYA SREE S|TOTAL:527|CERT:36260174",
        {"payload_type": "STRUCTURED_DELIMITED"}
    )
    assert fields_delim["candidate_name"] == "SANTHIYA SREE S"
    assert fields_delim["registration_number"] == "2414265216"
    assert fields_delim["total_marks"] == "527"
    assert fields_delim["certificate_number"] == "36260174"

    fields_url = parse_qr_fields(
        "https://dge.tn.gov.in/verify?regno=1610468100&name=SARAVANAVEL+C&total=824",
        {"payload_type": "OFFICIAL_GOV_URL", "is_url": True}
    )
    assert fields_url["registration_number"] == "1610468100"
    assert fields_url["candidate_name"] == "SARAVANAVEL C"
    assert fields_url["total_marks"] == "824"
    print("  [PASS] Field parsing extracts candidate credentials from delimited text and query parameters.")

    # Test 4: QR-to-OCR Cross-Consistency: Matching Case
    print("\n--- Test 4: QR-to-OCR Consistency: Matching Credentials ---")
    ocr_consistent = {
        "candidate_name": "SANTHIYA SREE S",
        "registration_number": "2414265216",
        "total_marks": "527",
        "certificate_number": "36260174"
    }
    comp_match = compare_qr_with_ocr(fields_delim, ocr_consistent)
    assert comp_match["status"] == "CONSISTENT"
    assert comp_match["consistent"] == True
    assert len(comp_match["matches"]) == 4
    assert len(comp_match["discrepancies"]) == 0
    print("  [PASS] Matching credentials correctly reported as CONSISTENT.")

    # Test 5: QR-to-OCR Cross-Consistency: Copied QR Code / Data Discrepancy
    print("\n--- Test 5: QR-to-OCR Consistency: Copied QR Code Discrepancy ---")
    # QR belongs to Santhiya Sree S, but OCR visible text has an entirely different student name and marks
    ocr_conflict = {
        "candidate_name": "VIKRAM ADITYA",
        "registration_number": "9999999999",
        "total_marks": "350",
        "certificate_number": "36260174"
    }
    comp_conflict = compare_qr_with_ocr(fields_delim, ocr_conflict)
    assert comp_conflict["status"] == "DISCREPANCY_DETECTED"
    assert comp_conflict["consistent"] == False
    assert len(comp_conflict["discrepancies"]) >= 2
    # Check that candidate name discrepancy is explicitly noted
    assert any("Candidate name discrepancy" in d for d in comp_conflict["discrepancies"])
    assert any("Registration number discrepancy" in d for d in comp_conflict["discrepancies"])
    print("  [PASS] Copied QR code discrepancy successfully flagged with detailed evidence notes.")

    # Test 6: Image Detection & OpenCV Decoding on Synthetic Image
    print("\n--- Test 6: End-to-End Image Detection & Decoding ---")
    qr = qrcode.QRCode(box_size=8, border=4)
    test_data = "REG:1610468100|NAME:SARAVANAVEL C|TOTAL:824|CERT:11180882"
    qr.add_data(test_data)
    qr.make(fit=True)
    pil_img = qr.make_image(fill_color="black", back_color="white")
    np_img = np.array(pil_img.convert("RGB"))

    test_img_path = os.path.join(os.path.dirname(__file__), "scratch_test_qr.png")
    cv2.imwrite(test_img_path, cv2.cvtColor(np_img, cv2.COLOR_RGB2BGR))

    try:
        analysis = analyze_certificate_qr(
            test_img_path,
            ocr_fields={
                "candidate_name": "SARAVANAVEL C",
                "registration_number": "1610468100",
                "total_marks": "824",
                "certificate_number": "11180882"
            }
        )
        assert analysis["detected"] == True
        assert analysis["payload_classification"]["payload_type"] == "STRUCTURED_DELIMITED"
        assert analysis["consistency_check"]["status"] == "CONSISTENT"
        assert analysis["consistency_check"]["consistent"] == True
        print("  [PASS] End-to-end QR image detection, decoding, classification, and consistency passed!")
    finally:
        if os.path.exists(test_img_path):
            os.remove(test_img_path)

    # Test 7: Blurred / Low-Resolution Degraded QR (DETECTED_UNREADABLE)
    print("\n--- Test 7: Degraded / Blurred QR Image ---")
    qr_small = qrcode.QRCode(box_size=6, border=2)
    qr_small.add_data("https://cbse.gov.in/verify?id=TEST999")
    qr_small.make(fit=True)
    pil_small = qr_small.make_image(fill_color="black", back_color="white")
    np_small = np.array(pil_small.convert("RGB"))
    small_bgr = cv2.cvtColor(np_small, cv2.COLOR_RGB2BGR)

    # Downscale and apply blur to create realistic camera degradation
    down = cv2.resize(small_bgr, (60, 60), interpolation=cv2.INTER_AREA)
    blurred = cv2.GaussianBlur(down, (3, 3), 1.0)
    re_up = cv2.resize(blurred, (240, 240), interpolation=cv2.INTER_LINEAR)

    degraded_test_path = os.path.join(os.path.dirname(__file__), "scratch_test_degraded_qr.png")
    cv2.imwrite(degraded_test_path, re_up)

    try:
        det_deg = detect_and_decode_qr(degraded_test_path)
        assert det_deg["detected"] == True
        assert det_deg["detection_state"] in ["DETECTED_UNREADABLE", "DECODED"]
        analysis_deg = analyze_certificate_qr(degraded_test_path)
        assert analysis_deg["detected"] == True
        assert analysis_deg["detection_state"] in ["DETECTED_UNREADABLE", "DECODED", "DECODED_RECOGNIZED"]
        print("  [PASS] Degraded QR properly detected with appropriate state (never falsely marked missing).")
    finally:
        if os.path.exists(degraded_test_path):
            os.remove(degraded_test_path)

    # Test 8: Real Marksheet QR Detection Check
    print("\n--- Test 8: Real Marksheet QR Detection Verification ---")
    real_sample_path = os.path.join(os.path.dirname(__file__), "santhiya 12th ms.jpeg")
    if os.path.exists(real_sample_path):
        real_analysis = analyze_certificate_qr(real_sample_path)
        assert real_analysis["detected"] == True, "Real marksheet contains visible QR and must have detected=True"
        assert real_analysis["detection_state"] in ["DETECTED_UNREADABLE", "DECODED", "DECODED_RECOGNIZED"]
        print(f"  [PASS] Real marksheet QR verified: detected=True, state={real_analysis['detection_state']}")
    else:
        print("  [SKIP] santhiya 12th ms.jpeg not present")

    print("\n========================================================")
    print("ALL QR VALIDATOR UNIT TESTS PASSED SUCCESSFULLY!")
    print("========================================================")

if __name__ == "__main__":
    run_tests()

