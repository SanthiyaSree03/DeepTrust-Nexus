"""
Integration test: real extract_cli.main() -> JSON -> checks the response contract that the backend and
dashboard rely on. The OCR READER is FAKE (scripted layout), so this verifies plumbing and decision
logic (variants, merge, name re-read, diagnostics), NOT EasyOCR accuracy on real documents.
"""
import json, os, subprocess, sys, tempfile
import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DRIVER = os.path.join(HERE, "_fake_pipeline_driver.py")


def test_main_contract():
    path = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
    cv2.imwrite(path, np.full((1400, 1800, 3), 255, np.uint8))
    try:
        proc = subprocess.run([sys.executable, DRIVER, path], capture_output=True, text=True, timeout=180,
                              env={**os.environ, "DEEPTRUST_OCR_VARIANTS": "upscaled_clahe,bg_normalized"})
    finally:
        os.unlink(path)
    out = proc.stdout[proc.stdout.index("{"): proc.stdout.rindex("}") + 1]
    res = json.loads(out)
    assert res["success"] is True, res
    f = res["extracted_fields"]
    assert f["candidate_name"] == "MOHAN RAJ" and f["field_status"]["candidate_name"] == "CONFIDENT"
    assert f["candidate_name_source"] == "HEADER_REGION_REOCR"
    assert f["candidate_name_first_pass"]["raw"] == "UGoll", "first-pass read must be preserved for diagnostics"
    assert f["registration_number"] == "XM23R2195306000" and f["emis_id"] == "2414265216"
    assert f["field_status"]["registration_number"] == "CONFIDENT" and f["total_marks"] == "449"
    m = res["ocr_metrics"]
    assert m["variants_used"] == ["upscaled_clahe", "bg_normalized"] and "readable_text_confidence" in m
    assert m["languages_active"] == ["en"] and "language_note" in m
    d = res["ocr_diagnostics"]
    assert set(d["per_variant"]) == {"upscaled_clahe", "bg_normalized"} and d["name_region"]["best"]["agreement"] >= 2
    assert "pdf_signature_markers" in res["document_metadata"] and res["document_metadata"]["pdf_signature_markers"] is None
    assert res["raw_detections"] if "raw_detections" in res else True
    print("  [PASS] extract_cli.main(): fields, statuses, preserved first-pass read, variants, languages, diagnostics and PDF-marker key all present.")


if __name__ == "__main__":
    print("=== Pipeline integration (fake OCR reader) ===")
    try:
        test_main_contract(); print("\n1/1 passed")
    except Exception as e:
        print(f"  [FAIL] {type(e).__name__}: {e}"); sys.exit(1)
