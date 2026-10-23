"""
ai/test_marksheet_pipeline.py - Repeatable Validation Procedure for Marksheet Ingestion & Verification

Usage:
    python ai/test_marksheet_pipeline.py [path/to/marksheet.jpg|png|pdf]

If run without arguments, evaluates all existing workspace samples and prints
a comparative audit table against quality thresholds.
"""

import sys
import os
import json
import cv2
import numpy as np

# Ensure ai directory is on python path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from extract_cli import parse_extracted_fields, extract_candidate_name_generic, apply_name_region_reread
from ocr import extract_text
from qr_validator import analyze_certificate_qr
from tamper_detector import analyze_document_tampering


def inspect_image_quality(img_or_path):
    """
    Measures optical image characteristics: dimensions, aspect ratio,
    sharpness (Laplacian variance), and estimated DPI for standard A4 documents.
    """
    if isinstance(img_or_path, str):
        if not os.path.exists(img_or_path):
            return None
        img = cv2.imread(img_or_path)
    else:
        img = img_or_path

    if img is None:
        return None

    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    # A4 standard physical dimensions: 8.27 x 11.69 inches (210 x 297 mm)
    estimated_dpi = round(min(w / 8.27, h / 11.69))

    return {
        "width": w,
        "height": h,
        "sharpness": round(sharpness, 1),
        "estimated_dpi": estimated_dpi,
        "resolution_adequate": estimated_dpi >= 150,
        "character_height_adequate": estimated_dpi >= 150
    }


def evaluate_marksheet(image_path):
    """
    Runs the full extraction, QR, and tamper pipeline on an image or PDF page,
    returning structured verification metrics.
    """
    from ingest import ingest_document
    doc = ingest_document(image_path)
    if not doc.get("success"):
        return {"error": f"Could not load document at {image_path}: {doc.get('error')}"}

    primary_bgr = doc["pages"][0]["image_bgr"]
    quality = inspect_image_quality(primary_bgr)

    # 1. OCR extraction
    raw_detections = extract_text(primary_bgr)
    total_boxes = len(raw_detections)
    confidences = [d.get("confidence", 0.0) for d in raw_detections]
    avg_conf = sum(confidences) / total_boxes if total_boxes > 0 else 0.0

    # 2. Structured fields parsing
    extracted_fields = parse_extracted_fields(raw_detections)

    # 2b. Targeted re-reading of candidate name region (matches extract_cli)
    apply_name_region_reread(extracted_fields, primary_bgr, raw_detections)

    # 3. QR code analysis
    qr_analysis = analyze_certificate_qr(primary_bgr, ocr_fields=extracted_fields)

    # 4. Tampering heuristics
    tamper_analysis = analyze_document_tampering(
        primary_bgr,
        raw_detections=raw_detections,
        extracted_fields=extracted_fields
    )

    return {
        "image_path": image_path,
        "quality": quality,
        "ocr_metrics": {
            "total_boxes": total_boxes,
            "average_confidence": round(avg_conf, 2),
            "average_confidence_percentage": f"{avg_conf * 100:.1f}%"
        },
        "extracted_fields": extracted_fields,
        "qr_analysis": {
            "detected": qr_analysis.get("detected", False),
            "detection_state": qr_analysis.get("detection_state", "NOT_DETECTED"),
            "payload_type": qr_analysis.get("payload_classification", {}).get("payload_type", "NONE"),
            "qr_fields": qr_analysis.get("qr_fields", {})
        },
        "tamper_analysis": {
            "indicators": tamper_analysis.get("indicators_detected", []),
            "review_recommended": tamper_analysis.get("review_recommended", False)
        }
    }


def print_evaluation_summary(result):
    """Prints a structured summary separating OCR readability from authenticity verification."""
    if not result or "error" in result:
        print(f"Error: {result.get('error', 'Unknown evaluation error') if result else 'Empty result'}")
        return

    q = result["quality"]
    f = result["extracted_fields"]
    field_status = f.get("field_status", {})
    qr = result["qr_analysis"]
    ocr = result["ocr_metrics"]

    # Categorize extracted fields
    confident_fields = []
    uncertain_fields = []
    missing_fields = []

    field_keys = [
        ("Candidate Name", "candidate_name", f.get("candidate_name")),
        ("Certificate Number", "certificate_number", f.get("certificate_number")),
        ("Registration Number", "registration_number", f.get("registration_number")),
        ("Total Marks", "total_marks", f.get("total_marks")),
        ("Board / Authority", "board", f.get("board")),
        ("Course / Class", "course", f.get("course")),
        ("Examination Year", "examination_year", f.get("examination_year")),
    ]

    for label, key, val in field_keys:
        st = field_status.get(key, "MISSING" if val is None else "CONFIDENT")
        if st == "CONFIDENT":
            confident_fields.append((label, val))
        elif st == "UNCERTAIN":
            uncertain_fields.append((label, val, f.get(f"{key}_confidence")))
        else:
            missing_fields.append(label)

    print("=" * 75)
    print(f"MARKSHEET EVALUATION: {os.path.basename(result['image_path'])}")
    print("=" * 75)
    print("SECTION 1: OPTICAL SCAN QUALITY")
    print(f"  • Image Dimensions    : {q['width']} x {q['height']} px (~{q['estimated_dpi']} DPI)")
    print(f"  • Resolution Status   : {'ADEQUATE (>= 150 DPI)' if q['resolution_adequate'] else 'INSUFFICIENT (Low scan resolution < 150 DPI)'}")
    print(f"  • Sharpness Score     : {q['sharpness']} (Laplacian variance)")
    print(f"  • Total OCR Detections: {ocr['total_boxes']} boxes (Average Confidence: {ocr['average_confidence_percentage']})")
    print("-" * 75)
    print("SECTION 2: OCR READABILITY & FIELD EXTRACTION BREAKDOWN")
    print("  [CONFIDENT FIELDS]")
    if confident_fields:
        for lbl, val in confident_fields:
            print(f"    - {lbl:22}: {val}")
    else:
        print("    - (None)")

    print("  [UNCERTAIN FIELDS (Manual Inspection Required)]")
    if uncertain_fields:
        for item in uncertain_fields:
            lbl, val = item[0], item[1]
            conf = item[2] if len(item) > 2 and item[2] is not None else "N/A"
            raw_text = f.get("candidate_name_raw") if "Name" in lbl else ""
            raw_disp = f", Raw OCR: '{raw_text}'" if raw_text else ""
            print(f"    - {lbl:22}: '{val}' (Confidence: {conf}{raw_disp})")
    else:
        print("    - (None)")

    print("  [MISSING / UNDETECTED FIELDS]")
    if missing_fields:
        for lbl in missing_fields:
            print(f"    - {lbl}")
    else:
        print("    - (None)")

    # Subject Marks and Arithmetic Breakdown
    subj_marks = f.get("subject_marks", [])
    arith = f.get("arithmetic_check", {})
    print("\n  [SUBJECT-WISE MARKS]")
    if subj_marks:
        for sm in subj_marks:
            th_prac = ""
            if "theory" in sm or "practical" in sm:
                th_prac = f" (Theory: {sm.get('theory', '---')}, Practical: {sm.get('practical', '---')})"
            print(f"    - {sm.get('subject', 'UNKNOWN'):20}: {sm.get('marks')}{th_prac}")
    else:
        print("    - (No individual subjects extracted)")

    print(f"\n  [ARITHMETIC CONSISTENCY]")
    print(f"    • Status      : {arith.get('status', 'N/A')}")
    print(f"    • Consistent  : {arith.get('consistent', 'N/A')}")
    if arith.get("calculated_sum") is not None:
        print(f"    • Sum vs Total: Calculated {arith.get('calculated_sum')} vs Recorded {arith.get('recorded_total')} (Diff: {arith.get('difference', 0)})")
    print(f"    • Details     : {arith.get('details', 'N/A')}")

    print("-" * 75)
    print("SECTION 3: QR CODE DETECTION & CLASSIFICATION")
    print(f"  • QR Detected         : {qr['detected']}")
    print(f"  • QR Detection State  : {qr['detection_state']}")
    print(f"  • Payload Type        : {qr['payload_type']}")
    readable_qr = bool((qr.get("qr_fields") or {}).get("is_readable", False))
    if qr["detection_state"] in ["DECODED", "DECODED_RECOGNIZED"]:
        decode_disp = "YES (Structured student credentials parsed)" if readable_qr else "YES (Decoded URL / unstructured payload)"
    elif qr["detection_state"] == "DETECTED_UNREADABLE":
        decode_disp = "NO (Visually detected, but unreadable bitstream at current scan resolution)"
    else:
        decode_disp = "N/A (No QR detected on document)"
    print(f"  • Payload Decodable   : {decode_disp}")

    print("-" * 75)
    print("SECTION 4: AUTHENTICITY VERIFICATION STATUS & LIMITATIONS")
    # Disclaimers ensuring clarity is never confused with authenticity
    print("  • Authentic Signature : NOT DETECTED (No offline cryptographic signature present)")
    print("  • Live Board Access   : NOT CONFIGURED (No query to live CBSE or State Board API)")
    print("  • Verification Status : REVIEW REQUIRED (Low scan clarity / lack of cryptographic proof)")
    print("  • Critical Policy     : High OCR confidence or a decodable QR code does NOT")
    print("                          establish real authenticity without cryptographic issuer trust.")
    print("=" * 75)



def main():
    if len(sys.argv) > 1:
        target = sys.argv[1]
        if not os.path.exists(target):
            print(f"Error: Target file not found: {target}")
            sys.exit(1)
        res = evaluate_marksheet(target)
        print_evaluation_summary(res)
    else:
        # Default: Evaluate all existing marksheet samples in ai/ directory
        samples = [
            os.path.join(CURRENT_DIR, "10th marksheet(ss).jpeg"),
            os.path.join(CURRENT_DIR, "santhiya 12th ms.jpeg"),
            os.path.join(CURRENT_DIR, "sample_marksheet.jpg"),
        ]

        print("\n" + "#" * 70)
        print("# DEEPTRUST NEXUS — REPEATABLE MARKSHEET VALIDATION PROCEDURE")
        print("#" * 70)

        for s in samples:
            if os.path.exists(s):
                res = evaluate_marksheet(s)
                print_evaluation_summary(res)
                print()



if __name__ == "__main__":
    main()
