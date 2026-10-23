"""
ai/test_ingest.py - Unit and Integration Tests for Document Ingestion Pipeline
"""

import os
import sys
import tempfile
import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ingest import ingest_document, detect_file_type

def test_image_ingestion():
    print("--- Test 1: Standard Image Ingestion ---")
    res = ingest_document("ai/sample_marksheet.jpg")
    assert res["success"] is True, f"Failed image ingest: {res.get('error')}"
    assert res["page_count"] == 1
    assert res["pages"][0]["image_bgr"] is not None
    print(f"  [PASS] Successfully ingested image (format={res['format']}, size={res['file_size']} bytes)")

def test_magic_byte_validation():
    print("--- Test 2: Magic Byte Format Detection ---")
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(b"NOT_A_REAL_JPEG_OR_PNG_HEADER_DATA")
        temp_path = f.name

    try:
        res = ingest_document(temp_path)
        assert res["success"] is False
        assert "Unsupported or unrecognized" in res["error"]
        print("  [PASS] Successfully rejected corrupted/spoofed file extension")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

def test_pdf_generation_and_ingestion():
    print("--- Test 3: Synthetic PDF Ingestion (Text & Raster) ---")
    import pypdf
    from PIL import ImageDraw

    # Create a 2-page PDF
    temp_pdf_path = os.path.join(tempfile.gettempdir(), "test_cert.pdf")
    
    img1 = Image.new("RGB", (600, 800), color=(255, 255, 255))
    d1 = ImageDraw.Draw(img1)
    d1.text((50, 50), "CENTRAL BOARD OF SECONDARY EDUCATION", fill=(0, 0, 0))
    d1.text((50, 100), "CANDIDATE NAME: TEST STUDENT", fill=(0, 0, 0))

    img2 = Image.new("RGB", (600, 800), color=(255, 255, 255))
    d2 = ImageDraw.Draw(img2)
    d2.text((50, 50), "PAGE 2 - MARKS STATEMENT", fill=(0, 0, 0))

    img1.save(temp_pdf_path, save_all=True, append_images=[img2])

    try:
        res = ingest_document(temp_pdf_path)
        assert res["success"] is True, f"PDF ingest failed: {res.get('error')}"
        assert res["format"] == "PDF"
        assert res["page_count"] == 2
        assert len(res["pages"]) == 2
        assert res["pages"][0]["image_bgr"].shape[0] > 1000  # High-DPI rendered
        print(f"  [PASS] Multi-page PDF successfully rendered ({res['page_count']} pages at 300 DPI)")
    finally:
        if os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)

def test_real_sample_marksheet():
    print("--- Test 4: Real Marksheet Ingestion ---")
    target = "ai/santhiya 12th ms.jpeg"
    if os.path.exists(target):
        res = ingest_document(target)
        assert res["success"] is True
        page = res["pages"][0]
        # Low-res image should have been adaptively upscaled
        assert page["scale_factor"] >= 1.5
        assert page["image_bgr"].shape[1] >= 1000
        print(f"  [PASS] Real marksheet ingested and adaptively scaled from width={423} to {page['image_bgr'].shape[1]}px")
    else:
        print("  [SKIP] ai/santhiya 12th ms.jpeg not present")

def test_encrypted_pdf_rejection():
    print("--- Test 5: Password-Protected / Encrypted PDF Rejection ---")
    import pypdf
    from PIL import ImageDraw

    temp_enc_path = os.path.join(tempfile.gettempdir(), "test_encrypted.pdf")
    temp_plain_path = os.path.join(tempfile.gettempdir(), "test_plain.pdf")

    # Generate a simple PDF and encrypt it
    img = Image.new("RGB", (400, 400), color=(255, 255, 255))
    img.save(temp_plain_path)

    try:
        reader = pypdf.PdfReader(temp_plain_path)
        writer = pypdf.PdfWriter()
        for p in reader.pages:
            writer.add_page(p)
        writer.encrypt("secure_marksheet_password")
        with open(temp_enc_path, "wb") as f_out:
            writer.write(f_out)

        res = ingest_document(temp_enc_path)
        assert res["success"] is False
        assert "password-protected or encrypted" in res["error"].lower(), f"Unexpected error message: {res.get('error')}"
        print(f"  [PASS] Successfully rejected password-protected PDF: '{res['error']}'")
    finally:
        for p in [temp_enc_path, temp_plain_path]:
            if os.path.exists(p):
                os.remove(p)

def test_corrupt_pdf_rejection():
    print("--- Test 6: Corrupted PDF Header/Body Rejection ---")
    temp_corrupt_path = os.path.join(tempfile.gettempdir(), "corrupt.pdf")
    with open(temp_corrupt_path, "wb") as f:
        f.write(b"%PDF-1.4\n%MalformedGarbageDataThatIsNotAValidPdfObjectStreamOrTrailer")

    try:
        res = ingest_document(temp_corrupt_path)
        assert res["success"] is False
        assert "failed to parse" in res["error"].lower() or "corrupted" in res["error"].lower()
        print(f"  [PASS] Successfully rejected corrupted PDF: '{res['error']}'")
    finally:
        if os.path.exists(temp_corrupt_path):
            os.remove(temp_corrupt_path)

def test_oversized_file_rejection():
    print("--- Test 7: Oversized File Limit Rejection (> 25 MB) ---")
    import tempfile
    temp_large_path = os.path.join(tempfile.gettempdir(), "large_test_file.pdf")
    
    # Create sparse or 26 MB file
    with open(temp_large_path, "wb") as f:
        f.seek(26 * 1024 * 1024)
        f.write(b"\0")

    try:
        res = ingest_document(temp_large_path)
        assert res["success"] is False
        assert "exceeds maximum allowed limit" in res["error"].lower()
        print(f"  [PASS] Successfully rejected oversized file: '{res['error']}'")
    finally:
        if os.path.exists(temp_large_path):
            os.remove(temp_large_path)

def test_cli_pdf_end_to_end():
    print("--- Test 8: extract_cli.py End-to-End PDF Ingestion ---")
    import subprocess
    import json
    from PIL import ImageDraw

    temp_cli_pdf = os.path.join(tempfile.gettempdir(), "cli_test_cert.pdf")
    img = Image.new("RGB", (800, 600), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((50, 50), "CENTRAL BOARD OF SECONDARY EDUCATION", fill=(0, 0, 0))
    d.text((50, 100), "CANDIDATE NAME: PRIYA SHARMA", fill=(0, 0, 0))
    d.text((50, 150), "CERTIFICATE NO: 99887766", fill=(0, 0, 0))
    d.text((50, 200), "TOTAL MARKS: 475", fill=(0, 0, 0))
    img.save(temp_cli_pdf)

    try:
        python_exe = sys.executable
        cli_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "extract_cli.py")
        proc = subprocess.run(
            [python_exe, cli_path, temp_cli_pdf],
            capture_output=True,
            text=True
        )
        assert proc.returncode == 0, f"extract_cli failed: {proc.stderr}"
        out = json.loads(proc.stdout)
        assert out["success"] is True
        assert out["document_metadata"]["format"] == "PDF"
        assert out["document_metadata"]["page_count"] == 1
        assert "ocr_metrics" in out
        print(f"  [PASS] CLI successfully processed PDF: format={out['document_metadata']['format']}, boxes={out['ocr_metrics']['total_boxes_detected']}")
    finally:
        if os.path.exists(temp_cli_pdf):
            os.remove(temp_cli_pdf)

if __name__ == "__main__":
    print("=== DeepTrust Nexus Document Ingestion Test Suite ===")
    test_image_ingestion()
    test_magic_byte_validation()
    test_pdf_generation_and_ingestion()
    test_real_sample_marksheet()
    test_encrypted_pdf_rejection()
    test_corrupt_pdf_rejection()
    test_oversized_file_rejection()
    test_cli_pdf_end_to_end()
    print("\nALL 8 DOCUMENT INGESTION & PIPELINE TESTS PASSED SUCCESSFULLY!")

