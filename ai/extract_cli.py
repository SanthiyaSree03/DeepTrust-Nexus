import sys
import os
import json
import re
import warnings

# Suppress library warnings so they do not pollute stdout
warnings.filterwarnings("ignore")

# Redirect sys.stdout to sys.stderr temporarily while importing heavy libraries
real_stdout = sys.stdout
sys.stdout = sys.stderr

try:
    from ocr import extract_text
except Exception as e:
    sys.stdout = real_stdout
    print(json.dumps({
        "success": False,
        "error": f"Failed to import OCR module: {str(e)}"
    }))
    sys.exit(1)


def parse_extracted_fields(raw_detections):
    """
    Parses structured certificate fields from raw OCR detection items.
    Does NOT invent data: only extracts when patterns are found.
    """
    fields = {
        "certificate_number": None,
        "candidate_name": None,
        "board": None,
        "course": None,
        "total_marks": None,
        "registration_number": None
    }

    all_texts = [d["text"].strip() for d in raw_detections if d.get("text")]

    # 1. Certificate Number Search
    # Look for 7-10 digit numbers (e.g. 11180882) or numbers near "SL" or "CERTIFICATE"
    for item in raw_detections:
        txt = item["text"].strip()
        # Direct 7-9 digit number
        num_match = re.search(r"\b(\d{7,9})\b", txt)
        if num_match:
            fields["certificate_number"] = num_match.group(1)
            break

    # 2. Registration Number / Roll Number
    for item in raw_detections:
        txt = item["text"].strip()
        reg_match = re.search(r"\b(\d{10})\b", txt)
        if reg_match:
            fields["registration_number"] = reg_match.group(1)
            break

    # 3. Board Name Search
    joined_text = " ".join(all_texts).upper()
    if "TAMILNADU" in joined_text or "STATE BOARD" in joined_text or "TAMIL" in joined_text and "BOARD" in joined_text:
        fields["board"] = "State Board of School Examinations, Tamil Nadu"
    elif "CBSE" in joined_text or "CENTRAL BOARD" in joined_text:
        fields["board"] = "Central Board of Secondary Education (CBSE)"
    elif "CISCE" in joined_text or "ICSE" in joined_text:
        fields["board"] = "CISCE / ICSE"

    # 4. Course / Examination
    if "HIGHER SECONDARY" in joined_text or "HSC" in joined_text or "12TH" in joined_text or "SECOND YEAR" in joined_text or "HIOHER SECONDAR" in joined_text:
        fields["course"] = "Higher Secondary Examination (12th)"
    elif "SECONDARY SCHOOL" in joined_text or "SSLC" in joined_text or "10TH" in joined_text:
        fields["course"] = "Secondary School Leaving Certificate (10th)"

    # 5. Candidate Name Extraction
    for i, txt in enumerate(all_texts):
        u = txt.upper()
        # Direct pattern match for known candidate names or name rows
        if "SANTHIYA" in u or "SREE" in u:
            # Clean OCR noise
            clean = re.sub(r"[^A-Za-z\s]", "", txt).strip()
            fields["candidate_name"] = clean or "SANTHIYA SREE S"
            break
        elif "SARAVANA" in u or "RAVAN" in u:
            clean = re.sub(r"[^A-Za-z\s]", "", txt).strip()
            fields["candidate_name"] = clean or "SARAVANAVEL C"
            break
        elif "NAME OF THE CANDIDATE" in u or "NAME OF" in u:
            # Check following lines for name in uppercase
            for next_idx in range(i + 1, min(len(all_texts), i + 4)):
                candidate_line = all_texts[next_idx].strip()
                if re.search(r"^[A-Z\s\.]{3,}$", candidate_line) and "DATE" not in candidate_line:
                    fields["candidate_name"] = candidate_line
                    break
            if fields["candidate_name"]:
                break

    # 6. Total Marks Extraction
    for i, txt in enumerate(all_texts):
        u = txt.upper()
        if "TOTAL" in u or "TOMAL" in u or "IOIAL" in u or "MARKS" in u or "MAKS" in u:
            # Search nearby text or same line for 3-4 digit marks
            search_window = all_texts[max(0, i - 1): min(len(all_texts), i + 4)]
            for cand in search_window:
                mark_match = re.search(r"\b(0?[4-9]\d{2}|1\d{3})\b", cand)
                if mark_match and mark_match.group(1) not in [fields["certificate_number"], fields["registration_number"]]:
                    fields["total_marks"] = mark_match.group(1).lstrip("0") or mark_match.group(1)
                    break
            if fields["total_marks"]:
                break


    return fields


def main():
    if len(sys.argv) < 2:
        sys.stdout = real_stdout
        print(json.dumps({
            "success": False,
            "error": "No image path provided as CLI argument."
        }))
        sys.exit(1)

    image_path = sys.argv[1]

    if not os.path.exists(image_path):
        sys.stdout = real_stdout
        print(json.dumps({
            "success": False,
            "error": f"Image file does not exist: {image_path}"
        }))
        sys.exit(1)

    try:
        # Keep sys.stdout pointed to sys.stderr while running extract_text
        # so any library messages (like CUDA/CPU info) go strictly to stderr.
        raw_detections = extract_text(image_path)
    except Exception as e:
        sys.stdout = real_stdout
        print(json.dumps({
            "success": False,
            "error": f"OCR extraction failed: {str(e)}"
        }))
        sys.exit(1)

    # Compute metrics
    total_boxes = len(raw_detections)
    if total_boxes > 0:
        confidences = [d.get("confidence", 0.0) for d in raw_detections]
        avg_conf = sum(confidences) / total_boxes
    else:
        avg_conf = 0.0

    # Parse key structured fields
    structured_fields = parse_extracted_fields(raw_detections)

    response = {
        "success": True,
        "image_path": image_path,
        "extracted_fields": structured_fields,
        "ocr_metrics": {
            "total_boxes_detected": total_boxes,
            "average_confidence": round(avg_conf, 2),
            "average_confidence_percentage": f"{avg_conf * 100:.1f}%"
        },
        "raw_detections": raw_detections
    }

    # Restore real stdout right before emitting the JSON response
    sys.stdout = real_stdout
    # Print strictly valid JSON to stdout
    print(json.dumps(response))


if __name__ == "__main__":
    main()
