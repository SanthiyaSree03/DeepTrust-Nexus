"""
ai/test_marksheet_ocr_regression.py - Regression tests for candidate name and registration number extraction.

Tests:
1. Bilingual & tabular candidate name extraction (prevents picking adjacent column labels like SESSION).
2. Permanent registration number extraction across split labels and table rows.
3. Name region search geometry correctly encompasses table cells without hardcoding specific names/numbers.
"""

import os
import sys
import numpy as np

# Ensure ai directory is on python path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from extract_cli import parse_extracted_fields, _name_candidate_after, _find_labelled_value
from name_region import name_search_regions, rect_of


def box_at(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def test_bilingual_name_cell_geometry():
    """Verify name_search_regions expands leftward to encompass bilingual table cells."""
    # Label at x=400..650 (English part), with preceding Tamil box at x=200..390
    dets = [
        {"box": box_at(200, 380, 390, 412), "text": "தேர்வரின் பெயர்"},
        {"box": box_at(400, 390, 650, 412), "text": "NAME OF THE CANDIDATE"},
    ]
    lbl_rect = (400, 390, 650, 412)
    page_w, page_h = 1000, 1500
    regions = name_search_regions(lbl_rect, page_w, page_h, dets, label_idx=1)
    
    below = next((r for r in regions if r["name"] == "below_label"), None)
    assert below is not None, "below_label region missing"
    rx0, ry0, rx1, ry1 = below["rect"]
    
    # Must cover left side of table cell (where candidate name starts)
    assert rx0 <= 150, f"Expected rx0 <= 150 to cover cell start, got {rx0}"
    assert ry1 >= 480, f"Expected ry1 >= 480 to cover multiline cell value, got {ry1}"
    print("  [PASS] name_search_regions bounds bilingual table cells correctly.")


def test_candidate_name_avoids_adjacent_session_column():
    """Verify _name_candidate_after rejects adjacent SESSION column text and picks the cell below."""
    items = [
        # Bilingual header row: [Tamil] [English] | [SESSION]
        {"box": box_at(200, 380, 390, 412), "text": "தேர்வரின் பெயர்", "confidence": 0.3},
        {"box": box_at(400, 390, 650, 412), "text": "NAME OF THE CANDIDATE", "confidence": 0.95},
        # Next column on same row (SESSION header misread as letters):
        {"box": box_at(800, 385, 890, 415), "text": "LGoul", "confidence": 0.23},
        {"box": box_at(900, 385, 990, 410), "text": "SESSION", "confidence": 0.99},
        # Cell below: Candidate name
        {"box": box_at(100, 450, 280, 480), "text": "ARAVIND KUMAR R", "confidence": 0.85},
    ]
    cand = _name_candidate_after(items, i=1)
    assert cand is not None, "Candidate name must be found"
    assert cand["name"] == "ARAVIND KUMAR R", f"Expected ARAVIND KUMAR R, got '{cand['name']}'"
    assert cand["confidence"] == 0.85
    print("  [PASS] _name_candidate_after avoids adjacent SESSION column and captures value in cell below.")


def test_split_label_permanent_register_number():
    """Verify permanent registration number is extracted when label is split across boxes and rows."""
    items = [
        {"box": box_at(100, 1180, 250, 1205), "text": "நிரந்தரப் பதிவெண்", "confidence": 0.5},
        {"box": box_at(260, 1180, 360, 1205), "text": "PERMANENT", "confidence": 0.99},
        {"box": box_at(365, 1180, 480, 1205), "text": "REGISTER NO.", "confidence": 0.95},
        # Intervening table columns on header row
        {"box": box_at(590, 1180, 650, 1200), "text": "CODE NO.", "confidence": 0.5},
        {"box": box_at(660, 1175, 770, 1200), "text": "T.M.R. DATE", "confidence": 0.5},
        # Row below: values
        {"box": box_at(120, 1220, 300, 1245), "text": "AB12C3456789000", "confidence": 0.97},
        {"box": box_at(660, 1215, 750, 1235), "text": "J3297576", "confidence": 0.99},
    ]
    fields = parse_extracted_fields(items)
    assert fields["registration_number"] == "AB12C3456789000", f"Expected AB12C3456789000, got '{fields['registration_number']}'"
    assert fields["field_status"]["registration_number"] == "CONFIDENT"
    assert fields["registration_source"] == "LABELLED_REGISTRATION"
    print("  [PASS] Permanent registration number extracted from split-label table layout.")


def test_unlabelled_state_board_alphanumeric_registration_fallback():
    """Verify state board alphanumeric registration number is extracted as UNCERTAIN when unlabelled."""
    items = [
        {"box": box_at(100, 200, 200, 220), "text": "RANDOM HEADER", "confidence": 0.8},
        {"box": box_at(100, 300, 300, 325), "text": "TN24R9876543210", "confidence": 0.92},
    ]
    fields = parse_extracted_fields(items)
    assert fields["registration_number"] == "TN24R9876543210"
    assert fields["field_status"]["registration_number"] == "UNCERTAIN"
    assert fields["registration_source"] == "UNLABELLED_REGISTRATION"
    print("  [PASS] Unlabelled alphanumeric registration number fallback operates correctly.")


def test_tamil_nadu_10th_marksheet_total_and_subject_arithmetic():
    """Verify TN 10th layout: total-in-words is spatially bound to TOTAL MARKS row (not subject marks 086),
    and Mathematics mark appearing before label in reading order is captured, yielding exact 449 sum."""
    items = [
        # Candidate name
        {"box": box_at(400, 390, 650, 412), "text": "NAME OF THE CANDIDATE", "confidence": 0.95},
        {"box": box_at(100, 450, 280, 480), "text": "SANTHIYA SREE", "confidence": 0.69},
        # Subject 1: Tamil (contains 086 and words ZERO EIGHT SIX - must NOT become total in words)
        {"box": box_at(100, 600, 250, 625), "text": "TAMIL", "confidence": 0.95},
        {"box": box_at(300, 600, 360, 625), "text": "086", "confidence": 0.98},
        {"box": box_at(400, 600, 580, 625), "text": "ZERO EIGHT SIX", "confidence": 0.95},
        # Subject 2: English
        {"box": box_at(100, 640, 250, 665), "text": "ENGLISH", "confidence": 0.95},
        {"box": box_at(300, 640, 360, 665), "text": "096", "confidence": 0.99},
        {"box": box_at(400, 640, 580, 665), "text": "ZERO NINE SIX", "confidence": 0.95},
        # Subject 3: Mathematics (in reading order, 088 and words precede label box due to column layout)
        {"box": box_at(300, 680, 360, 705), "text": "088", "confidence": 1.0},
        {"box": box_at(400, 680, 580, 705), "text": "ZERO EIGHT EIGHT", "confidence": 0.93},
        {"box": box_at(100, 680, 250, 705), "text": "MATHEMATICS", "confidence": 0.91},
        # Subject 4: Science (Theory 070 + Practical 025 -> Total 095)
        {"box": box_at(100, 720, 250, 745), "text": "SCIENCE", "confidence": 0.95},
        {"box": box_at(260, 720, 310, 745), "text": "070", "confidence": 0.98},
        {"box": box_at(320, 720, 370, 745), "text": "025", "confidence": 0.98},
        {"box": box_at(380, 720, 430, 745), "text": "095", "confidence": 0.99},
        {"box": box_at(450, 720, 630, 745), "text": "ZERO NINE FIVE", "confidence": 0.93},
        # Subject 5: Social Science
        {"box": box_at(100, 760, 250, 785), "text": "SOCIAL SCIENCE", "confidence": 0.95},
        {"box": box_at(380, 760, 430, 785), "text": "084", "confidence": 0.97},
        {"box": box_at(450, 760, 630, 785), "text": "ZERO EIGHT FOUR", "confidence": 0.92},
        # Bottom row: Total marks
        {"box": box_at(100, 820, 250, 845), "text": "TOTAL MARKS", "confidence": 0.96},
        {"box": box_at(380, 820, 430, 845), "text": "449", "confidence": 0.98},
        {"box": box_at(450, 820, 630, 845), "text": "FOUR FOUR NINE", "confidence": 0.97},
    ]
    f = parse_extracted_fields(items)
    assert f["candidate_name"] == "SANTHIYA SREE"
    assert f["total_marks"] == "449", f"Expected total 449, got {f['total_marks']}"
    assert f["total_marks_in_words"] == 449, f"Expected total in words 449, got {f['total_marks_in_words']}"
    assert f["field_status"]["total_marks"] == "CONFIDENT"
    assert "total_marks_conflict" not in f or f["total_marks_conflict"] is None
    assert len(f["subject_marks"]) == 5, f"Expected 5 subjects, got {len(f['subject_marks'])}"
    sub_map = {s["subject"]: s["marks"] for s in f["subject_marks"]}
    assert sub_map["MATHEMATICS"] == 88, f"Expected Mathematics 88, got {sub_map.get('MATHEMATICS')}"
    assert sub_map["SCIENCE"] == 95, f"Expected Science total 95 (not theory 70), got {sub_map.get('SCIENCE')}"
    sci_entry = next(s for s in f["subject_marks"] if s["subject"] == "SCIENCE")
    assert sci_entry.get("theory") == 70, f"Expected Science theory 70, got {sci_entry.get('theory')}"
    assert sci_entry.get("practical") == 25, f"Expected Science practical 25, got {sci_entry.get('practical')}"
    chk = f["arithmetic_check"]
    assert chk["performed"] is True
    assert chk["consistent"] is True
    assert chk["status"] == "VERIFIED_CONSISTENT"
    assert chk["calculated_sum"] == 449
    print("  [PASS] TN 10th layout: Science Theory (70) + Practical (25) resolved to Total (95), sum equals 449.")


def test_tamil_nadu_12th_marksheet_low_res_garbled_name_marked_uncertain():
    """Verify TN 12th layout: degraded/garbled candidate name is marked UNCERTAIN and not fabricated."""
    items = [
        # Bilingual TN 12th header with garbled label & value
        {"box": box_at(100, 100, 300, 125), "text": "Geutr uue/neoF TFeCIDIL", "confidence": 0.4},
        {"box": box_at(100, 130, 280, 155), "text": "nilina Sree", "confidence": 0.06},
        {"box": box_at(500, 50, 650, 75), "text": "CERTIFICATE NO 36260174", "confidence": 0.95},
        {"box": box_at(100, 200, 350, 225), "text": "PERMANENT REGISTER NO 2414265216", "confidence": 0.95},
        {"box": box_at(100, 800, 250, 825), "text": "TOTAL MARKS", "confidence": 0.95},
        {"box": box_at(300, 800, 360, 825), "text": "527", "confidence": 0.98},
    ]
    f = parse_extracted_fields(items)
    assert f["candidate_name"] == "nilina Sree"
    assert f["field_status"]["candidate_name"] == "UNCERTAIN", "Low-confidence name must be UNCERTAIN"
    assert f["total_marks"] == "527"
    assert f["certificate_number"] == "36260174"
    assert f["registration_number"] == "2414265216"
    print("  [PASS] TN 12th degraded scan: garbled candidate name honestly marked UNCERTAIN; real OCR values preserved.")


def test_cbse_10th_marksheet_layout_with_hundred_words_total():
    """Verify different layout: CBSE 10th marksheet with total in words as 'FOUR HUNDRED AND THIRTY FIVE'."""
    items = [
        {"box": box_at(100, 200, 350, 225), "text": "NAME OF CANDIDATE", "confidence": 0.95},
        {"box": box_at(100, 235, 300, 260), "text": "PRIYA SHARMA", "confidence": 0.97},
        {"box": box_at(100, 300, 250, 325), "text": "ENGLISH", "confidence": 0.95},
        {"box": box_at(300, 300, 350, 325), "text": "085", "confidence": 0.96},
        {"box": box_at(100, 340, 250, 365), "text": "MATHEMATICS", "confidence": 0.95},
        {"box": box_at(300, 340, 350, 365), "text": "090", "confidence": 0.96},
        {"box": box_at(100, 380, 250, 405), "text": "SCIENCE", "confidence": 0.95},
        {"box": box_at(300, 380, 350, 405), "text": "092", "confidence": 0.96},
        {"box": box_at(100, 420, 250, 445), "text": "SOCIAL SCIENCE", "confidence": 0.95},
        {"box": box_at(300, 420, 350, 445), "text": "088", "confidence": 0.96},
        {"box": box_at(100, 460, 250, 485), "text": "HINDI", "confidence": 0.95},
        {"box": box_at(300, 460, 350, 485), "text": "080", "confidence": 0.96},
        {"box": box_at(100, 520, 250, 545), "text": "TOTAL MARKS", "confidence": 0.95},
        {"box": box_at(300, 520, 350, 545), "text": "435", "confidence": 0.98},
        {"box": box_at(400, 520, 700, 545), "text": "FOUR HUNDRED AND THIRTY FIVE", "confidence": 0.95},
    ]
    f = parse_extracted_fields(items)
    assert f["candidate_name"] == "PRIYA SHARMA"
    assert f["field_status"]["candidate_name"] == "CONFIDENT"
    assert f["total_marks"] == "435"
    assert f["total_marks_in_words"] == 435
    assert f["field_status"]["total_marks"] == "CONFIDENT"
    assert f["arithmetic_check"]["consistent"] is True
    assert f["arithmetic_check"]["calculated_sum"] == 435
    print("  [PASS] CBSE 10th layout: 'FOUR HUNDRED AND THIRTY FIVE' matches 435, arithmetic consistent.")


def test_state_board_12th_6_subject_arithmetic():
    """Verify 12th marksheet with 6 subjects summing to 527."""
    items = [
        {"box": box_at(100, 200, 300, 225), "text": "NAME OF CANDIDATE: KAVITHA M", "confidence": 0.94},
        {"box": box_at(100, 300, 200, 320), "text": "TAMIL 090", "confidence": 0.95},
        {"box": box_at(100, 330, 200, 350), "text": "ENGLISH 085", "confidence": 0.95},
        {"box": box_at(100, 360, 200, 380), "text": "PHYSICS 088", "confidence": 0.95},
        {"box": box_at(100, 390, 200, 410), "text": "CHEMISTRY 087", "confidence": 0.95},
        {"box": box_at(100, 420, 200, 440), "text": "BIOLOGY 092", "confidence": 0.95},
        {"box": box_at(100, 450, 200, 470), "text": "MATHEMATICS 085", "confidence": 0.95},
        {"box": box_at(100, 500, 200, 520), "text": "TOTAL MARKS", "confidence": 0.95},
        {"box": box_at(250, 500, 320, 520), "text": "527", "confidence": 0.99},
        {"box": box_at(350, 500, 550, 520), "text": "FIVE TWO SEVEN", "confidence": 0.95},
    ]
    f = parse_extracted_fields(items)
    assert f["candidate_name"] == "KAVITHA M"
    assert f["total_marks"] == "527"
    assert f["total_marks_in_words"] == 527
    assert len(f["subject_marks"]) == 6, f"Expected 6 subjects, got {len(f['subject_marks'])}"
    assert f["arithmetic_check"]["consistent"] is True
    assert f["arithmetic_check"]["calculated_sum"] == 527
    print("  [PASS] 12th 6-subject layout: all 6 subjects captured, sum equals 527.")


def test_numeric_and_words_total_conflict_marks_uncertain():
    """Verify that when stated numeric total (349) conflicts with words total (449), it is marked UNCERTAIN."""
    items = [
        {"box": box_at(100, 100, 250, 120), "text": "TOTAL MARKS", "confidence": 0.95},
        {"box": box_at(260, 100, 320, 120), "text": "349", "confidence": 0.95},
        {"box": box_at(330, 100, 500, 120), "text": "FOUR FOUR NINE", "confidence": 0.95},
        {"box": box_at(100, 200, 200, 220), "text": "TAMIL 092", "confidence": 0.95},
        {"box": box_at(100, 230, 200, 250), "text": "ENGLISH 088", "confidence": 0.95},
        {"box": box_at(100, 260, 200, 280), "text": "MATHEMATICS 095", "confidence": 0.95},
        {"box": box_at(100, 290, 200, 310), "text": "SCIENCE 090", "confidence": 0.95},
        {"box": box_at(100, 320, 200, 340), "text": "SOCIAL SCIENCE 084", "confidence": 0.95},
    ]
    f = parse_extracted_fields(items)
    assert f["total_marks"] == "349"
    assert f["total_marks_in_words"] == 449
    assert f["field_status"]["total_marks"] == "UNCERTAIN"
    assert f.get("total_marks_conflict") is not None
    assert f["arithmetic_check"]["status"] == "NOT_APPLICABLE"
    assert f["arithmetic_check"]["reason"] == "TOTAL_SOURCES_CONFLICT"
    print("  [PASS] Conflicting numeric (349) and words total (449) correctly flags conflict and UNCERTAIN.")


def run_all():
    print("=== Marksheet OCR Extraction Regression Suite ===")
    test_bilingual_name_cell_geometry()
    test_candidate_name_avoids_adjacent_session_column()
    test_split_label_permanent_register_number()
    test_unlabelled_state_board_alphanumeric_registration_fallback()
    test_tamil_nadu_10th_marksheet_total_and_subject_arithmetic()
    test_tamil_nadu_12th_marksheet_low_res_garbled_name_marked_uncertain()
    test_cbse_10th_marksheet_layout_with_hundred_words_total()
    test_state_board_12th_6_subject_arithmetic()
    test_numeric_and_words_total_conflict_marks_uncertain()
    print("\nAll 9 OCR regression tests passed successfully!")


if __name__ == "__main__":
    run_all()

