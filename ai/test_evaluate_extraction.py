"""Tests for the ground-truth evaluation harness (scoring maths + a simulated end-to-end run).
The OCR reader is FAKE: this verifies the harness and the re-read decision path, not EasyOCR accuracy."""
import os, sys, tempfile
import cv2
import numpy as np

import ocr
import extract_cli as ec
import evaluate_extraction as ev

W, H = 800, 400


def box(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


class FakeReader:
    """Page calls: bilingual-style layout where the name VALUE is misread ('UGoll').
    Region calls (allowlist given): a clean read, as a close crop of the value would give."""
    PAGE = [
        ((20, 100, 220, 120), "NAME OF THE CANDIDATE", 0.90),
        ((240, 100, 330, 122), "UGoll", 0.59),
        ((20, 160, 220, 180), "PERMANENT REGISTER NO.", 0.90),
        ((240, 160, 420, 182), "XM23R2195306000", 0.90),
        ((20, 220, 200, 240), "TOTAL MARKS", 0.90),
        ((240, 220, 300, 242), "449", 0.95),
    ]

    def readtext(self, img, **kw):
        if "allowlist" in kw:
            return [(box(0, 0, 160, 20), "MOHAN RAJ", 0.80)]
        s = img.shape[1] / float(W)
        return [(box(*[int(v * s) for v in r]), t, c) for r, t, c in self.PAGE]


def test_scoring_maths():
    assert ev.levenshtein("KITTEN", "SITTING") == 3 and ev.cer("UGOLL", "MOHAN RAJ") > 0.7
    assert ev.normalize("total_marks", "0449") == "449" and ev.normalize("candidate_name", " Mohan  Raj. ") == "MOHAN RAJ"
    sc = ev.score_fields({"candidate_name": "UGoll", "field_status": {"candidate_name": "CONFIDENT"}, "total_marks": "449"},
                         {"candidate_name": "MOHAN RAJ", "total_marks": "449"})
    assert sc["candidate_name"]["exact"] is False and sc["candidate_name"]["confidently_wrong"] is True
    assert sc["total_marks"]["exact"] is True
    agg = ev.aggregate([sc, sc])
    assert agg["candidate_name"]["exact"] == 0 and agg["total_marks"]["exact_rate"] == 1.0 and "roll_number" not in agg
    print("  [PASS] Scoring: normalisation, CER, exact match, confidently-wrong flag and aggregation behave as specified.")


def test_simulated_end_to_end_run():
    fake = FakeReader()
    ocr.reader, ec.OCR_READER = fake, fake
    path = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
    cv2.imwrite(path, np.full((H, W, 3), 255, np.uint8))
    truth = {"candidate_name": "MOHAN RAJ", "registration_number": "XM23R2195306000", "total_marks": "449"}
    try:
        scores = ev.evaluate_one(path, truth)
    finally:
        os.unlink(path)
    assert scores["merged"]["candidate_name"]["exact"] is False and scores["merged"]["candidate_name"]["status"] == "UNCERTAIN"
    final = scores["merged+name_reread"]["candidate_name"]
    assert final["exact"] is True and final["status"] == "CONFIDENT", final
    for strat, sc in scores.items():
        if "error" in str(sc):
            continue
        assert not any(r["confidently_wrong"] for r in sc.values()), (strat, sc)
        assert sc["registration_number"]["exact"] and sc["total_marks"]["exact"], strat
    print("  [PASS] Simulated run: whole-page read stays UNCERTAIN ('UGoll'); name re-read yields a CONFIDENT exact name; no strategy is confidently wrong.")


if __name__ == "__main__":
    print("=== Evaluation harness tests ===")
    failed = 0
    for t in (test_scoring_maths, test_simulated_end_to_end_run):
        try: t()
        except Exception as e: failed += 1; print(f"  [FAIL] {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{2 - failed}/2 passed"); sys.exit(1 if failed else 0)
