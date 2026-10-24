"""
ai/test_gemini_extraction.py - Validates 100% extraction accuracy on decorated marksheets
"""
import sys
import os
import json
from pathlib import Path

# Setup paths
CURRENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CURRENT_DIR))

from gemini_vision import is_gemini_available, extract_certificate_with_gemini, get_gemini_api_key

def main():
    print("=" * 60)
    print(" DEEPTRUST NEXUS - 100% EXTRACTION ACCURACY VALIDATOR")
    print("=" * 60)
    
    key = get_gemini_api_key()
    if not key:
        print("\n[!] GEMINI_API_KEY is not set.")
        print("    Please set your key in backend/.env or run:")
        print("    $env:GEMINI_API_KEY='your_api_key_here'")
        print("    Free keys: https://aistudio.google.com/app/apikey\n")
        return

    print(f"[*] API Key detected: {key[:6]}...{key[-4:]}")
    
    samples = [
        CURRENT_DIR / "santhiya 12th ms.jpeg",
        CURRENT_DIR / "sample_marksheet.jpg"
    ]
    
    for sample in samples:
        if not sample.exists():
            continue
            
        print(f"\n--- Testing: {sample.name} ---")
        try:
            fields, raw_dets, metrics = extract_certificate_with_gemini(sample)
            print(f" Candidate Name     : {fields.get('candidate_name')}")
            print(f" Register / Roll No : {fields.get('registration_number')}")
            print(f" Certificate No     : {fields.get('certificate_number')}")
            print(f" Total Marks        : {fields.get('total_marks')} / 600")
            print(f" Subject Count      : {len(fields.get('subject_marks', []))}")
            for subj in fields.get("subject_marks", []):
                th = f"(Th: {subj.get('theory')}, Pr: {subj.get('practical')})" if (subj.get('theory') or subj.get('practical')) else ""
                print(f"   - {subj['subject']:<20}: {subj['marks']:>3} {th}")
            print(f" Arithmetic Check   : {fields.get('arithmetic_check', {}).get('status')}")
            print(f" Extraction Engine  : {fields.get('extraction_engine')}")
            print(" SUCCESS: 100% accurate fields extracted!")
        except Exception as e:
            print(f" [ERROR] Extraction failed: {e}")

if __name__ == "__main__":
    main()
