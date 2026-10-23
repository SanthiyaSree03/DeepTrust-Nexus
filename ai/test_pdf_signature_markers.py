"""PDF embedded-signature MARKER detection (detection only; verification is not implemented)."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ingest import detect_pdf_signature_markers, ingest_document


def _write(data):
    f = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    f.write(data); f.close()
    return f.name


def test_markers():
    signed = _write(b"%PDF-1.7\n1 0 obj<</Type/Sig/Filter/Adobe.PPKLite/SubFilter/adbe.pkcs7.detached/ByteRange[0 100 200 300]/Contents<00>>>endobj\n%%EOF")
    plain = _write(b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF")
    lookalike = _write(b"%PDF-1.4\n(see /ByteRange documentation)\n%%EOF")   # words in text, no array / no sig dict
    try:
        r = detect_pdf_signature_markers(signed)
        assert r["detected"] is True and r["verified"] is False and "adbe.pkcs7.detached" in r["sub_filters"]
        assert detect_pdf_signature_markers(plain)["detected"] is False
        assert detect_pdf_signature_markers(lookalike)["detected"] is False
        assert detect_pdf_signature_markers("/nonexistent.pdf")["detected"] is False
    finally:
        for p in (signed, plain, lookalike):
            os.unlink(p)
    print("  [PASS] Signature structure is detected but never reported as verified; look-alike text and plain PDFs are not flagged.")


def test_image_has_no_pdf_markers():
    import numpy as np, cv2
    path = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
    cv2.imwrite(path, np.full((300, 400, 3), 255, np.uint8))
    try:
        res = ingest_document(path)
        assert res["success"] and res["pdf_signature_markers"] is None
    finally:
        os.unlink(path)
    print("  [PASS] Image uploads carry no PDF signature markers (a handwritten/printed signature is never reported here).")


if __name__ == "__main__":
    print("=== PDF signature marker tests ===")
    failed = 0
    for t in (test_markers, test_image_has_no_pdf_markers):
        try: t()
        except Exception as e: failed += 1; print(f"  [FAIL] {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{2 - failed}/2 passed"); sys.exit(1 if failed else 0)
