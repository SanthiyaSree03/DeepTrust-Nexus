"""
Tests for subject extraction, 6-subject 12th marksheet handling,
bilingual Tamil/English OCR, 'PASS' score token parsing, and arithmetic gap reconciliation.
"""
from extract_cli import parse_extracted_fields

def d(text, conf=0.9, box=None):
    res = {"text": text, "confidence": conf}
    if box:
        res["box"] = box
    return res

def test_missing_subject_reconciliation_exact_515():
    # Model the exact user scenario: 5 subjects read, total is 515, 6th subject mark 98 is on row between Chem & Math
    dets = [
        d("STATE BOARD OF SCHOOL EXAMINATIONS, TAMIL NADU", box=[[300, 100], [800, 100], [800, 130], [300, 130]]),
        d("NAME OF THE CANDIDATE : SANTHIYA SREE S", box=[[100, 200], [500, 200], [500, 230], [100, 230]]),
        d("PERMANENT REGISTER NUMBER", box=[[100, 250], [400, 250], [400, 270], [100, 270]]),
        d("2414265216", box=[[420, 250], [600, 250], [600, 270], [420, 270]]),

        # Subject table header
        d("SUBJECT", box=[[100, 350], [250, 350], [250, 370], [100, 370]]),
        d("MARKS OBTAINED FOR 100", box=[[450, 350], [650, 350], [650, 370], [450, 370]]),

        # Row 1: Tamil
        d("TAMIL", box=[[100, 400], [200, 400], [200, 420], [100, 420]]),
        d("093", box=[[500, 400], [550, 400], [550, 420], [500, 420]]),

        # Row 2: English
        d("ENGLISH", box=[[100, 450], [200, 450], [200, 470], [100, 470]]),
        d("094", box=[[500, 450], [550, 450], [550, 470], [500, 470]]),

        # Row 3: Physics
        d("PHYSICS", box=[[100, 500], [200, 500], [200, 520], [100, 520]]),
        d("077", box=[[500, 500], [550, 500], [550, 520], [500, 520]]),

        # Row 4: Chemistry
        d("CHEMISTRY", box=[[100, 550], [200, 550], [200, 570], [100, 570]]),
        d("090", box=[[500, 550], [550, 550], [550, 570], [500, 570]]),

        # Row 5: 6th subject (e.g. Computer Science or Biology with noisy OCR text)
        d("கணினி அறிவியல்", box=[[100, 600], [250, 600], [250, 620], [100, 620]]),
        d("098 PASS", box=[[500, 600], [580, 600], [580, 620], [500, 620]]),

        # Row 6: Mathematics
        d("MATHEMATICS", box=[[100, 650], [250, 650], [250, 670], [100, 670]]),
        d("063", box=[[500, 650], [550, 650], [550, 670], [500, 670]]),

        # Total Marks
        d("TOTAL MARKS :", box=[[100, 750], [300, 750], [300, 770], [100, 770]]),
        d("0515", box=[[350, 750], [420, 750], [420, 770], [350, 770]]),
    ]

    f = parse_extracted_fields(dets)
    subjs = f.get("subject_marks", [])
    print("Extracted subjects count:", len(subjs))
    for s in subjs:
        print(f"  {s['subject']}: {s['marks']}")

    assert len(subjs) == 6, f"Expected 6 subjects, got {len(subjs)}"
    subj_dict = {s["subject"]: s["marks"] for s in subjs}
    assert subj_dict["TAMIL"] == 93
    assert subj_dict["ENGLISH"] == 94
    assert subj_dict["PHYSICS"] == 77
    assert subj_dict["CHEMISTRY"] == 90
    assert subj_dict["MATHEMATICS"] == 63
    assert ("COMPUTER SCIENCE" in subj_dict and subj_dict["COMPUTER SCIENCE"] == 98) or \
           ("BIOLOGY" in subj_dict and subj_dict["BIOLOGY"] == 98)

    arith = f.get("arithmetic_check", {})
    print("Arithmetic check:", arith)
    assert arith["consistent"] is True
    assert arith["difference"] == 0
    assert arith["calculated_sum"] == 515
    assert arith["recorded_total"] == 515
    print("  [PASS] All 6 subjects extracted with 0 arithmetic discrepancy (515 == 515)!")

def test_missing_subject_reconciliation_blurred_label():
    # If the 6th subject label is completely distorted/unreadable, but 098 is on the row between Chem & Math
    dets = [
        d("TOTAL MARKS : 515", box=[[100, 750], [400, 750], [400, 770], [100, 770]]),
        d("TAMIL 093", box=[[100, 400], [550, 400], [550, 420], [100, 420]]),
        d("ENGLISH 094", box=[[100, 450], [550, 450], [550, 470], [100, 470]]),
        d("PHYSICS 077", box=[[100, 500], [550, 500], [550, 520], [100, 520]]),
        d("CHEMISTRY 090", box=[[100, 550], [550, 550], [550, 570], [100, 570]]),
        # Blurred label box with only noise characters, but contains 098 score
        d("###~~~??? 098", box=[[100, 600], [550, 600], [550, 620], [100, 620]]),
        d("MATHEMATICS 063", box=[[100, 650], [550, 650], [550, 670], [100, 670]]),
    ]

    f = parse_extracted_fields(dets)
    subjs = f.get("subject_marks", [])
    assert len(subjs) == 6, f"Expected 6 subjects, got {len(subjs)}"
    arith = f.get("arithmetic_check", {})
    assert arith["consistent"] is True
    assert arith["calculated_sum"] == 515
    assert arith["difference"] == 0
    print("  [PASS] Blurred label reconstructed via curriculum inference & arithmetic reconciliation!")

if __name__ == "__main__":
    test_missing_subject_reconciliation_exact_515()
    test_missing_subject_reconciliation_blurred_label()
    print("\nALL RECONCILIATION TESTS PASSED SUCCESSFULLY!")
