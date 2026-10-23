"""
ai/test_tamper_detector.py - Unit Test Suite for Tamper Detection Engine
------------------------------------------------------------------------
Tests image forensics heuristics:
1. Clean synthetic document without anomalies.
2. Synthetic document with an edited / spliced patch.
3. Varying image quality / compression levels.
4. Missing or unreliable coordinate data.
5. Marks arithmetic mismatch detection.
6. Coexistence of QR analysis and Tamper analysis.
"""

import os
import sys
import numpy as np
import cv2

from tamper_detector import (
    analyze_compression_ela,
    analyze_text_alignment_and_font,
    analyze_edge_discontinuity,
    evaluate_arithmetic_forensics,
    analyze_document_tampering
)
from qr_validator import analyze_certificate_qr

def run_tests():
    print("=== DeepTrust Nexus Tamper Detector Test Suite ===")

    # Test 1: Clean Synthetic Document
    print("\n--- Test 1: Clean Synthetic Certificate Image ---")
    clean_img = np.ones((800, 600, 3), dtype=np.uint8) * 245
    # Draw consistent table headers and marks
    cv2.putText(clean_img, "CERTIFICATE OF MARKS", (100, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (20, 20, 20), 2)
    # 5 consistent marks (height ~20px, consistent baseline)
    clean_detections = []
    y_starts = [200, 250, 300, 350, 400]
    marks_vals = ["085", "080", "090", "085", "090"]
    for i, (yst, val) in enumerate(zip(y_starts, marks_vals)):
        cv2.putText(clean_img, val, (350, yst + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (15, 15, 15), 2)
        box = [[350, yst], [410, yst], [410, yst + 24], [350, yst + 24]]
        clean_detections.append({
            "text": val,
            "confidence": 0.95,
            "box": box
        })

    clean_fields = {
        "candidate_name": "SARAVANAVEL C",
        "total_marks": "430",
        "subject_marks": [{"subject": f"SUBJ_{i}", "marks": int(v)} for i, v in enumerate(marks_vals)],
        "arithmetic_check": {
            "applicable": True,
            "consistent": True,
            "calculated_sum": 430,
            "recorded_total": 430,
            "details": "Sum of 5 subject marks (430) matches recorded total (430)."
        }
    }

    res_clean = analyze_document_tampering(clean_img, clean_detections, clean_fields)
    assert res_clean["analysis_completed"] == True
    assert res_clean["review_recommended"] == False
    assert len(res_clean["indicators_detected"]) == 0
    print("  [PASS] Clean document has 0 tampering indicators; review_recommended is False.")

    # Test 2: Synthetic Spliced Region / Font Size Mismatch
    print("\n--- Test 2: Font Height & Alignment Discrepancy ---")
    tampered_detections = list(clean_detections)
    # One mark was pasted with a much larger font / box (height 55px vs normal 24px)
    tampered_detections[2] = {
        "text": "099",
        "confidence": 0.92,
        "box": [[350, 300], [450, 300], [450, 355], [350, 355]]  # height 55px vs 24px
    }

    res_font = analyze_text_alignment_and_font(tampered_detections)
    assert res_font["status"] == "COMPLETED"
    assert res_font["anomalies_detected"] == True
    assert any("differ" in f["note"] for f in res_font["findings"])
    print("  [PASS] Inconsistent font box height (55px vs 24px) correctly flagged as layout anomaly.")

    # Test 3: Marks Arithmetic Forensic Integration
    print("\n--- Test 3: Marks Arithmetic Forensic Discrepancy ---")
    tampered_fields = {
        "candidate_name": "SARAVANAVEL C",
        "total_marks": "500",  # Changed from 430 to 500
        "subject_marks": [{"subject": f"SUBJ_{i}", "marks": int(v)} for i, v in enumerate(marks_vals)],
        "arithmetic_check": {
            "applicable": True,
            "consistent": False,
            "calculated_sum": 430,
            "recorded_total": 500,
            "difference": -70,
            "details": "Sum of 5 subject marks (430) differs from recorded total (500) by -70."
        }
    }

    res_arithmetic = analyze_document_tampering(clean_img, clean_detections, tampered_fields)
    assert res_arithmetic["analysis_completed"] == True
    assert "MARKS_ARITHMETIC_MISMATCH" in res_arithmetic["indicators_detected"]
    assert res_arithmetic["review_recommended"] == True
    print("  [PASS] Arithmetic discrepancy flagged as high-severity indicator with review_recommended = True.")

    # Test 4: Missing or Unreliable Coordinate Data
    print("\n--- Test 4: Missing or Empty Coordinates Graceful Degradation ---")
    no_coord_detections = [{"text": "MATHS", "confidence": 0.8}, {"text": "95", "confidence": 0.9}]
    res_no_coords = analyze_document_tampering(clean_img, no_coord_detections, clean_fields)
    assert res_no_coords["analysis_completed"] == True
    # Layout check should gracefully report insufficient coordinates rather than crashing
    assert res_no_coords["module_results"]["layout_font_analysis"]["status"] == "INSUFFICIENT_COORDINATE_DATA"
    print("  [PASS] Missing coordinates gracefully handled with status INSUFFICIENT_COORDINATE_DATA.")

    # Test 5: Recompression & Quality Variation
    print("\n--- Test 5: Varying JPEG Quality Levels ---")
    # Save clean image at quality 70 (compressed) and run ELA
    success, low_q_buf = cv2.imencode(".jpg", clean_img, [cv2.IMWRITE_JPEG_QUALITY, 70])
    low_q_img = cv2.imdecode(low_q_buf, cv2.IMREAD_COLOR)
    ela_low_q = analyze_compression_ela(low_q_img, clean_detections)
    assert ela_low_q["status"] == "COMPLETED"
    print("  [PASS] Compressed image evaluated without crash; global ELA metrics recorded.")

    # Test 6: QR Analysis & Tamper Analysis Coexistence
    print("\n--- Test 6: QR & Tamper Analysis Side-by-Side ---")
    tmp_path = os.path.join(os.path.dirname(__file__), "scratch_clean_test.png")
    cv2.imwrite(tmp_path, clean_img)
    try:
        qr_out = analyze_certificate_qr(tmp_path, ocr_fields=clean_fields)
        tamper_out = analyze_document_tampering(tmp_path, clean_detections, clean_fields)

        assert "detected" in qr_out
        assert "analysis_completed" in tamper_out
        assert qr_out["detected"] == False  # No QR drawn on this image
        assert tamper_out["analysis_completed"] == True
        print("  [PASS] QR Analysis and Tamper Analysis coexist cleanly with distinct schemas.")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    print("\n========================================================")
    print("ALL TAMPER DETECTOR UNIT TESTS PASSED SUCCESSFULLY!")
    print("========================================================")

if __name__ == "__main__":
    run_tests()
