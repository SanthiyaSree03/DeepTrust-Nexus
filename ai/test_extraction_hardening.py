"""
Regression tests for the extraction defects found during source review.
All detections are SYNTHETIC: they model layouts and failure modes, not any real person's certificate.
Run from ai/:  python test_extraction_hardening.py   (needs the project venv; EasyOCR is not exercised)
"""
import copy
import sys

from extract_cli import (
    parse_extracted_fields,
    compute_readable_text_confidence,
    parse_total_in_words,
    name_is_plausible,
)
from tamper_detector import evaluate_arithmetic_forensics


def d(text, conf=0.9):
    return {"text": text, "confidence": conf}


def test_permanent_register_not_confused_with_emis_or_roll():
    dets = [
        d("STATE BOARD OF SCHOOL EXAMINATIONS TAMILNADU"),
        d("EMIS ID 2414265216", 0.95),          # 10 digits, appears BEFORE the real number
        d("PERMANENT REGISTER NO.", 0.9),
        d("XM23R2195306000", 0.88),
        d("ROLL NO. 5306000", 0.92),
    ]
    f = parse_extracted_fields(dets)
    assert f["registration_number"] == "XM23R2195306000", f["registration_number"]
    assert f["registration_source"] == "LABELLED_REGISTRATION"
    assert f["field_status"]["registration_number"] == "CONFIDENT"
    assert f["emis_id"] == "2414265216"
    assert f["roll_number"] == "5306000"
    assert f["certificate_number"] != "5306000", "Roll number must not become the certificate number"
    print("  [PASS] Permanent register number wins over EMIS id and roll number; EMIS id kept separate.")


def test_emis_only_never_becomes_registration():
    f = parse_extracted_fields([d("EMIS NO"), d("2414265216", 0.95)])
    assert f["registration_number"] is None, f["registration_number"]
    assert f["field_status"]["registration_number"] == "MISSING"
    print("  [PASS] A lone EMIS id is not reported as the registration number.")


def test_unlabelled_numbers_are_uncertain():
    f = parse_extracted_fields([d("2414265216", 0.99), d("36260174", 0.99)])
    assert f["field_status"]["registration_number"] == "UNCERTAIN"
    assert f["field_status"]["certificate_number"] == "UNCERTAIN"
    print("  [PASS] High OCR confidence alone does not make an unlabelled number CONFIDENT.")


def test_total_numeric_vs_words_conflict_is_not_tampering():
    dets = [d("TOTAL MARKS", 0.9), d("349", 0.95), d("IN WORDS FOUR FOUR NINE", 0.8),
            d("TAMIL 092"), d("ENGLISH 088"), d("MATHEMATICS 095"), d("SCIENCE 090"), d("SOCIAL SCIENCE 084")]
    f = parse_extracted_fields(dets)
    assert f["total_marks"] == "349"
    assert f["total_marks_in_words"] == 449
    assert f["field_status"]["total_marks"] == "UNCERTAIN"
    assert f["total_marks_conflict"]["in_words"] == "449"
    chk = f["arithmetic_check"]
    assert chk["performed"] is False and chk["consistent"] is None
    assert chk["reason"] == "TOTAL_SOURCES_CONFLICT" and chk["calculated_sum"] == 449
    assert evaluate_arithmetic_forensics(f)["anomaly_detected"] is False
    print("  [PASS] Numeric/word total conflict -> total UNCERTAIN, no arithmetic mismatch asserted, no tamper signal.")


def test_total_agreeing_with_words_is_confident_and_checked():
    dets = [d("TOTAL", 0.3), d("449", 0.5), d("FOUR FOUR NINE", 0.5),
            d("TAMIL 92"), d("ENGLISH 88"), d("MATHEMATICS 95"), d("SCIENCE 90"), d("SOCIAL SCIENCE 84")]
    f = parse_extracted_fields(dets)
    assert f["field_status"]["total_marks"] == "CONFIDENT"
    assert f["arithmetic_check"]["consistent"] is True
    print("  [PASS] Two independent readings that agree make the total CONFIDENT and enable the arithmetic check.")


def test_maximum_marks_line_not_used_as_total():
    f = parse_extracted_fields([d("MAXIMUM MARKS 600", 0.99), d("TOTAL MARKS", 0.9), d("527", 0.9)])
    assert f["total_marks"] == "527", f["total_marks"]
    print("  [PASS] 'Maximum marks' is not mistaken for the obtained total.")


def test_name_garble_and_fallback_are_never_confident():
    f = parse_extracted_fields([d("NAME OF CANDIDATE", 0.9), d("UGoll", 0.59)])
    assert f["candidate_name"] == "UGoll" and f["field_status"]["candidate_name"] == "UNCERTAIN"
    f = parse_extracted_fields([d("MOHAN RAJ KUMAR", 0.97)])  # no header anchor
    assert f["candidate_name_source"] == "PATTERN_FALLBACK"
    assert f["field_status"]["candidate_name"] == "UNCERTAIN"
    f = parse_extracted_fields([d("NAME OF CANDIDATE", 0.9), d("MOHAN RAJ", 0.93)])
    assert f["field_status"]["candidate_name"] == "CONFIDENT"
    assert name_is_plausible("MOHAN RAJ") and not name_is_plausible("UGoll")
    print("  [PASS] Garbled / unanchored names stay UNCERTAIN; clean header-anchored names are CONFIDENT.")


def test_subject_matching_longest_first_and_not_tamilnadu():
    dets = [d("TAMIL NADU STATE BOARD"), d("SOCIAL SCIENCE 85"), d("SCIENCE 78"), d("TAMIL 91")]
    subs = {x["subject"]: x["marks"] for x in parse_extracted_fields(dets)["subject_marks"]}
    assert subs == {"SOCIAL SCIENCE": 85, "SCIENCE": 78, "TAMIL": 91}, subs
    print("  [PASS] SOCIAL SCIENCE is not recorded as SCIENCE; 'TAMIL NADU' is not a subject.")


def test_readable_confidence_is_character_weighted():
    noise = [d("x", 0.0) for _ in range(100)]            # 100 chars at 0.0
    text = [d("PERMANENT REGISTER NO", 0.92) for _ in range(15)]  # 15 x 19 alnum chars at 0.92
    dets = noise + text
    plain = sum(x["confidence"] for x in dets) / len(dets)
    weighted = compute_readable_text_confidence(dets)
    expected = (15 * 19 * 0.92) / (100 + 15 * 19)
    assert abs(weighted - expected) < 1e-9, (weighted, expected)
    assert weighted > plain and plain < 0.45 < weighted, (plain, weighted)
    assert compute_readable_text_confidence([]) == 0.0
    print(f"  [PASS] Plain mean {plain:.2f}; text-weighted {weighted:.2f} (exact formula). Reduces, but does not remove, noise drag.")


def test_words_total_parser():
    assert parse_total_in_words("IN WORDS FOUR FOUR NINE") == 449
    assert parse_total_in_words("FOUR HUNDRED AND FORTY NINE") == 449
    assert parse_total_in_words("NO NUMBER WORDS HERE") is None
    print("  [PASS] Totals in words are parsed (digit-by-digit and hundred forms).")


def test_no_invention_and_determinism():
    empty = parse_extracted_fields([])
    for k in ("certificate_number", "candidate_name", "registration_number", "total_marks"):
        assert empty[k] is None and empty["field_status"][k] == "MISSING", k
    dets = [d("PERMANENT REGISTER NO."), d("XM23R2195306000"), d("NAME OF CANDIDATE"), d("MOHAN RAJ")]
    a = parse_extracted_fields(copy.deepcopy(dets))
    b = parse_extracted_fields(copy.deepcopy(dets))
    assert a == b
    print("  [PASS] Empty OCR yields no invented values; identical input gives identical output.")


if __name__ == "__main__":
    print("=== Extraction hardening regression tests ===")
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            failed += 1
            print(f"  [FAIL] {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
