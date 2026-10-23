import os
import sys
import json

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from test_marksheet_pipeline import evaluate_marksheet

samples = [
    os.path.join(CURRENT_DIR, "10th marksheet(ss).jpeg"),
    os.path.join(CURRENT_DIR, "santhiya 12th ms.jpeg"),
    os.path.join(CURRENT_DIR, "sample_marksheet.jpg")
]

for s in samples:
    if not os.path.exists(s):
        print(f"Skipping non-existent: {s}")
        continue
    print("=" * 80)
    print(f"EVALUATING: {os.path.basename(s)}")
    print("=" * 80)
    res = evaluate_marksheet(s)
    fields = res.get("extracted_fields", {})
    print(f"Candidate Name       : {fields.get('candidate_name')} (Status: {fields.get('field_status', {}).get('candidate_name')}, Conf: {fields.get('candidate_name_confidence')})")
    print(f"Registration Number  : {fields.get('registration_number')} (Status: {fields.get('field_status', {}).get('registration_number')}, Conf: {fields.get('field_confidence', {}).get('registration_number')})")
    print(f"Certificate Number   : {fields.get('certificate_number')} (Status: {fields.get('field_status', {}).get('certificate_number')})")
    print(f"Total Marks          : {fields.get('total_marks')} (Status: {fields.get('field_status', {}).get('total_marks')}, Conf: {fields.get('field_confidence', {}).get('total_marks')})")
    print(f"Total in Words       : {fields.get('total_marks_in_words')}")
    print(f"Total Conflict       : {fields.get('total_marks_conflict')}")
    print(f"Arithmetic Check     : {fields.get('arithmetic_check')}")
    print(f"Subject Marks Count  : {len(fields.get('subject_marks', []))}")
    for sm in fields.get("subject_marks", []):
        print(f"   - {sm}")
    print(f"QR Analysis          : detected={res.get('qr_analysis', {}).get('detected')}, state={res.get('qr_analysis', {}).get('detection_state')}, payload_type={res.get('qr_analysis', {}).get('payload_type')}")
    print()
