"""
Tests for the multi-variant OCR layer, safe language loading, the name-region re-reader and the
geometry/label-aware field mapping. All inputs are SYNTHETIC (fake OCR readers, synthetic images);
no real certificate data is used and EasyOCR recognition itself is NOT exercised here.
Run from ai/:  python test_ocr_pipeline.py
"""
import sys

import cv2
import numpy as np

import ocr
from extract_cli import parse_extracted_fields, clean_name_string, is_valid_name_candidate, name_is_plausible
from name_region import (find_name_label, fuzzy_label_score, name_search_regions, reocr_name_region,
                         decide_name_override, group_rows)


def box(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def det(text, conf, b=None, **extra):
    d = {"text": text, "confidence": conf}
    if b:
        d["box"] = b
    d.update(extra)
    return d


# ---------------------------------------------------------------- language loading
def test_language_fallback_and_no_silent_download():
    calls = []

    def factory(langs, **kw):
        calls.append((list(langs), kw))
        if langs != ["en"] and not kw.get("download_enabled"):
            raise FileNotFoundError("Missing model ta.pth and download disabled")
        return object()

    _, active, note = ocr.build_reader(["ta", "en"], allow_download=False, factory=factory)
    assert active == ["en"] and note and "NOT being read" in note and "ALLOW_DOWNLOAD" in note
    assert calls[0][1]["download_enabled"] is False, "must not download a language model silently"
    _, active, note = ocr.build_reader(["ta", "en"], allow_download=True, factory=factory)
    assert active == ["ta", "en"] and note is None
    _, active, note = ocr.build_reader(["en"], factory=factory)
    assert active == ["en"] and note is None
    print("  [PASS] Tamil+English falls back to English with an explicit note; no download unless allowed.")


# ---------------------------------------------------------------- variants
def test_background_normalisation_flattens_decoration():
    h, w = 240, 480
    yy, xx = np.mgrid[0:h, 0:w]
    background = (150 + 60 * np.sin(xx / 25.0) * np.cos(yy / 25.0)).astype(np.uint8)  # synthetic guilloche-like wash
    img = background.copy()
    cv2.putText(img, "MOHAN RAJ", (40, 120), cv2.FONT_HERSHEY_SIMPLEX, 1.2, 20, 3)
    bgr = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    flat, scale = ocr.variant_bg_normalized(bgr)
    assert scale == 2.0 and flat.shape == (h * 2, w * 2)
    region_raw = img[0:60, 0:w].astype(float)           # text-free band
    region_flat = flat[0:120, 0:w * 2].astype(float)
    assert region_flat.std() < region_raw.std() * 0.6, (region_flat.std(), region_raw.std())
    thr, _ = ocr.variant_adaptive_threshold(bgr)
    assert set(np.unique(thr)) <= {0, 255}
    print(f"  [PASS] Background std {region_raw.std():.1f} -> {region_flat.std():.1f} after normalisation; threshold is binary.")


# ---------------------------------------------------------------- merging
def test_merge_keeps_alternatives_and_agreement():
    b = box(100, 100, 300, 130)
    per = {
        "a": [det("UGoll", 0.59, b)],
        "b": [det("SANTHIYA SREE", 0.62, box(102, 101, 301, 131))],
        "c": [det("SANTHIYA SREE", 0.55, box(99, 99, 299, 129))],
        "d": [det("OTHER", 0.9, box(500, 500, 600, 530))],
    }
    merged = ocr.merge_variant_detections(per)
    assert len(merged) == 2
    top = next(m for m in merged if "SANTHIYA" in m["text"])
    assert top["variant"] == "b" and top["agreement"] == 2 and top["variants_seen"] == 3
    assert any(a["text"] == "UGoll" for a in top["alternatives"])
    assert abs(top["mean_confidence"] - round((0.59 + 0.62 + 0.55) / 3, 3)) < 1e-9
    print("  [PASS] Overlapping readings merge; winner keeps alternatives, agreement count and unbiased mean confidence.")


def test_reading_order_rows():
    dets = [det("C", .9, box(300, 12, 340, 32)), det("A", .9, box(10, 10, 50, 30)),
            det("D", .9, box(10, 80, 50, 100)), det("B", .9, box(150, 11, 190, 31))]
    assert [d["text"] for d in ocr.sort_reading_order(dets)] == ["A", "B", "C", "D"]
    print("  [PASS] Merged detections are returned in reading order (rows top-to-bottom, left-to-right).")


def test_variants_run_and_rescale_boxes():
    class FakeReader:
        def readtext(self, img, **kw):
            scale = img.shape[1] / 400.0                # recover how much this variant was upscaled
            return [(box(int(40 * scale), int(20 * scale), int(200 * scale), int(44 * scale)), "MOHAN RAJ", 0.8)]

    img = np.full((200, 400, 3), 255, np.uint8)
    out = ocr.extract_text_detailed(img, variants=["original", "upscaled_clahe"], ocr_reader=FakeReader())
    assert out["variants_used"] == ["original", "upscaled_clahe"] and not out["variant_errors"]
    assert len(out["detections"]) == 1, out["detections"]
    d = out["detections"][0]
    assert d["box"] == box(40, 20, 200, 44) and d["agreement"] == 2
    print("  [PASS] Each variant's boxes are rescaled to original coordinates and merged into one detection.")


def test_one_failing_variant_does_not_lose_the_rest():
    class Flaky:
        def __init__(self):
            self.n = 0

        def readtext(self, img, **kw):
            self.n += 1
            if self.n == 1:
                raise RuntimeError("boom")
            return [(box(0, 0, 50, 20), "X", 0.9)]

    out = ocr.extract_text_detailed(np.full((50, 100, 3), 255, np.uint8), variants=["original", "bg_normalized"], ocr_reader=Flaky())
    assert out["variants_used"] == ["bg_normalized"] and "original" in out["variant_errors"]
    print("  [PASS] A failing variant is reported in variant_errors; remaining variants still produce output.")


# ---------------------------------------------------------------- name region re-read
class ScriptedReader:
    """Returns the same scripted rows for every call; records the kwargs it was given."""
    def __init__(self, rows):
        self.rows, self.kwargs = rows, []

    def readtext(self, img, **kw):
        self.kwargs.append(kw)
        return list(self.rows)


IDENT = {"bg_normalized": lambda im: (im, 1.0), "upscaled_clahe": lambda im: (im, 1.0), "adaptive_threshold": lambda im: (im, 1.0)}
PAGE = np.full((400, 800, 3), 255, np.uint8)
LABEL = det("NAME OF THE CANDIDATE", 0.9, box(20, 100, 220, 120))


def _run_region(rows, label=LABEL):
    rd = ScriptedReader(rows)
    res = reocr_name_region(PAGE, [label], rd, IDENT, clean_name_string, is_valid_name_candidate, name_is_plausible)
    return res, rd


def test_region_reread_confirmed_by_agreeing_variants():
    res, rd = _run_region([(box(0, 0, 160, 20), "MOHAN RAJ", 0.82)])
    assert res["attempted"] and res["best"]["name"] == "MOHAN RAJ" and res["best"]["agreement"] == 3
    assert all(kw.get("allowlist") and "0" not in kw["allowlist"] for kw in rd.kwargs), "letters-only allowlist expected"
    dec = decide_name_override({"name": "UGoll", "confidence": 0.59, "plausible": False}, res)
    assert dec["status"] == "CONFIDENT" and dec["source"] == "HEADER_REGION_REOCR"
    print("  [PASS] Name region re-read with 3 agreeing variants + exact label -> CONFIDENT (letters-only allowlist used).")


def test_region_reread_without_agreement_stays_uncertain():
    outs = iter([("SANTHIYA SREE", 0.8), ("SANTHYA SRE", 0.7), ("SAN THIYA", 0.6)] * 4)

    class Varying:
        def readtext(self, img, **kw):
            t, c = next(outs)
            return [(box(0, 0, 160, 20), t, c)]

    res = reocr_name_region(PAGE, [LABEL], Varying(), IDENT, clean_name_string, is_valid_name_candidate, name_is_plausible)
    dec = decide_name_override({"name": "UGoll", "confidence": 0.59, "plausible": False}, res)
    assert dec is None or dec["status"] == "UNCERTAIN"
    print("  [PASS] Variants that disagree never produce a CONFIDENT name.")


def test_region_reread_garbage_and_missing_label():
    res, _ = _run_region([(box(0, 0, 60, 20), "x7%", 0.9), (box(70, 0, 120, 20), "##", 0.9)])
    assert res["best"] is None and decide_name_override({"name": "UGoll", "confidence": .59, "plausible": False}, res) is None
    res, _ = reocr_name_region(PAGE, [det("SOMETHING ELSE", .9, box(0, 0, 10, 10))], ScriptedReader([]), IDENT,
                               clean_name_string, is_valid_name_candidate, name_is_plausible), None
    assert res["attempted"] is False and res["reason"] == "NAME_LABEL_NOT_LOCATED"
    print("  [PASS] Garbage reads and an unlocatable label yield no name (nothing invented).")


def test_fuzzy_label_cannot_confirm_a_name():
    damaged = det("NAMF OF THF CANDIDATF", 0.7, box(20, 100, 220, 120))
    idx, kind = find_name_label([damaged])
    assert kind == "FUZZY"
    res, _ = _run_region([(box(0, 0, 160, 20), "MOHAN RAJ", 0.9)], label=damaged)
    dec = decide_name_override({"name": None, "confidence": 0.0, "plausible": False}, res)
    assert dec["status"] == "UNCERTAIN"
    assert fuzzy_label_score("TOTAL MARKS OBTAINED", ["NAME OF THE CANDIDATE"]) < 0.6
    print("  [PASS] A fuzzy-matched label can only give an UNCERTAIN name; unrelated labels do not match.")


def test_search_regions_stay_near_the_label():
    regs = {r["name"]: r["rect"] for r in name_search_regions((20, 100, 220, 120), 800, 400)}
    assert regs["right_of_label"][0] > 220 and regs["below_label"][1] == 120 and regs["below_label"][3] <= 120 + 2.2 * 20 + 1
    rows = group_rows([(box(0, 0, 50, 20), "MOHAN", 0.9), (box(60, 1, 110, 21), "RAJ", 0.7), (box(0, 60, 50, 80), "NEXT", 0.9)])
    assert [r["text"] for r in rows] == ["MOHAN RAJ", "NEXT"]
    print("  [PASS] Search regions are limited to the label's row and the band below it; row grouping works.")


# ---------------------------------------------------------------- geometry-aware field mapping
def test_decorative_text_after_label_is_not_the_name():
    dets = [
        det("NAME OF THE CANDIDATE", 0.9, box(20, 100, 220, 120)),
        det("ROYAL LION CREST", 0.93, box(20, 10, 400, 70)),        # big decorative banner ABOVE; next in list order
        det("MOHAN RAJ", 0.91, box(240, 100, 420, 122)),           # the real value: same row, right of label
    ]
    f = parse_extracted_fields(dets)
    assert f["candidate_name"] == "MOHAN RAJ", f["candidate_name"]
    assert f["field_status"]["candidate_name"] == "CONFIDENT" and f["candidate_name_source"] == "HEADER"
    print("  [PASS] Geometry picks the value on the label's row, not decorative text that follows it in list order.")


def test_value_below_label_and_inline_value():
    f = parse_extracted_fields([det("NAME OF THE CANDIDATE", 0.9, box(20, 100, 220, 120)),
                                det("ROYAL LION CREST", 0.93, box(500, 10, 780, 60)),
                                det("MOHAN RAJ", 0.9, box(30, 130, 200, 152))])
    assert f["candidate_name"] == "MOHAN RAJ"
    f = parse_extracted_fields([det("NAME OF THE CANDIDATE : MOHAN RAJ", 0.88)])
    assert f["candidate_name"] == "MOHAN RAJ" and f["field_status"]["candidate_name"] == "CONFIDENT"
    print("  [PASS] Values directly below the label, and values in the same box as the label, are found.")


def test_no_geometric_candidate_means_no_confident_name():
    f = parse_extracted_fields([det("NAME OF THE CANDIDATE", 0.9, box(20, 100, 220, 120)),
                                det("ROYAL LION CREST", 0.95, box(20, 300, 400, 340))])  # far below, outside the band
    assert f["field_status"]["candidate_name"] != "CONFIDENT"
    print("  [PASS] Text far from the label is never promoted to a CONFIDENT name.")


def test_damaged_name_label_is_a_weak_anchor():
    f = parse_extracted_fields([det("NAMF OF THF CANDIDATF", 0.8, box(20, 100, 220, 120)), det("MOHAN RAJ", 0.95, box(240, 100, 420, 122))])
    assert f["candidate_name"] == "MOHAN RAJ" and f["candidate_name_source"] == "HEADER_FUZZY"
    assert f["field_status"]["candidate_name"] == "UNCERTAIN"
    print("  [PASS] An OCR-damaged label anchors the name only weakly (UNCERTAIN).")


def test_fuzzy_permanent_register_label_is_uncertain():
    f = parse_extracted_fields([det("Pemanent Reaister No", 0.7), det("XM23R2195306000", 0.9), det("ROLL NO. 5306000", 0.9)])
    assert f["registration_number"] == "XM23R2195306000" and f["registration_source"] == "FUZZY_LABEL_REGISTRATION"
    assert f["field_status"]["registration_number"] == "UNCERTAIN" and f["roll_number"] == "5306000"
    print("  [PASS] A damaged 'Permanent Register No' label still finds the number, marked UNCERTAIN; roll number stays separate.")


def test_tamil_label_stem_is_syntactically_usable():
    f = parse_extracted_fields([det("நிரந்தரப் பதிவு எண் XM23R2195306000", 0.9)])
    assert f["registration_number"] == "XM23R2195306000" and f["registration_source"] == "LABELLED_REGISTRATION"
    print("  [PASS] Tamil permanent-register label stem matches (only effective when the Tamil model is active).")


def test_variant_disagreement_downgrades_confidence():
    base = [det("PERMANENT REGISTER NO.", 0.9), det("XM23R2195306000", 0.9, alternatives=[{"variant": "bg", "text": "XM23R2I95306000", "confidence": 0.7}])]
    f = parse_extracted_fields(base)
    assert f["field_status"]["registration_number"] == "UNCERTAIN" and f["field_notes"]["registration_number"] == "VARIANTS_DISAGREE"
    weak = [det("PERMANENT REGISTER NO.", 0.9), det("XM23R2195306000", 0.9, alternatives=[{"variant": "bg", "text": "XM23R2I95306000", "confidence": 0.3}])]
    assert parse_extracted_fields(weak)["field_status"]["registration_number"] == "CONFIDENT"
    print("  [PASS] A confident alternative reading from another variant downgrades the field; a weak one does not.")


def test_observed_ugoll_failure_stays_uncertain_and_is_preserved():
    f = parse_extracted_fields([det("NAME OF CANDIDATE", 0.9, box(20, 100, 220, 120)), det("UGoll", 0.59, box(240, 100, 330, 122))])
    assert f["candidate_name"] == "UGoll" and f["field_status"]["candidate_name"] == "UNCERTAIN"
    assert f["candidate_name_raw"] == "UGoll" and f["field_confidence"]["candidate_name"] == 0.59
    print("  [PASS] The observed 'UGoll' @59% read stays UNCERTAIN with raw text and confidence preserved.")


if __name__ == "__main__":
    print("=== OCR pipeline / field mapping tests ===")
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  [FAIL] {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
