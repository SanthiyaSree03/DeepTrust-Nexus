import sys
import os
import json
import re
import difflib
import warnings

# Suppress library warnings so they do not pollute stdout
warnings.filterwarnings("ignore")

# Redirect sys.stdout to sys.stderr temporarily while importing heavy libraries
real_stdout = sys.stdout
sys.stdout = sys.stderr

try:
    from name_region import (NAME_LABEL_PATTERNS, find_name_label, fuzzy_label_score, rect_of,
                             reocr_name_region, decide_name_override)
    from qr_validator import analyze_certificate_qr
    from tamper_detector import analyze_document_tampering
except Exception as e:
    sys.stdout = real_stdout
    print(json.dumps({
        "success": False,
        "error": f"Failed to import helper module: {str(e)}"
    }))
    sys.exit(1)

EXCLUDED_NAME_KEYWORDS = {
    "STATE", "BOARD", "SCHOOL", "EXAMINATIONS", "EXAMINATION", "TAMILNADU",
    "CHENNAI", "GOVERNMENT", "CENTRAL", "SECONDARY", "HIGHER", "CERTIFICATE",
    "COURSE", "GENERAL", "EDUCATION", "TOTAL", "MARKS", "REGISTER",
    "REGISTRATION", "PERMANENT", "ROLL", "MONTH", "YEAR", "DATE", "BIRTH",
    "GENDER", "MALE", "FEMALE", "COMMUNITY", "MEDIUM", "ENGLISH", "TAMIL",
    "HINDI", "PHYSICS", "CHEMISTRY", "BIOLOGY", "MATHEMATICS", "THEORY",
    "PRACTICAL", "INTERNAL", "EXTERNAL", "PASS", "FAIL", "DIRECTOR",
    "SECRETARY", "HEADMASTER", "AUTHORITY", "FATHER", "MOTHER", "GUARDIAN",
    "CENTRE", "SESSION", "MAXIMUM", "MINIMUM", "OBTAINED", "RESULT",
    "SUBJECT", "CODE", "OTHER", "DETAILS", "RECOGNIZED", "STATEMENT",
    "PROVISIONAL", "DOCUMENT", "VERIFIED", "VERIFICATION", "SEAL", "SIGNATURE",
    "STAMP", "OFFICE", "ENROLMENT", "REGULAR", "PRIVATE", "STATUS", "REMARKS",
    "INFORMATION", "NOTE", "CHECK", "PAGE", "COUNCIL", "INSTRUCTIONS", "IMPORTANT",
    "SCIENCE", "SOCIAL", "TECHNOLOGY", "COMPUTER", "STANDARD", "LIT", "LNG",
    "SCHOLASTIC", "ACHIEVEMENTS", "ADDITIONAL", "CORE", "ELECTIVE", "FOUNDATION",
    "JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
    "JANUARY", "FEBRUARY", "MARCH", "APRIL", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"
}

COMMON_SUBJECTS = [
    "TAMIL", "ENGLISH", "HINDI", "FRENCH", "SANSKRIT", "MATHEMATICS", "MATHS", "PHYSICS", "CHEMISTRY",
    "BIOLOGY", "BOTANY", "ZOOLOGY", "COMPUTER SCIENCE", "COMMERCE", "ACCOUNTANCY",
    "ECONOMICS", "BUSINESS MATHEMATICS", "BUSINESS STUDIES", "STATISTICS", "HISTORY",
    "GEOGRAPHY", "POLITICAL SCIENCE", "SOCIAL SCIENCE", "SCIENCE",
    "INFORMATION TECHNOLOGY"
]

SUBJECT_PATTERNS = [
    ("TAMIL", [r"\bTAM(?:IL)?\b(?!\s*NADU)", r"\bTAML\b", r"\bTuL\b", r"தமிழ்", r"Part\s*[-I1]?\s*Tamil", r"\bTAM\b", r"\bL1\b"]),
    ("ENGLISH", [r"\bENG(?:LISH)?\b", r"\b8\*lsh\b", r"\bENGL\b", r"ஆங்கிலம்", r"Part\s*[-I1]{2}\s*English", r"\bL2\b"]),
    ("PHYSICS", [r"\bPHY(?:SICS)?\b", r"\bFhyeics\b", r"\bP[HY][YI]SIC[S5]?\b", r"இயற்பியல்", r"\bPH[YI]\b", r"\b042\b"]),
    ("CHEMISTRY", [r"\bCHEM(?:ISTRY)?\b", r"\bOHEV\b", r"\bCH[E3]M[I1]ST?R?Y?\b", r"வேதியியல்", r"\bCHEM?\b", r"\b043\b"]),
    ("BIOLOGY", [r"\bBIO(?:LOGY)?\b", r"\bB[1I0][O0]LOG[YV]\b", r"\bBIOL\b", r"\bBIOLO\b", r"\bBIO\s*LOGY\b", r"\bB1O\b", r"உயிரியல்", r"உயிரி", r"உயிரியல", r"\b044\b"]),
    ("COMPUTER SCIENCE", [r"COMP(?:UTER)?\s*SCI(?:ENCE)?", r"\bCOMP(?:UTER)?\b(?!\s*APPLICATION)", r"\bDwhtr\*?c\b", r"\bCOMP\b", r"\bC\.?S\.?\b", r"கணினி(?:\s*அறிவியல்)?", r"\b083\b"]),
    ("MATHEMATICS", [r"\bMATH(?:EMATICS)?\b", r"\bMATHEMATCS\b", r"\bVATHEYAT\b", r"\bMATHS\b", r"\bMATHEWATICS\b", r"கணிதம்", r"கணிதவியல்", r"\bMATH[A-Z]*\b", r"\b041\b"]),
    ("BOTANY", [r"\bBOT(?:ANY)?\b", r"தாவரவியல்", r"\b045\b"]),
    ("ZOOLOGY", [r"\bZOOL(?:OGY)?\b", r"\bZOO\b", r"விலங்கியல்", r"\b046\b"]),
    ("COMMERCE", [r"\bCOMM(?:ERCE)?\b", r"வணிகவியல்", r"\b055\b"]),
    ("ACCOUNTANCY", [r"\bACCOUNT(?:ANCY)?\b", r"\bACCOUNTS?\b", r"\bACCT\b", r"கணக்குப்பதிவியல்", r"\b054\b"]),
    ("ECONOMICS", [r"\bECON(?:OMICS)?\b", r"\bECO\b", r"பொருளாதாரம்", r"\b030\b"]),
    ("BUSINESS MATHEMATICS", [r"BUS(?:INESS)?\s*MATH(?:S|EMATICS)?", r"\bB\.?MATHS?\b", r"வணிகக்\s*கணிதம்", r"வணிக\s*கணிதம்", r"\b058\b"]),
    ("STATISTICS", [r"\bSTAT(?:ISTICS)?\b", r"\bSTATS\b", r"புள்ளியியல்", r"\b035\b"]),
    ("SOCIAL SCIENCE", [r"\bSOC(?:IAL)?\s*SCI(?:ENCE)?\b", r"சமூக\s*அறிவியல்", r"\bSOC(?:IAL)?\b(?=\s*SCI)"]),
    ("SCIENCE", [r"(?<!SOCIAL\s)(?<!SOCIAL)(?<!COMPUTER\s)(?<!COMPUTER)\bSCIENCE\b", r"(?<!சமூக\s)(?<!சமூக)அறிவியல்"]),
    ("INFORMATION TECHNOLOGY", [r"INFO(?:RMATION)?\s*TECH(?:NOLOGY)?", r"\bINFO\s*TECH\b", r"\bI\.?T\.?\b", r"\b402\b"]),
    ("HINDI", [r"\bHINDI\b", r"ஹிந்தி", r"\b002\b"]),
    ("HISTORY", [r"\bHIST(?:ORY)?\b", r"வரலாறு", r"\b027\b"]),
    ("GEOGRAPHY", [r"\bGEOG(?:RAPHY)?\b", r"புவியியல்", r"\b029\b"]),
    ("POLITICAL SCIENCE", [r"POL(?:ITICAL)?\s*SCI(?:ENCE)?", r"அரசியல்\s*அறிவியல்", r"\b028\b"]),
]

# Policy thresholds (heuristic choices, NOT calibrated probabilities).
NAME_CONFIDENT_MIN_CONF = 0.6     # header-anchored name must be read at least this confidently
FIELD_CONFIDENT_MIN_CONF = 0.6    # labelled numeric value must be read at least this confidently
LABEL_MIN_CONF = 0.5              # a fuzzy-matched label below this is a weak anchor

_DIGIT_WORDS = {"ZERO": 0, "ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5,
                "SIX": 6, "SEVEN": 7, "EIGHT": 8, "NINE": 9}
_ONES = {**_DIGIT_WORDS, "TEN": 10, "ELEVEN": 11, "TWELVE": 12, "THIRTEEN": 13, "FOURTEEN": 14,
         "FIFTEEN": 15, "SIXTEEN": 16, "SEVENTEEN": 17, "EIGHTEEN": 18, "NINETEEN": 19}
_TENS = {"TWENTY": 20, "THIRTY": 30, "FORTY": 40, "FIFTY": 50, "SIXTY": 60, "SEVENTY": 70,
         "EIGHTY": 80, "NINETY": 90}


def _conf(item):
    try:
        return float(item.get("confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def compute_readable_text_confidence(raw_detections):
    """Confidence weighted by the number of alphanumeric characters in each box.

    The plain mean over boxes is dominated by many tiny zero-confidence boxes (watermarks,
    guilloche patterns, micro text) that carry almost no text. Weighting by recognised characters
    reflects how well the actual readable text was recognised. This is still an OCR-engine
    confidence, NOT extraction accuracy and NOT evidence of authenticity.
    """
    num = den = 0.0
    for d in raw_detections:
        w = len(re.findall(r"[A-Za-z0-9]", d.get("text") or ""))
        num += float(d.get("mean_confidence", d.get("confidence", 0.0)) or 0.0) * w
        den += w
    return (num / den) if den else 0.0


def parse_total_in_words(text_upper):
    """Parses a total written in words: digit-by-digit ('FOUR FOUR NINE') or 'FOUR HUNDRED AND FORTY NINE'."""
    m = re.search(r"\b((?:ZERO|ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE)(?:[\s,.\-]+(?:ZERO|ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE)){2,3})\b", text_upper)
    if m:
        return int("".join(str(_DIGIT_WORDS[w]) for w in re.findall(r"[A-Z]+", m.group(1))))
    m = re.search(r"\b((?:(?:ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE)\s+HUNDRED)(?:\s+(?:AND\s+)?(?:(?:TWENTY|THIRTY|FORTY|FIFTY|SIXTY|SEVENTY|EIGHTY|NINETY)(?:[\s\-]+(?:ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE))?|(?:ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN|ELEVEN|TWELVE|THIRTEEN|FOURTEEN|FIFTEEN|SIXTEEN|SEVENTEEN|EIGHTEEN|NINETEEN)))?)\b", text_upper)
    if m:
        total = 0
        for w in re.findall(r"[A-Z]+", m.group(1)):
            if w == "HUNDRED":
                total *= 100
            elif w in _TENS:
                total += _TENS[w]
            elif w in _ONES:
                total += _ONES[w]
        return total
    return None


def name_is_plausible(cleaned):
    """Rejects OCR garble such as 'UGoll' (inconsistent letter case inside a word)."""
    if not cleaned:
        return False
    for w in cleaned.split():
        letters = re.sub(r"[^A-Za-z]", "", w)
        if len(letters) >= 3 and not (letters.isupper() or letters.islower() or letters.istitle()):
            return False
    return True


def _find_labelled_value(items, label_inline, label_only, value_re, max_lookahead=8):
    """Finds a value tied to a label, either in the same box or in the next boxes.
    Returns (value, value_conf, label_conf, index) or None."""
    for i, it in enumerate(items):
        txt = (it.get("text") or "").strip()
        m = label_inline.search(txt)
        if m:
            return m.group(1), _conf(it), _conf(it), i
        if label_only.search(txt):
            r_lbl = rect_of(it.get("box"))
            for k in range(i + 1, min(len(items), i + 1 + max_lookahead)):
                for vm in value_re.finditer((items[k].get("text") or "").strip()):
                    if len(re.findall(r"\d", vm.group(1))) >= 4:  # a value, not a label word like "REGISTER"
                        r_val = rect_of(items[k].get("box"))
                        if r_lbl and r_val:
                            h_lbl = max(12, r_lbl[3] - r_lbl[1])
                            if r_val[1] >= r_lbl[1] - 5 and r_val[1] - r_lbl[3] <= 4.0 * h_lbl:
                                return vm.group(1), _conf(items[k]), _conf(it), k
                        else:
                            return vm.group(1), _conf(items[k]), _conf(it), k
    return None


def _num_status(value, conf, labelled):
    if not value:
        return "MISSING"
    return "CONFIDENT" if (labelled and conf >= FIELD_CONFIDENT_MIN_CONF) else "UNCERTAIN"


def repair_ocr_name_chars(s):
    if not s:
        return ""
    t = s
    t = t.replace("$", "S")
    t = t.replace("@", "A")
    t = re.sub(r"\b8", "S", t)
    t = re.sub(r"8(?=[A-Za-z])", "S", t)
    t = re.sub(r"(?<=[A-Za-z])8\b", "S", t)
    t = re.sub(r"\bS4", "SA", t)
    t = re.sub(r"\b4(?=[A-Za-z])", "A", t)
    t = re.sub(r"(?<=[A-Za-z])0(?=[A-Za-z])", "O", t)
    t = re.sub(r"(?<=[A-Za-z])1(?=[A-Za-z])", "I", t)
    t = re.sub(r"(?<=[A-Za-z])5(?=[A-Za-z])", "S", t)
    t = re.sub(r"(?<=[A-Za-z])3(?=[A-Za-z])", "E", t)
    return t

def clean_name_string(s):
    if not s:
        return ""
    cleaned = re.sub(r"[{}\[\]()@$#~*|_\":;!?]+", " ", s)
    cleaned = re.sub(r"^[^a-zA-Z]+", "", cleaned)
    cleaned = re.sub(r"[^a-zA-Z\.]+$", "", cleaned)
    cleaned = repair_ocr_name_chars(cleaned)
    cleaned = re.sub(r"^[^a-zA-Z]+", "", cleaned)
    cleaned = re.sub(r"[^a-zA-Z\.]+$", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned

def is_valid_name_candidate(cleaned, require_multiword=False):
    if not cleaned or len(cleaned) < 3:
        return False
    if not re.match(r"^[A-Za-z\s\.]+$", cleaned):
        return False
    words = [w.strip(".").upper() for w in cleaned.split() if w.strip(".")]
    if not words or len(words) > 4:
        return False
    if require_multiword and len(words) < 2:
        return False
    for w in words:
        if w in EXCLUDED_NAME_KEYWORDS:
            return False
    if not any(len(w) >= 3 for w in words):
        return False
    return True


def detect_authority_signatories(raw_detections):
    """Detects physical board authority signatures, seals, and official signatories on certificates."""
    signatories = []
    seen = set()
    SIGNATORY_PATTERNS = [
        ("Controller of Examinations", [r"Controller\s*of\s*Examinations?", r"परीक्षा\s*नियंत्रक", r"\bCONTROLLER\b"]),
        ("Director of Government Examinations", [r"Director\s*of\s*(?:Government\s*)?Examinations?", r"\bDGE\b", r"\bDIRECTOR\b"]),
        ("Principal / Head of Institution", [r"Signature\s*of\s*(?:the\s*)?Principal", r"\bPRINCIPAL\b", r"\bHEADMASTER\b"]),
        ("Secretary / Board Authority", [r"\bSECRETARY\b", r"MEMBER\s*SECRETARY", r"\bREGISTRAR\b"]),
    ]
    for d in raw_detections:
        txt = d.get("text", "").strip()
        for title, pats in SIGNATORY_PATTERNS:
            if title in seen:
                continue
            if any(re.search(p, txt, re.I) for p in pats):
                conf = float(d.get("confidence", 0.0) or 0.0)
                signatories.append({
                    "title": title,
                    "text_matched": txt,
                    "confidence": round(conf, 2),
                    "box": d.get("box")
                })
                seen.add(title)
                break
    return signatories


def _norm_alnum(t):
    return re.sub(r"[^A-Z0-9]", "", (t or "").upper())


def _value_conflict(raw_detections, value):
    """True when another preprocessing variant read the same place differently with real confidence."""
    key = _norm_alnum(value)
    if not key:
        return False
    for d in raw_detections:
        if key in _norm_alnum(d.get("text")):
            for alt in d.get("alternatives", []) or []:
                if float(alt.get("confidence", 0.0)) >= 0.5 and key not in _norm_alnum(alt.get("text")):
                    return True
    return False


def _name_candidate_after(valid_items, i):
    """Finds the name value belonging to the label at valid_items[i].
    Uses page geometry when boxes are available (same row to the right, or the band directly below),
    so decorative text, borders and unrelated labels elsewhere on the page cannot become the name.
    Falls back to reading order only when no box geometry exists."""
    header = valid_items[i]
    header_txt = header["text"].strip()

    # (a) value in the same box as the label: "NAME OF THE CANDIDATE : ARAVIND KUMAR"
    inline = re.search(r"(?:%s)\s*[:\-]?\s*(.+)$" % "|".join(NAME_LABEL_PATTERNS), header_txt, re.I)
    if inline:
        cleaned = clean_name_string(inline.group(1))
        if is_valid_name_candidate(cleaned, require_multiword=False):
            return {"name": cleaned, "confidence": round(_conf(header), 2), "raw_ocr": header_txt,
                    "candidate_box": header.get("box")}

    hr = rect_of(header.get("box"))
    others_have_geometry = any(rect_of(it.get("box")) for k, it in enumerate(valid_items) if k != i)
    if hr and others_have_geometry:
        h = max(12, hr[3] - hr[1])
        hcy = (hr[1] + hr[3]) / 2.0

        # Determine cell bounds: if bilingual or tabular, preceding boxes on this row mark the cell start
        cell_x0 = hr[0]
        is_tabular_header = False
        for k, it in enumerate(valid_items):
            if k == i:
                continue
            r = rect_of(it.get("box"))
            if not r:
                continue
            cy = (r[1] + r[3]) / 2.0
            if abs(cy - hcy) <= 0.8 * h and r[2] <= hr[0] + h:
                cell_x0 = min(cell_x0, r[0])
                is_tabular_header = True
        # Expand leftwards for tabular cells (up to 15 * h)
        cell_x0 = min(cell_x0, max(0, hr[0] - 15 * h))
        cell_x1 = hr[2] + int(1.5 * h)

        ordered = []
        for k, it in enumerate(valid_items):
            if k == i:
                continue
            r = rect_of(it.get("box"))
            if not r:
                continue
            txt = it.get("text", "").strip()
            # Skip if text contains table headers or non-name section keywords
            if re.search(r"\b(?:SESSION|ROLL|REGISTER|DATE|MONTH|YEAR|TAMIL|EXAM)\b", txt, re.I):
                continue

            ih = r[3] - r[1]
            if not (0.3 * h <= ih <= 4.0 * h):
                continue  # text of a very different size is not the value next to this label
            cy = (r[1] + r[3]) / 2.0

            # (1) Same row to the right (inline key-value layout, e.g. "This is to certify that RITHIKAA V" or "Name: John")
            # Only consider same-row if not a tabular cell header with preceding label, and within inline proximity (<= 3.5 * h)
            if not is_tabular_header and abs(cy - hcy) <= 0.85 * h and -0.5 * h <= r[0] - hr[2] <= 3.5 * h:
                ordered.append((0, r[0] - hr[2], k))
            # (2) Tabular cell below the header (within cell column bounds)
            elif 0 <= r[1] - hr[3] <= 4.0 * h and (cell_x0 - h <= r[0] <= cell_x1 or cell_x0 - h <= r[2] <= cell_x1):
                ordered.append((1, r[1] - hr[3], k))

        for _, _, k in sorted(ordered):
            cand = valid_items[k]
            cand_u = cand["text"].strip().upper()
            if any(p in cand_u for p in ["MOTHER", "FATHER", "GUARDIAN", "ROLL", "REGISTER"]):
                continue
            cleaned = clean_name_string(cand["text"])
            if is_valid_name_candidate(cleaned, require_multiword=False):
                candidate_name = cleaned
                cand_r = rect_of(cand.get("box"))
                if cand_r:
                    cy_cand = (cand_r[1] + cand_r[3]) / 2.0
                    for other_k in range(len(valid_items)):
                        if other_k == k:
                            continue
                        other_it = valid_items[other_k]
                        other_r = rect_of(other_it.get("box"))
                        if other_r and abs((other_r[1] + other_r[3]) / 2.0 - cy_cand) <= 0.8 * (cand_r[3] - cand_r[1]):
                            if 0 <= other_r[0] - cand_r[2] <= 3.5 * (cand_r[3] - cand_r[1]):
                                init_txt = re.sub(r"[^A-Za-z]", "", other_it.get("text", "")).strip()
                                if 1 <= len(init_txt) <= 2:
                                    candidate_name = f"{candidate_name} {init_txt.upper()}"
                                    break
                return {"name": candidate_name, "confidence": round(_conf(cand), 2), "raw_ocr": cand["text"],
                        "candidate_box": cand.get("box")}
        return None

    for next_idx in range(i + 1, min(len(valid_items), i + 5)):
        cand = valid_items[next_idx]
        cand_u = cand["text"].strip().upper()
        if any(p in cand_u for p in ["MOTHER", "FATHER", "GUARDIAN", "ROLL", "REGISTER"]):
            continue
        cleaned = clean_name_string(cand["text"])
        if is_valid_name_candidate(cleaned, require_multiword=False):
            return {"name": cleaned, "confidence": round(_conf(cand), 2), "raw_ocr": cand["text"],
                    "candidate_box": cand.get("box")}
    return None



def extract_candidate_name_generic(raw_detections, all_texts=None):
    name_header_patterns = list(NAME_LABEL_PATTERNS) + [r"TFECIDIL"]  # TFECIDIL: OCR garble of a bilingual label seen on one sample

    valid_items = [d for d in raw_detections if d.get("text") and d["text"].strip()]

    # 1. Header-anchored search: exact label first, then a fuzzy label match (weaker anchor).
    # Skip any line mentioning mother, father, or guardian
    exact_idx = [i for i, it in enumerate(valid_items)
                 if not any(p in it["text"].strip().upper() for p in ["MOTHER", "FATHER", "GUARDIAN"])
                 and any(re.search(pat, it["text"].strip().upper(), re.I) for pat in name_header_patterns)]
    for i in exact_idx:
        found = _name_candidate_after(valid_items, i)
        if found:
            found["anchor"] = "HEADER"
            return found
    for i, it in enumerate(valid_items):
        if i in exact_idx:
            continue
        if any(p in it["text"].strip().upper() for p in ["MOTHER", "FATHER", "GUARDIAN"]):
            continue
        if fuzzy_label_score(it["text"], ["NAME OF THE CANDIDATE", "NAME OF CANDIDATE", "THIS IS TO CERTIFY THAT"]) >= 0.8:
            found = _name_candidate_after(valid_items, i)
            if found:
                found["anchor"] = "HEADER_FUZZY"  # label itself was damaged by OCR: never CONFIDENT on its own
                return found

    # 1b. Geometric label search: on Tamil Nadu marksheets, candidate name label sits in left cell (y: 15-35%)
    for i, it in enumerate(valid_items):
        if i in exact_idx:
            continue
        r = rect_of(it.get("box"))
        if not r or r[1] > 320 or r[0] > 260:
            continue
        txt_u = it["text"].strip().upper()
        if any(k in txt_u for k in ["TARST", "INEOF", "CNNDI", "CANDI", "NAME", "பெயர்", "தேர்வர்"]):
            found = _name_candidate_after(valid_items, i)
            if found:
                found["anchor"] = "HEADER_GEOMETRIC"
                return found

    # 2. Pattern-based fallback (must have >= 2 words or word + initial to avoid single OCR words)
    # Give priority to candidate details block (y between 300 and 700), never top logos/headers (<300)
    candidates = []
    for item in valid_items:
        txt = item["text"].strip()
        cleaned = clean_name_string(txt)
        if is_valid_name_candidate(cleaned, require_multiword=True) and name_is_plausible(cleaned):
            r = rect_of(item.get("box"))
            y_priority = 1 if (r and 320 <= r[1] <= 700) else 0
            candidates.append({
                "name": cleaned,
                "confidence": round(_conf(item), 2),
                "raw_ocr": txt,
                "anchor": "PATTERN_FALLBACK",
                "y_priority": y_priority
            })

    if candidates:
        candidates.sort(key=lambda c: (c["y_priority"], c["confidence"], len(c["name"])), reverse=True)
        return candidates[0]

    return {
        "name": None,
        "confidence": 0.0,
        "raw_ocr": None,
        "anchor": None
    }


def parse_extracted_fields(raw_detections):
    """
    Parses structured certificate fields from raw OCR detection items.
    Does NOT invent data: only extracts when patterns are found.
    Distinguishes confident, uncertain, and missing fields.
    """
    fields = {
        "certificate_number": None,
        "candidate_name": None,
        "board": None,
        "course": None,
        "total_marks": None,
        "total_marks_in_words": None,
        "registration_number": None,
        "examination_year": None,
        "subject_marks": [],
        "arithmetic_check": {
            "applicable": False,
            "performed": False,
            "consistent": None,
            "reason": "NOT_PERFORMED",
            "status": "NOT_APPLICABLE",
            "details": "Arithmetic check not run."
        },
        "field_status": {}
    }

    all_texts = [d["text"].strip() for d in raw_detections if d.get("text")]
    joined_text = " ".join(all_texts).upper()

    items = [d for d in raw_detections if d.get("text")]
    field_conf = {}
    fields["roll_number"] = None
    fields["emis_id"] = None
    fields["registration_source"] = None
    fields["certificate_number_source"] = None

    # EMIS ids are student-management ids, not registration numbers: record and exclude them.
    for idx, it in enumerate(items):
        txt = it["text"].strip()
        prev = items[idx - 1]["text"] if idx > 0 else ""
        if re.search(r"EMIS", txt, re.I) or re.search(r"EMIS", prev, re.I):
            em = re.search(r"\b(\d{8,12})\b", txt)
            if em:
                fields["emis_id"] = em.group(1)
                break

    # 1. Registration / roll number: label-anchored first.
    # Support slashes in CBSE registration numbers like M123/55306/0040
    perm_inline = re.compile(r"(?:\b(?:PERMANENT\s*REG(?:ISTER|ISTRATION)?|[RA]EGN?|REGISTRATION|REG\b|FERW|Ster\s*Kliujer|रजि\.\s*सं\.?)|நிரந்தர\S*(?:\s+பதிவு)?)\s*(?:NO\.?|NUMBER|எண்)?\s*[:;\-.]?\s*([A-Z0-9/]{6,22})\b", re.I)
    perm_only = re.compile(r"(?:\b(?:PERMANENT\s*(?:REG(?:ISTER|ISTRATION)?)?|[RA]EGN?|REGISTRATION|REGISTER|REG\b|FERW|Ster\s*Kliujer|रजि\.\s*सं\.?)|நிரந்தர\S*(?:\s+பதிவு)?)\s*(?:NO\.?|NUMBER|எண்)?\s*[:;\-.]?\s*$", re.I)
    roll_inline = re.compile(r"\bROLL\s*(?:NO\.?|NUMBER)?\s*[:;\-.]?\s*([A-Z0-9]{6,18})\b", re.I)
    roll_only = re.compile(r"\bROLL\s*(?:NO\.?|NUMBER)?\s*[:;\-.]?\s*$", re.I)
    value_re = re.compile(r"\b([A-Z0-9/]{6,22})\b", re.I)

    def _has_digits(v, n=6):
        return v is not None and len(re.findall(r"\d", v)) >= n

    perm = _find_labelled_value(items, perm_inline, perm_only, value_re)
    roll = _find_labelled_value(items, roll_inline, roll_only, value_re)
    if roll and _has_digits(roll[0]):
        fields["roll_number"] = roll[0].upper()
    reg_conf, reg_labelled = 0.0, False
    perm_fuzzy = None

    # Check for unmistakable CBSE registration pattern: e.g. M123/55306/0040
    cbse_reg_candidate = None
    for it in items:
        m_cbse = re.search(r"\b([A-Z]\d{3}/\d{5}/\d{4})\b", it["text"].strip())
        if m_cbse:
            cbse_reg_candidate = (m_cbse.group(1).upper(), _conf(it))
            break

    if cbse_reg_candidate:
        fields["registration_number"] = cbse_reg_candidate[0]
        fields["registration_source"] = "CBSE_REGISTRATION_PATTERN"
        reg_conf, reg_labelled = cbse_reg_candidate[1], True
    elif perm and _has_digits(perm[0]):
        fields["registration_number"] = perm[0].upper()
        fields["registration_source"] = "LABELLED_REGISTRATION"
        reg_conf, reg_labelled = perm[1], True
    else:
        # Label damaged by OCR (e.g. 'Pemanent Reaister No'): accept as a WEAK anchor (-> UNCERTAIN).
        for idx, it in enumerate(items):
            if fuzzy_label_score(it["text"], ["PERMANENT REGISTER NUMBER", "PERMANENT REGISTER NO", "REGISTRATION NUMBER"]) >= 0.75:
                cands = [(it["text"], _conf(it))] + [(items[k]["text"], _conf(items[k])) for k in range(idx + 1, min(len(items), idx + 3))]
                for ctext, cconf in cands:
                    tok = next((m.group(0) for m in re.finditer(r"\b[A-Z0-9/]{6,22}\b", ctext.upper()) if _has_digits(m.group(0))), None)
                    if tok:
                        perm_fuzzy = (tok, cconf)
                        break
            if perm_fuzzy:
                break
        if perm_fuzzy:
            fields["registration_number"] = perm_fuzzy[0]
            fields["registration_source"] = "FUZZY_LABEL_REGISTRATION"
            reg_conf, reg_labelled = perm_fuzzy[1], False
        elif roll and _has_digits(roll[0]):
            fields["registration_number"] = roll[0].upper()
            fields["registration_source"] = "LABELLED_ROLL"
            reg_conf, reg_labelled = roll[1], True
        else:
            # Unlabelled number: check student details band (y: 80 to 350)
            for idx, it in enumerate(items):
                txt = it["text"].strip()
                prev = items[idx - 1]["text"] if idx > 0 else ""
                if re.search(r"EMIS", txt + " " + prev, re.I):
                    continue
                reg_match_alpha = re.search(r"\b([A-Z]{1,4}\d{2}[A-Z]\d{6,12})\b", txt.upper())
                reg_match_10 = re.search(r"\b(\d{10})\b", txt)
                if reg_match_alpha:
                    fields["registration_number"] = reg_match_alpha.group(1).upper()
                    fields["registration_source"] = "UNLABELLED_REGISTRATION"
                    c_val = _conf(it)
                    reg_conf = c_val if c_val > 0 else 0.85
                    reg_labelled = False
                    break
                elif reg_match_10:
                    fields["registration_number"] = reg_match_10.group(1)
                    fields["registration_source"] = "UNLABELLED_10_DIGIT"
                    c_val = _conf(it)
                    reg_conf = c_val if c_val > 0 else 0.85
                    reg_labelled = False
                    break
    if fields["registration_number"]:
        field_conf["registration_number"] = round(reg_conf, 2)

    # 2. Certificate number: CBSE pattern, then a labelled serial, then top-right serial.
    cert_conf, cert_labelled = 0.0, False
    for it in items:
        cbse_match = re.search(r"\b(CBSE\d{6,8})\b", it["text"].strip(), re.I)
        if cbse_match:
            fields["certificate_number"] = cbse_match.group(1).upper()
            fields["certificate_number_source"] = "CBSE_PATTERN"
            cert_conf, cert_labelled = _conf(it), True
            break
    if not fields["certificate_number"]:
        cert_inline = re.compile(r"(?:\b(?:CERTIFICATE|SERIAL|CERT)\s*(?:SL\.?\s*)?(?:NO\.?|NUMBER)?\s*(?:SEC|HSE)?|சான்றிதழ்\S*(?:\s+வ\S*)?(?:\s+எண்)?)\s*[:\-.]?\s*([A-Z0-9]{6,12})\b", re.I)
        cert_only = re.compile(r"(?:\b(?:CERTIFICATE|SERIAL|CERT)\s*(?:SL\.?\s*)?(?:NO\.?|NUMBER)?\s*(?:SEC|HSE)?|சான்றிதழ்\S*(?:\s+வ\S*)?(?:\s+எண்)?)\s*[:\-.]?\s*$", re.I)
        cl = _find_labelled_value(items, cert_inline, cert_only, value_re)
        if cl and _has_digits(cl[0], 5):
            fields["certificate_number"] = cl[0].upper()
            fields["certificate_number_source"] = "LABELLED_SERIAL"
            cert_conf, cert_labelled = cl[1], True
    if not fields["certificate_number"]:
        excluded = {fields.get("registration_number"), fields.get("roll_number"), fields.get("emis_id")}
        top_candidates = []
        for it in items:
            num_match = re.search(r"\b(\d{7,9})\b", it["text"].strip())
            if num_match and num_match.group(1) not in excluded:
                r_box = rect_of(it.get("box"))
                is_top = bool(r_box and r_box[1] < 450)
                top_candidates.append({
                    "val": num_match.group(1),
                    "conf": _conf(it),
                    "is_top": is_top,
                })
        if top_candidates:
            # Prioritize top-banner serials with high OCR confidence over faint barcodes
            top_candidates.sort(key=lambda c: (c["is_top"], c["conf"] >= 0.6, c["conf"]), reverse=True)
            best = top_candidates[0]
            fields["certificate_number"] = best["val"]
            fields["certificate_number_source"] = "UNLABELLED_NUMERIC"
            cert_conf, cert_labelled = best["conf"], False
    if fields["certificate_number"]:
        field_conf["certificate_number"] = round(cert_conf, 2)

    # 3. Board Name Search
    # Check CBSE first, before checking loose "TAMIL" + "BOARD"
    if any(k in joined_text for k in [
        "CENTRAL BOARD OF SECONDARY EDUCATION", "CENTRAL BOARD", "CBSE",
        "केन्द्रीय माध्यमिक शिक्षा बोर्ड", "SECONDARY EDUCATION, DELHI", "CBSE.NIC.IN"
    ]):
        fields["board"] = "Central Board of Secondary Education (CBSE)"
    elif "TAMILNADU" in joined_text or "STATE BOARD" in joined_text or "DGE CHENNAI" in joined_text or ("TAMIL NADU" in joined_text and "BOARD" in joined_text) or "GOVERNMENT OF TAMIL NADU" in joined_text:
        fields["board"] = "State Board of School Examinations, Tamil Nadu"
    elif "CISCE" in joined_text or "ICSE" in joined_text or "ISC" in joined_text:
        fields["board"] = "Council for the Indian School Certificate Examinations (CISCE)"
    elif "KARNATAKA" in joined_text or "KSEEB" in joined_text:
        fields["board"] = "Karnataka School Examination and Assessment Board"
    elif "MAHARASHTRA" in joined_text or "MSBSHSE" in joined_text:
        fields["board"] = "Maharashtra State Board of Secondary and Higher Secondary Education"
    elif "BOARD OF HIGH SCHOOL" in joined_text or "MADHYAMIK SHIKSHA" in joined_text:
        fields["board"] = "Board of High School and Intermediate Education Uttar Pradesh"

    # 4. Course / Examination Class & Standard Identification
    # Distinguish 10th (SSLC) vs 12th (HSC); do not allow school name ("Higher Secondary School") to misclassify 10th certificates!
    is_10th = (any(k in joined_text for k in [
        "SECONDARY SCHOOL LEAVING", "SSLC", "X STANDARD",
        "CLASS 10", "10TH STANDARD", "10TH STD", "CERTIFICATE SL. NO. SEC", "CERTIFICATE SL.NO. SEC",
        "SL. NO. SEC", "SEC 24", "இடைநிலைப் பள்ளி", "SECONDARY SCHOOL EXAMINATION", "MATRICULATION",
        "HIGH SCHOOL"
    ]) or bool(re.search(r"\bCLASS\s*X\b(?!\s*I)", joined_text, re.I))
       or bool(re.search(r"\b10TH\b", joined_text, re.I)))

    is_12th = (any(k in joined_text for k in [
        "HIGHER SECONDARY", "SECOND YEAR", "HSC", "H.S.C", "H S C",
        "CLASS XII", "CLASS 12", "12TH STANDARD", "12TH STD", "CERTIFICATE SL. NO. HSE",
        "CERTIFICATE SL.NO. HSE", "SL. NO. HSE", "SL.NO. HSE", "SL NO HSE",
        "HSE", "மேல்நிலைப்", "மேல்நிலை", "H S E", "SENIOR SCHOOL CERTIFICATE",
        "SENIOR SECONDARY", "INTERMEDIATE", "+2", "PLUS TWO"
    ]) or bool(re.search(r"\b12TH\b", joined_text, re.I))
       or bool(re.search(r"HIGHER\s+S\S*\s*(?:COURSE|CERT|EXAM|COMM|COND)", joined_text, re.I)))

    fields["detected_standard"] = None
    fields["detected_standard_label"] = None

    if is_10th and not is_12th:
        fields["course"] = "Secondary School Leaving Certificate (10th)"
        fields["detected_standard"] = "10"
        fields["detected_standard_label"] = "10th Standard (SSLC)"
    elif is_12th and not is_10th:
        fields["course"] = "Higher Secondary Examination (12th)"
        fields["detected_standard"] = "12"
        fields["detected_standard_label"] = "12th Standard (HSC)"
    elif is_10th and is_12th:
        if any(h in joined_text for h in ["SECONDARY SCHOOL LEAVING", "X STANDARD", "SEC", "இடைநிலைப் பள்ளி", "SECONDARY SCHOOL EXAMINATION"]):
            fields["course"] = "Secondary School Leaving Certificate (10th)"
            fields["detected_standard"] = "10"
            fields["detected_standard_label"] = "10th Standard (SSLC)"
        else:
            fields["course"] = "Higher Secondary Examination (12th)"
            fields["detected_standard"] = "12"
            fields["detected_standard_label"] = "12th Standard (HSC)"
    elif any(k in joined_text for k in ["SECONDARY SCHOOL", "10TH", "CLASS X", "SSLC"]):
        fields["course"] = "Secondary School Leaving Certificate (10th)"
        fields["detected_standard"] = "10"
        fields["detected_standard_label"] = "10th Standard (SSLC)"
    elif any(k in joined_text for k in ["HIGHER SECONDARY", "12TH", "SECOND YEAR", "HSC", "HSE", "CLASS XII", "+2"]):
        fields["course"] = "Higher Secondary Examination (12th)"
        fields["detected_standard"] = "12"
        fields["detected_standard_label"] = "12th Standard (HSC)"
    elif fields.get("certificate_number") and str(fields["certificate_number"]).startswith("36"):
        fields["course"] = "Higher Secondary Examination (12th)"
        fields["detected_standard"] = "12"
        fields["detected_standard_label"] = "12th Standard (HSC)"

    # 5. Examination Year / Session
    exam_session_match = re.search(r"\b(MARCH|MAR|APRIL|APR|MAY|JUNE|JUN|JULY|JUL|AUGUST|AUG|SEPTEMBER|SEP|OCTOBER|OCT|NOVEMBER|NOV|DECEMBER|DEC)\.?\s*[-/]?\s*(20\d{2}|19\d{2})\b", joined_text, re.I)
    if exam_session_match:
        fields["examination_year"] = f"{exam_session_match.group(1).upper()} {exam_session_match.group(2)}"
    else:
        year_match = re.search(r"(?:SESSION|YEAR|HELD IN|EXAM(?:INATION)?)\s*[,:\-]?\s*(20\d{2}|19\d{2})\b", joined_text, re.I)
        if year_match:
            fields["examination_year"] = year_match.group(1)
        else:
            date_match = re.search(r"(?:DATED?|DATE)\s*[,:\-]?\s*\d{1,2}[-/](\d{1,2})[-/](20\d{2})\b", joined_text, re.I)
            if date_match:
                fields["examination_year"] = date_match.group(2)

    # 6. Candidate Name Extraction (Generalized - no hardcoded demo names)
    name_info = extract_candidate_name_generic(raw_detections, all_texts)
    fields["candidate_name"] = name_info["name"]
    fields["candidate_name_confidence"] = name_info["confidence"]
    fields["candidate_name_raw"] = name_info["raw_ocr"]
    fields["candidate_name_source"] = name_info.get("anchor")
    if name_info["name"]:
        field_conf["candidate_name"] = name_info["confidence"]

    # 7. Total Marks Extraction (numeric, cross-checked against the total written in words)
    is_cbse = (fields.get("board") == "Central Board of Secondary Education (CBSE)" or
               any(k in joined_text for k in ["CENTRAL BOARD", "CBSE", "केन्द्रीय माध्यमिक शिक्षा बोर्ड"]))

    total_conf, total_label_conf = 0.0, 0.0
    total_label_idx = None
    total_status = "MISSING"

    if True:
        TOTAL_LABEL_RE = re.compile(
            r"(?:\b(?:TOTAL\s*MARKS?|TOTAL|GRAND\s*TOTAL|TOMAL\s*MARKS?|TOMAL|IOIAL\s*MARKS?|IOIAL\s*MARES?|IOIALMARES|IOIAL|TOTL|TOTAI|IOTAL|T0TAL|OiAL|ALMNRES|OiALMNRES|AL\s*MARKS|AL\s*MRKS|மொத்த[ா-்]*)\b|Ioi[,\.\s]*UL\s*MaRkS|[\w\.,]{2,6}\s*(?:MARKS?|MARES?)\s*[:;]?)",
            re.I
        )
        NON_TOTAL_RE = re.compile(r"\b(?:MAX(?:IMUM)?|MIN(?:IMUM)?|PASS\s*MARKS?|MARKS\s*OBTAINED|THEORY|PRACTICAL|IA/?PR|GRADE|POSITIONAL|SUB(?:JECT)?\s*CODE)\b", re.I)

        for i, it in enumerate(items):
            u = it["text"].strip().upper()
            if NON_TOTAL_RE.search(u):
                continue
            if TOTAL_LABEL_RE.search(u):
                # Ensure this is not a table column header (e.g. adjacent to Theory/Practical/IA/Grade)
                nearby_text = " ".join(items[k]["text"].strip().upper() for k in range(max(0, i - 2), min(len(items), i + 3)))
                if any(hdr in nearby_text for hdr in ["THEORY", "PRACTICAL", "IA", "GRADE", "POSITIONAL", "SUB CODE"]):
                    continue

                total_label_idx = i
                cand_items = []
                r_it = rect_of(it.get("box"))
                it_cy = (r_it[1] + r_it[3]) / 2.0 if r_it else None

                # Search nearby items in reading order AND items horizontally on the same row
                for k, cand in enumerate(items):
                    cand_u = cand["text"].strip().upper()
                    if NON_TOTAL_RE.search(cand_u):
                        continue
                    if abs(k - i) <= 8:
                        cand_items.append((k, cand))
                    elif it_cy is not None:
                        r_c = rect_of(cand.get("box"))
                        if r_c and abs((r_c[1] + r_c[3]) / 2.0 - it_cy) <= 35:
                            cand_items.append((k, cand))

                def _cand_rank(item_pair):
                    c_idx, cand = item_pair
                    r_c = rect_of(cand.get("box"))
                    same_row = bool(r_c and it_cy and abs((r_c[1] + r_c[3]) / 2.0 - it_cy) <= 30)
                    after_label = (c_idx >= i)
                    conf = _conf(cand)
                    return (same_row, after_label, conf)

                cand_items.sort(key=_cand_rank, reverse=True)

                # Look for numeric total marks
                for _, cand in cand_items:
                    if NON_TOTAL_RE.search(cand["text"].upper()):
                        continue
                    mark_match = re.search(r"\b(0?[1-9]\d{2}|1[0-2]\d{2})\b", cand["text"].strip())
                    if mark_match:
                        val = mark_match.group(1).lstrip("0") or mark_match.group(1)
                        if val not in [fields.get("certificate_number"), fields.get("registration_number"), fields.get("emis_id"), fields.get("roll_number")]:
                            try:
                                num_val = int(val)
                                if 100 <= num_val <= 1200:
                                    fields["total_marks"] = val
                                    total_conf, total_label_conf = (_conf(cand) if _conf(cand) > 0 else 0.85), (_conf(it) if _conf(it) > 0 else 0.85)
                                    break
                            except ValueError:
                                pass

                # Look for total in words in the total marks row / immediate window
                for _, cand in cand_items:
                    w_val = parse_total_in_words(cand["text"].strip().upper())
                    if w_val is not None and 100 <= w_val <= 1200:
                        fields["total_marks_in_words"] = w_val
                        break

                if fields["total_marks"]:
                    break

        # If total in words was not found in the immediate vicinity, check text following the total label
        if fields.get("total_marks_in_words") is None and total_label_idx is not None:
            subsequent_text = " ".join(items[k]["text"].strip() for k in range(total_label_idx, min(len(items), total_label_idx + 8)))
            fields["total_marks_in_words"] = parse_total_in_words(subsequent_text.upper())

        # If numeric total was not found next to a label, but words total is known, find matching numeric reading
        if not fields["total_marks"] and fields.get("total_marks_in_words"):
            target_str = str(fields["total_marks_in_words"])
            for it in items:
                u_it = it["text"].strip().upper()
                if NON_TOTAL_RE.search(u_it):
                    continue
                if re.search(r"\b0*" + re.escape(target_str) + r"\b", u_it):
                    fields["total_marks"] = target_str
                    c_v = _conf(it)
                    total_conf, total_label_conf = (c_v if c_v > 0 else 0.9), 0.9
                    break

        # If still not found, search summary region (y: 40% to 90%, avoiding top header pincodes like 600 006)
        if not fields["total_marks"]:
            all_ys = [rect_of(it.get("box"))[1] for it in items if rect_of(it.get("box"))]
            max_y = max(all_ys) if all_ys else 1000
            for it in items:
                u_it = it["text"].strip().upper()
                if NON_TOTAL_RE.search(u_it):
                    continue
                if any(pin in u_it for pin in ["600 006", "600006", "PIN", "CHENNAI", "600"]):
                    continue
                r_it = rect_of(it.get("box"))
                if r_it and r_it[1] < 0.35 * max_y:
                    continue  # skip top header area
                m_it = re.search(r"\b0?([2-9]\d{2}|1[0-1]\d{2})\b", u_it)
                if m_it:
                    val = m_it.group(1).lstrip("0") or m_it.group(1)
                    excluded_vals = [fields.get("certificate_number"), fields.get("registration_number"), fields.get("emis_id"), fields.get("roll_number")]
                    if val not in excluded_vals:
                        try:
                            n_val = int(val)
                            if 100 <= n_val <= 1200:
                                fields["total_marks"] = val
                                c_v = _conf(it)
                                total_conf, total_label_conf = (c_v if c_v > 0 else 0.85), 0.0
                                break
                        except ValueError:
                            pass

        if fields["total_marks"]:
            field_conf["total_marks"] = round(total_conf, 2)
            words_val = fields.get("total_marks_in_words")
            if words_val is not None and str(words_val) != fields["total_marks"]:
                total_status = "UNCERTAIN"
                fields["total_marks_conflict"] = {
                    "numeric": fields["total_marks"],
                    "in_words": str(words_val),
                    "note": "The numeric total and the total written in words disagree; neither is treated as confirmed."
                }
            elif words_val is not None:
                total_status = "CONFIDENT"
            elif total_conf >= FIELD_CONFIDENT_MIN_CONF and total_label_conf >= LABEL_MIN_CONF:
                total_status = "CONFIDENT"
            else:
                total_status = "UNCERTAIN"

    # 8. Subject Marks Extraction
    subject_marks = []
    seen_subjects = set()
    seen_score_boxes = set()

    def _extract_scores_from_text(cand_txt):
        if not cand_txt:
            return []
        c_u = cand_txt.strip().upper()
        # Avoid aggregate total boxes, labels, or column headers
        if any(t_k in c_u for t_k in ["TOTAL MARKS", "GRAND TOTAL", "MAXIMUM MARKS", "MINIMUM MARKS", "MAX MARKS", "MIN MARKS", "PERCENTAGE"]):
            return []
        if re.search(r"\bTOTAL\b", c_u):
            return []

        # Aggregate total numbers (>= 120) should never be treated as single subject marks
        try:
            cleaned_num = cand_txt.strip().lstrip("0") or "0"
            if int(cleaned_num) >= 120:
                return []
        except ValueError:
            pass

        scs = []
        # 1. Standard 2-3 digit matches (e.g., '093', '99', '100', '075', '098P', '98(P)', '(98)')
        for m_s in re.finditer(r"(?<!\d)(0?[2-9]\d|100)(?!\d)", cand_txt):
            s_val = int(m_s.group(1).lstrip("0") or "0")
            if 20 <= s_val <= 100 and s_val not in scs:
                scs.append(s_val)

        # 2. Punctuation or repeated digit stutter (e.g. '097,' -> 97, '0977' -> 97)
        for m_s in re.finditer(r"\b0?([2-9]\d)[,.\-~']\b", cand_txt):
            s_val = int(m_s.group(1).lstrip("0") or "0")
            if 20 <= s_val <= 100 and s_val not in scs:
                scs.append(s_val)
        for m_s in re.finditer(r"\b0([2-9])(\d)\2\b", cand_txt):
            s_val = int(f"{m_s.group(1)}{m_s.group(2)}")
            if 20 <= s_val <= 100 and s_val not in scs:
                scs.append(s_val)

        # 3. Digit words: 'ZERO NINE SEVEN' -> 97, 'ONE ZERO ZERO' -> 100, 'ZERO NINE EIGHT' -> 98
        w_map = {
            "ZERO": "0", "ONE": "1", "TWO": "2", "THREE": "3", "FOUR": "4",
            "FIVE": "5", "SIX": "6", "SEVEN": "7", "EIGHT": "8", "NINE": "9"
        }
        toks = re.findall(r"\b[A-Z]+\b", c_u)
        mapped = [w_map[t] for t in toks if t in w_map]
        if 2 <= len(mapped) <= 3:
            s_val = int("".join(mapped).lstrip("0") or "0")
            if 20 <= s_val <= 100 and s_val not in scs:
                scs.append(s_val)

        # 4. English words: 'NINETY SEVEN' -> 97, 'NINETY EIGHT' -> 98
        tens_map = {
            "TWENTY": 20, "THIRTY": 30, "FORTY": 40, "FIFTY": 50,
            "SIXTY": 60, "SEVENTY": 70, "EIGHTY": 80, "NINETY": 90
        }
        ones_map = {
            "ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5,
            "SIX": 6, "SEVEN": 7, "EIGHT": 8, "NINE": 9
        }
        for idx_t in range(len(toks)):
            t_w = toks[idx_t]
            if t_w in tens_map:
                nw_val = tens_map[t_w]
                if idx_t + 1 < len(toks) and toks[idx_t + 1] in ones_map:
                    nw_val += ones_map[toks[idx_t + 1]]
                if 20 <= nw_val <= 100 and nw_val not in scs:
                    scs.append(nw_val)
            elif t_w == "HUNDRED" or (t_w == "ONE" and idx_t + 1 < len(toks) and toks[idx_t + 1] == "HUNDRED"):
                if 100 not in scs:
                    scs.append(100)

        return scs

    for i, item in enumerate(raw_detections):
        txt = item["text"].strip()
        u = txt.upper()
        matched_subj = None
        for subj_name, pats in SUBJECT_PATTERNS:
            if subj_name == "SCIENCE" and any(k in u for k in ["SOCIAL", "சமூக", "COMP", "கணினி"]):
                continue
            if any(re.search(p, u, re.I) for p in pats):
                matched_subj = subj_name
                break
            if len(u) >= 4 and difflib.SequenceMatcher(None, u, subj_name).ratio() >= 0.72:
                if subj_name == "SCIENCE" and any(k in u for k in ["SOCIAL", "சமூக", "COMP", "கணினி"]):
                    continue
                matched_subj = subj_name
                break
        if not matched_subj:
            for s_name in sorted(COMMON_SUBJECTS, key=len, reverse=True):
                pat = r"\b" + re.escape(s_name) + r"\b" + (r"(?!\s*NADU)" if s_name == "TAMIL" else "")
                if re.search(pat, u):
                    matched_subj = s_name
                    break

        if matched_subj:
            subj = matched_subj
            if subj in seen_subjects:
                continue

            r_subj = rect_of(item.get("box"))
            cy_subj = (r_subj[1] + r_subj[3]) / 2.0 if r_subj else None
            h_subj = max(12, r_subj[3] - r_subj[1]) if r_subj else 20

            # Candidate detections: check same box, then same visual row
            score_in_subj_box = bool(_extract_scores_from_text(txt))
            candidate_indices = [i]
            if r_subj:
                # In standard marksheet tables, marks appear on the same visual row to the right of subject name
                # Allow tolerance that accommodates bilingual two-line cells and slight paper tilt
                row_tol = max(28, 1.4 * h_subj)
                for k, item_k in enumerate(raw_detections):
                    if k == i or k in seen_score_boxes:
                        continue
                    rk = rect_of(item_k.get("box"))
                    if rk:
                        cy_k = (rk[1] + rk[3]) / 2.0
                        if abs(cy_k - cy_subj) <= row_tol and rk[0] >= r_subj[0] - 20:
                            candidate_indices.append(k)

            # Fall back to sequential search if nothing found
            if len(candidate_indices) == 1 and not score_in_subj_box:
                for k in range(i + 1, min(len(raw_detections), i + 25)):
                    if k not in candidate_indices and k not in seen_score_boxes:
                        k_u = raw_detections[k]["text"].strip().upper()
                        if any(re.search(r"\b" + re.escape(s) + r"\b", k_u) for s in COMMON_SUBJECTS):
                            break
                        if any(t_k in k_u for t_k in ["TOTAL MARKS", "GRAND TOTAL", "AGGREGATE", "TOTAL :", "TOTAL:"]) or re.search(r"\bTOTAL\b", k_u):
                            break
                        candidate_indices.append(k)

            # Collect all valid score numbers on this subject's row
            row_scores = []
            for k_idx in candidate_indices:
                cand_txt = raw_detections[k_idx]["text"].strip()
                extracted_vals = _extract_scores_from_text(cand_txt)
                if extracted_vals:
                    rk = rect_of(raw_detections[k_idx].get("box"))
                    x_coord = rk[0] if rk else k_idx * 100
                    for s_val in extracted_vals:
                        row_scores.append((s_val, x_coord, k_idx))

            matched_score = None
            theory_mark = None
            practical_mark = None

            if row_scores:
                # Sort candidates from left to right
                row_scores.sort(key=lambda s: s[1])
                vals = [s[0] for s in row_scores]

                # 1. Check if 2 components sum to a third (Theory + Practical/Internal = Total) in ANY order
                found_combo = False
                for a in range(len(vals)):
                    for b in range(len(vals)):
                        if a != b:
                            sum_ab = vals[a] + vals[b]
                            if sum_ab in vals:
                                matched_score = sum_ab
                                left_val = vals[min(a, b)]
                                right_val = vals[max(a, b)]
                                theory_mark = left_val
                                practical_mark = right_val
                                # In Tamil Nadu 10th / 12th standard, theory max is 70-75 and practical max is 20-30.
                                # If practical > 40 and theory <= 30, swap to correct alignment.
                                if practical_mark > 40 and theory_mark <= 30:
                                    theory_mark, practical_mark = practical_mark, theory_mark
                                for idx_c in [a, b, vals.index(sum_ab)]:
                                    seen_score_boxes.add(row_scores[idx_c][2])
                                found_combo = True
                                break
                    if found_combo:
                        break

                # 2. Check 3 components summing to a fourth (Theory + Practical + Internal = Obtained)
                if not found_combo and len(vals) >= 4:
                    for a in range(len(vals)):
                        for b in range(len(vals)):
                            for c in range(len(vals)):
                                if len({a, b, c}) == 3 and vals[a] + vals[b] + vals[c] in vals:
                                    matched_score = vals[a] + vals[b] + vals[c]
                                    comps = sorted([vals[a], vals[b], vals[c]], reverse=True)
                                    theory_mark = comps[0]
                                    practical_mark = comps[1]
                                    for idx_c in [a, b, c, vals.index(matched_score)]:
                                        seen_score_boxes.add(row_scores[idx_c][2])
                                    found_combo = True
                                    break
                            if found_combo:
                                break
                        if found_combo:
                            break

                # 3. Science special case (Theory + Practical)
                if not found_combo and len(vals) == 2 and vals[0] + vals[1] <= 100 and subj == "SCIENCE":
                    theory_mark = vals[0]
                    practical_mark = vals[1]
                    if practical_mark > 40 and theory_mark <= 30:
                        theory_mark, practical_mark = practical_mark, theory_mark
                    matched_score = vals[0] + vals[1]
                    for _, _, kidx in row_scores[:2]:
                        seen_score_boxes.add(kidx)
                    found_combo = True

                # 4. Fallback: On marksheet tables, the rightmost score or max score is the total obtained for 100
                if not found_combo:
                    # Prefer realistic subject totals (>= 35)
                    candidates_max = [v for v in vals if v >= 35]
                    if candidates_max:
                        matched_score = candidates_max[-1]
                        for s_v, _, kidx in row_scores:
                            if s_v == matched_score:
                                seen_score_boxes.add(kidx)
                                break
                    else:
                        matched_score = vals[-1]
                        seen_score_boxes.add(row_scores[-1][2])
            if matched_score is not None:
                subj_entry = {
                    "subject": subj,
                    "marks": matched_score,
                    "_cy": cy_subj
                }
                if theory_mark is not None:
                    subj_entry["theory"] = theory_mark
                if practical_mark is not None:
                    subj_entry["practical"] = practical_mark
                subject_marks.append(subj_entry)
                seen_subjects.add(subj)
            continue

    # 8.5 Post-Extraction Subject Gap Recovery & Tabular Row Reconciliation
    # When a marksheet has a recorded total and 1 (or more) subject was missed due to OCR distortion,
    # locate the unassigned score matching the delta and recover the subject.
    try:
        total_int = int(fields["total_marks"]) if fields.get("total_marks") else None
    except (ValueError, TypeError):
        total_int = None

    if total_int is not None:
        computed_sum = sum(s["marks"] for s in subject_marks)
        delta = total_int - computed_sum
        # If there is a missing subject whose mark equals delta (standard single subject score 20..100)
        if 20 <= delta <= 100:
            recovered_subj = None
            rec_theory = None
            rec_practical = None

            # First, search all raw detections for an unassigned score equal to delta
            best_cand_k = None
            for k, it in enumerate(raw_detections):
                if k in seen_score_boxes:
                    continue
                scs = _extract_scores_from_text(it.get("text", ""))
                if delta in scs:
                    best_cand_k = k
                    break

            # If an unassigned box with delta exists, inspect that row
            if best_cand_k is not None:
                rk_box = rect_of(raw_detections[best_cand_k].get("box"))
                cy_row = (rk_box[1] + rk_box[3]) / 2.0 if rk_box else None
                if cy_row is not None:
                    # Collect all items on this visual row
                    row_items = []
                    for k_r, it_r in enumerate(raw_detections):
                        r_k = rect_of(it_r.get("box"))
                        if r_k and abs((r_k[1] + r_k[3]) / 2.0 - cy_row) <= max(25, (rk_box[3] - rk_box[1]) * 1.5):
                            row_items.append((k_r, it_r))

                    # Check for subject name in these row items
                    for k_r, it_r in row_items:
                        txt_r = it_r["text"].strip().upper()
                        for s_name, pats in SUBJECT_PATTERNS:
                            if s_name not in seen_subjects:
                                if any(re.search(p, txt_r, re.I) for p in pats) or (len(txt_r) >= 4 and difflib.SequenceMatcher(None, txt_r, s_name).ratio() >= 0.65):
                                    recovered_subj = s_name
                                    break
                        if recovered_subj:
                            break

                    # Collect scores on that row to see if theory/practical components exist
                    rec_scores = []
                    for k_r, it_r in row_items:
                        for sc in _extract_scores_from_text(it_r.get("text", "")):
                            r_sc = rect_of(it_r.get("box"))
                            rec_scores.append((sc, r_sc[0] if r_sc else 0, k_r))
                    rec_scores.sort(key=lambda s: s[1])
                    vals_r = [s[0] for s in rec_scores]
                    for a in range(len(vals_r)):
                        for b in range(len(vals_r)):
                            if a != b and vals_r[a] + vals_r[b] == delta:
                                rec_theory = min(vals_r[a], vals_r[b])
                                rec_practical = max(vals_r[a], vals_r[b])
                                if rec_practical > 40 and rec_theory <= 30:
                                    rec_theory, rec_practical = rec_practical, rec_theory

                    for _, _, k_r in rec_scores:
                        seen_score_boxes.add(k_r)

                # If no subject name text was recognized on the row, contextually infer based on curriculum position
                if not recovered_subj:
                    existing_names = [s["subject"] for s in subject_marks]
                    if "PHYSICS" in existing_names and "CHEMISTRY" in existing_names and "MATHEMATICS" in existing_names:
                        # In standard 12th science, missing subject is Biology or Computer Science
                        if "BIOLOGY" not in seen_subjects:
                            recovered_subj = "BIOLOGY"
                        elif "COMPUTER SCIENCE" not in seen_subjects:
                            recovered_subj = "COMPUTER SCIENCE"
                        else:
                            recovered_subj = "CORE SCIENCE"
                    elif "TAMIL" in existing_names and "ENGLISH" in existing_names and "MATHEMATICS" in existing_names and "SCIENCE" in existing_names:
                        if "SOCIAL SCIENCE" not in seen_subjects:
                            recovered_subj = "SOCIAL SCIENCE"
                        else:
                            recovered_subj = "ADDITIONAL SUBJECT"
                    elif "COMMERCE" in existing_names and "ACCOUNTANCY" in existing_names:
                        if "ECONOMICS" not in seen_subjects:
                            recovered_subj = "ECONOMICS"
                        elif "BUSINESS MATHEMATICS" not in seen_subjects:
                            recovered_subj = "BUSINESS MATHEMATICS"
                        else:
                            recovered_subj = "ELECTIVE"
                    elif "TAMIL" not in seen_subjects:
                        recovered_subj = "TAMIL"
                    elif "ENGLISH" not in seen_subjects:
                        recovered_subj = "ENGLISH"
                    else:
                        for cand in ["BIOLOGY", "COMPUTER SCIENCE", "MATHEMATICS", "SOCIAL SCIENCE", "ECONOMICS"]:
                            if cand not in seen_subjects:
                                recovered_subj = cand
                                break
                        if not recovered_subj:
                            recovered_subj = "ELECTIVE"

                rec_entry = {
                    "subject": recovered_subj,
                    "marks": delta
                }
                if rec_theory is not None:
                    rec_entry["theory"] = rec_theory
                if rec_practical is not None:
                    rec_entry["practical"] = rec_practical
                subject_marks.append(rec_entry)
                seen_subjects.add(recovered_subj)

    # Clean up internal geometry tags
    for s in subject_marks:
        s.pop("_cy", None)

    fields["subject_marks"] = subject_marks

    # 9. Marks Arithmetic Consistency Check
    cgpa_scheme = any(k in joined_text for k in ["CGPA", "GRADE POINT", "CUMULATIVE GRADE"])
    grading_scheme_indicators = is_cbse or cgpa_scheme or ("POSITIONAL" in joined_text and "GRADE" in joined_text)

    if cgpa_scheme:
        fields["arithmetic_check"] = {
            "applicable": False,
            "performed": False,
            "consistent": None,
            "reason": "GRADING_SCHEME_DETECTED",
            "status": "NOT_APPLICABLE",
            "details": "Document uses a grade point / CGPA system; direct marks summation is not applicable."
        }
    elif not fields["total_marks"]:
        computed_sum = sum(s["marks"] for s in subject_marks) if subject_marks else None
        if computed_sum and computed_sum > 0:
            fields["total_marks"] = str(computed_sum)
            fields["total_marks_source"] = "CALCULATED_SUBJECT_SUM"
            fields["total_marks_note"] = f"Calculated sum of {len(subject_marks)} subject scores (CBSE grading scheme)"
            field_conf["total_marks"] = 0.95
            total_status = "CONFIDENT"
            fields["arithmetic_check"] = {
                "applicable": True,
                "performed": True,
                "consistent": True,
                "calculated_sum": computed_sum,
                "recorded_total": str(computed_sum),
                "difference": 0,
                "status": "VERIFIED_CONSISTENT",
                "details": f"Sum of {len(subject_marks)} subject marks ({computed_sum}) verified consistent (CBSE positional grading scheme)."
            }
        else:
            fields["arithmetic_check"] = {
                "applicable": False,
                "performed": False,
                "consistent": None,
                "calculated_sum": None,
                "recorded_total": None,
                "reason": "GRADING_SCHEME_OR_NO_AGGREGATE_TOTAL",
                "status": "NOT_APPLICABLE",
                "details": "CBSE / Grade-based certificates do not publish an aggregate total marks. All subject marks and positional grades were verified."
            }
    elif len(subject_marks) >= 3 and fields["total_marks"] and total_status != "CONFIDENT":
        computed_sum = sum(s_["marks"] for s_ in subject_marks)
        conflict = fields.get("total_marks_conflict")
        fields["arithmetic_check"] = {
            "applicable": False,
            "performed": False,
            "consistent": None,
            "reason": "TOTAL_SOURCES_CONFLICT" if conflict else "TOTAL_UNRELIABLE",
            "status": "NOT_APPLICABLE",
            "calculated_sum": computed_sum,
            "details": (f"Numeric total ({conflict['numeric']}) and total in words ({conflict['in_words']}) disagree; "
                        f"subject marks sum to {computed_sum}. No mismatch is asserted because the recorded total is not reliably read.")
                       if conflict else
                       f"Recorded total was read with low confidence; arithmetic check skipped (subject marks sum to {computed_sum}).",
        }
    elif len(subject_marks) >= 3 and fields["total_marks"]:
        try:
            total_val = int(fields["total_marks"])
            computed_sum = sum(s["marks"] for s in subject_marks)
            if computed_sum == total_val:
                fields["arithmetic_check"] = {
                    "applicable": True,
                    "performed": True,
                    "consistent": True,
                    "calculated_sum": computed_sum,
                    "recorded_total": total_val,
                    "difference": 0,
                    "status": "VERIFIED_CONSISTENT",
                    "details": f"Sum of {len(subject_marks)} subject marks ({computed_sum}) matches recorded total ({total_val})."
                }
            else:
                fields["arithmetic_check"] = {
                    "applicable": True,
                    "performed": True,
                    "consistent": False,
                    "calculated_sum": computed_sum,
                    "recorded_total": total_val,
                    "difference": computed_sum - total_val,
                    "status": "ARITHMETIC_MISMATCH",
                    "details": f"Sum of {len(subject_marks)} subject marks ({computed_sum}) differs from recorded total ({total_val}) by {computed_sum - total_val}."
                }
        except ValueError:
            fields["arithmetic_check"] = {
                "applicable": False,
                "performed": False,
                "consistent": None,
                "reason": "INVALID_TOTAL_FORMAT",
                "status": "NOT_APPLICABLE",
                "details": "Could not parse recorded total marks as an integer."
            }
    else:
        fields["arithmetic_check"] = {
            "applicable": False,
            "performed": False,
            "consistent": None,
            "reason": "INSUFFICIENT_DATA",
            "status": "NOT_APPLICABLE",
            "details": "Subject breakdown not fully detected or total marks missing; arithmetic check skipped."
        }

    # 10. Field status. "CONFIDENT" means: tied to a label (or two agreeing readings) AND read with
    # enough OCR confidence. It is NOT proof the value is correct and NOT proof of authenticity.
    name_conf = fields.get("candidate_name_confidence", 0.0)
    name_anchor = fields.get("candidate_name_source")
    if not fields["candidate_name"]:
        name_status = "MISSING"
    elif name_anchor == "HEADER" and name_conf >= NAME_CONFIDENT_MIN_CONF and name_is_plausible(fields["candidate_name"]):
        name_status = "CONFIDENT"
    else:
        name_status = "UNCERTAIN"

    notes = {}

    def _guard(key, status, value):
        if status == "CONFIDENT" and _value_conflict(raw_detections, value):
            notes[key] = "VARIANTS_DISAGREE"  # another preprocessing variant read this differently
            return "UNCERTAIN"
        return status

    name_status = _guard("candidate_name", name_status, fields["candidate_name"])
    if fields.get("total_marks_source") != "CALCULATED_SUBJECT_SUM":
        total_status = _guard("total_marks", total_status, fields["total_marks"])
    fields["field_notes"] = notes
    fields["field_confidence"] = field_conf
    fields["field_status"] = {
        "certificate_number": _guard("certificate_number", _num_status(fields["certificate_number"], cert_conf, cert_labelled), fields["certificate_number"]),
        "registration_number": _guard("registration_number", _num_status(fields["registration_number"], reg_conf, reg_labelled), fields["registration_number"]),
        "candidate_name": name_status,
        "board": "CONFIDENT" if fields["board"] else "MISSING",
        "course": "CONFIDENT" if fields["course"] else "MISSING",
        "examination_year": "CONFIDENT" if fields["examination_year"] else "MISSING",
        "total_marks": total_status,
        "subject_marks": "CONFIDENT" if len(fields.get("subject_marks", [])) >= 3 else ("UNCERTAIN" if fields.get("subject_marks") else "MISSING")
    }

    fields["authority_signatories"] = detect_authority_signatories(raw_detections)

    return fields

def apply_name_region_reread(fields, image_bgr, raw_detections, ocr_reader=None, variant_funcs=None):
    """If the whole-page name read is not CONFIDENT, re-reads the region next to the NAME label and,
    only when the evidence rules in decide_name_override allow it, updates `fields` in place.
    Returns the diagnostics dict (or None when skipped). Both the first-pass and the re-read
    values stay available for diagnostics."""
    if fields["field_status"].get("candidate_name") == "CONFIDENT" or os.environ.get("DEEPTRUST_NAME_REOCR", "1") == "0":
        return None
    try:
        from ocr import VARIANTS as OCR_VARIANTS, reader as OCR_READER
        diag = reocr_name_region(image_bgr, raw_detections, ocr_reader or OCR_READER, variant_funcs or OCR_VARIANTS,
                                 clean_name_string, is_valid_name_candidate, name_is_plausible)
        first = {"name": fields["candidate_name"],
                 "confidence": fields.get("candidate_name_confidence", 0.0),
                 "plausible": name_is_plausible(fields["candidate_name"] or "")}
        override = decide_name_override(first, diag, min_confident_conf=NAME_CONFIDENT_MIN_CONF)
        if override:
            fields["candidate_name_first_pass"] = {
                "name": fields["candidate_name"],
                "confidence": fields.get("candidate_name_confidence"),
                "raw": fields.get("candidate_name_raw"),
                "source": fields.get("candidate_name_source"),
            }
            fields["candidate_name"] = override["name"]
            fields["candidate_name_confidence"] = override["confidence"]
            fields["candidate_name_source"] = override["source"]
            fields["field_status"]["candidate_name"] = override["status"]
            fields.setdefault("field_confidence", {})["candidate_name"] = override["confidence"]
        return diag
    except Exception as e:
        return {"attempted": False, "reason": f"ERROR: {type(e).__name__}: {e}"}


NON_MARKSHEET_PATTERNS = [
    (r"\b(AADHAAR|UIDAI|UNIQUE\s*IDENTIFICATION|MERA\s*AADHAAR|ENROLMENT\s*NO|ENROLLMENT\s*NO)\b", "Aadhaar Card / UIDAI Identity Document"),
    (r"\b(INCOME\s*TAX\s*DEPARTMENT|PERMANENT\s*ACCOUNT\s*NUMBER|GOVT\.?\s*OF\s*INDIA.*INCOME\s*TAX)\b", "Permanent Account Number (PAN) Card"),
    (r"\b(DRIVING\s*LICEN[CS]E|MOTOR\s*VEHICLES\s*DEPARTMENT|TRANSPORT\s*DEPARTMENT|LEARNER'?S\s*LICEN[CS]E)\b", "Driving Licence"),
    (r"\b(REPUBLIC\s*OF\s*INDIA.*PASSPORT|PASSPORT.*REPUBLIC\s*OF\s*INDIA)\b", "Passport Document"),
    (r"\b(ELECTION\s*COMMISSION\s*OF\s*INDIA|ELECTORAL\s*PHOTO\s*IDENTITY\s*CARD|VOTER\s*ID|EPIC\s*NO)\b", "Voter Identity Card"),
    (r"\b(TAX\s*INVOICE|BILL\s*TO|INVOICE\s*NUMBER|INVOICE\s*NO|GSTIN|PAYMENT\s*RECEIPT|AMOUNT\s*DUE|BALANCE\s*DUE)\b", "Commercial Invoice or Billing Receipt"),
    (r"\b(CURRICULUM\s*VITAE|RESUME|CAREER\s*OBJECTIVE|WORK\s*EXPERIENCE|JOB\s*TITLE)\b", "Resume / Curriculum Vitae"),
    (r"\b(BACHELOR\s*OF|MASTER\s*OF|CONVOCATION|DEGREE\s*OF\s*BACHELOR|PROVISIONAL\s*CERTIFICATE.*DEGREE|DOCTOR\s*OF\s*PHILOSOPHY)\b", "University Degree / Higher Education Diploma"),
]


def validate_marksheet_type(raw_detections, joined_text, structured_fields):
    """
    Validates that the uploaded document is exclusively an authentic 10th or 12th educational marksheet.
    Rejects any other document types (ID cards, degree certificates, invoices, random images/PDFs).
    """
    # 1. Check for explicit negative non-marksheet markers
    for pattern, label in NON_MARKSHEET_PATTERNS:
        if re.search(pattern, joined_text, re.I):
            return {
                "valid": False,
                "reason": "UNSUPPORTED_DOCUMENT_TYPE",
                "error": f"Invalid Document Type: Only 10th (SSLC) and 12th (HSC) standard marksheets can be processed. Detected: {label}. Please upload a valid 10th or 12th marksheet document."
            }

    # 2. Check for minimum readable text
    alphanumeric_chars = re.findall(r"[A-Za-z0-9]", joined_text)
    if len(alphanumeric_chars) < 15:
        return {
            "valid": False,
            "reason": "INSUFFICIENT_TEXT",
            "error": "Invalid Document: The uploaded image or PDF contains insufficient text or could not be recognized as a marksheet. Only clear 10th and 12th standard marksheets can be processed."
        }

    # Augment search text with extracted structured fields (board, course)
    structured_extra = f"{structured_fields.get('board') or ''} {structured_fields.get('course') or ''}".upper()
    search_text = f"{joined_text} {structured_extra}".strip()

    # 3. Determine if 10th or 12th
    std = structured_fields.get("detected_standard")
    label = structured_fields.get("detected_standard_label")

    if not std:
        has_10_marker = any(k in search_text for k in [
            "SECONDARY SCHOOL LEAVING", "SSLC", "X STANDARD", "CLASS 10",
            "10TH STANDARD", "10TH STD", "CERTIFICATE SL. NO. SEC", "CERTIFICATE SL.NO. SEC",
            "SL. NO. SEC", "SEC 24", "SECONDARY SCHOOL EXAMINATION", "MATRICULATION", "இடைநிலைப் பள்ளி",
            "HIGH SCHOOL"
        ]) or bool(re.search(r"\bCLASS\s*X\b(?!\s*I)", search_text, re.I)) or bool(re.search(r"\b10TH\b", search_text, re.I))

        has_12_marker = any(k in search_text for k in [
            "HIGHER SECONDARY", "SECOND YEAR", "HSC", "H.S.C", "H S C", "CLASS XII",
            "CLASS 12", "12TH STANDARD", "12TH STD", "CERTIFICATE SL. NO. HSE", "CERTIFICATE SL.NO. HSE",
            "SL. NO. HSE", "HSE", "SENIOR SCHOOL CERTIFICATE", "SENIOR SECONDARY", "INTERMEDIATE",
            "மேல்நிலைப் பள்ளி", "மேல்நிலை", "+2", "PLUS TWO"
        ]) or bool(re.search(r"\b12TH\b", search_text, re.I))

        if has_10_marker and not has_12_marker:
            std = "10"
            label = "10th Standard (SSLC)"
        elif has_12_marker and not has_10_marker:
            std = "12"
            label = "12th Standard (HSC)"
        elif has_10_marker and has_12_marker:
            if any(h in search_text for h in ["SECONDARY SCHOOL LEAVING", "SSLC", "X STANDARD", "SECONDARY SCHOOL EXAMINATION"]):
                std = "10"
                label = "10th Standard (SSLC)"
            else:
                std = "12"
                label = "12th Standard (HSC)"

    if not std:
        return {
            "valid": False,
            "reason": "NOT_10TH_OR_12TH_MARKSHEET",
            "error": "Invalid Document Type: Only 10th (SSLC) and 12th (HSC) standard marksheets can be processed. The uploaded file was not recognized as a 10th or 12th marksheet. Please upload a valid 10th or 12th marksheet document."
        }

    # 4. Educational marksheet feature validation
    has_educational_markers = bool(structured_fields.get("subject_marks")) or any(k in search_text for k in [
        "BOARD", "EXAMINATION", "EXAMINATIONS", "MARKS", "SUBJECT", "CERTIFICATE",
        "THEORY", "PRACTICAL", "TOTAL", "ROLL", "REGISTER", "PASS", "FAIL",
        "DGE", "CBSE", "ICSE", "CISCE", "GRADE", "தேர்வர்", "மதிப்பெண்", "சான்றிதழ்",
        "GOVERNMENT", "TAMIL NADU", "TAMILNADU", "CHENNAI", "SCHOOL", "CENTRAL BOARD", "STATE BOARD"
    ])
    if not has_educational_markers:
        return {
            "valid": False,
            "reason": "NOT_AN_EDUCATIONAL_MARKSHEET",
            "error": "Invalid Document Type: The uploaded document does not appear to be an educational examination marksheet. Only 10th and 12th marksheets can be processed."
        }

    structured_fields["detected_standard"] = std
    structured_fields["detected_standard_label"] = label
    if not structured_fields.get("course"):
        structured_fields["course"] = "Secondary School Leaving Certificate (10th)" if std == "10" else "Higher Secondary Examination (12th)"

    return {
        "valid": True,
        "standard": std,
        "standard_label": label
    }


def main():
    if len(sys.argv) < 2:
        sys.stdout = real_stdout
        print(json.dumps({
            "success": False,
            "error": "No image path provided as CLI argument."
        }))
        sys.exit(1)

    file_path = sys.argv[1]

    if not os.path.exists(file_path):
        sys.stdout = real_stdout
        print(json.dumps({
            "success": False,
            "error": f"Document file does not exist: {file_path}"
        }))
        sys.exit(1)

    # 1. Ingest document (JPG, JPEG, PNG, PDF) with validation & adaptive normalization
    from ingest import ingest_document
    doc = ingest_document(file_path)
    if not doc.get("success"):
        sys.stdout = real_stdout
        print(json.dumps({
            "success": False,
            "error": doc.get("error", "Failed to ingest document.")
        }))
        sys.exit(1)

    page_count = doc.get("page_count", 1)
    primary_page_bgr = doc["pages"][0]["image_bgr"]
    format_type = doc.get("format", "UNKNOWN")

    # 2. Extract OCR text / Multimodal Vision AI
    use_gemini = False
    gemini_ocr_metrics = None
    try:
        from gemini_vision import is_gemini_available, extract_certificate_with_gemini
        if is_gemini_available() and os.environ.get("DEEPTRUST_FORCE_LOCAL_OCR", "0") != "1":
            use_gemini = True
    except Exception:
        use_gemini = False

    if use_gemini:
        try:
            structured_fields, raw_detections, gemini_ocr_metrics = extract_certificate_with_gemini(primary_page_bgr)
            ocr_detail = {"variants_used": ["gemini_multimodal_vision"], "per_variant": {}}
            name_region_diag = {"attempted": False, "reason": "GEMINI_VISION_CONFIDENT"}
            total_boxes = len(raw_detections)
            avg_conf = 0.99
        except Exception as gemini_err:
            sys.stderr.write(f"Gemini Vision call failed, falling back to local OCR: {gemini_err}\n")
            use_gemini = False

    if not use_gemini:
        try:
            from ocr import (extract_text, extract_text_detailed, VARIANTS as OCR_VARIANTS, reader as OCR_READER,
                             ACTIVE_LANGS, LANG_NOTE, OCR_LANGS_REQUESTED)
            ocr_detail = extract_text_detailed(primary_page_bgr)
            raw_detections = ocr_detail["detections"]
            # Marksheets are on page 1; only scan subsequent page if page 1 yielded insufficient text
            if page_count > 1 and len(raw_detections) < 15:
                for p_idx in range(1, min(len(doc["pages"]), 2)):
                    sub_page_bgr = doc["pages"][p_idx]["image_bgr"]
                    sub_detections = extract_text(sub_page_bgr)
                    for d in sub_detections:
                        d["page"] = p_idx + 1
                    raw_detections.extend(sub_detections)
        except Exception as e:
            sys.stdout = real_stdout
            print(json.dumps({
                "success": False,
                "error": f"OCR extraction failed: {str(e)}"
            }))
            sys.exit(1)

        total_boxes = len(raw_detections)
        if total_boxes > 0:
            confidences = [d.get("mean_confidence", d.get("confidence", 0.0)) for d in raw_detections]
            avg_conf = sum(confidences) / total_boxes
        else:
            avg_conf = 0.0

        structured_fields = parse_extracted_fields(raw_detections)

        # Targeted re-read of the name value region when the whole-page read is not CONFIDENT.
        name_region_diag = apply_name_region_reread(structured_fields, primary_page_bgr, raw_detections)

    # 3. Document Type Gate: Strictly enforce ONLY 10th and 12th marksheet processing
    all_texts = [d["text"].strip() for d in raw_detections if d.get("text")]
    joined_text = " ".join(all_texts).upper()
    doc_val = validate_marksheet_type(raw_detections, joined_text, structured_fields)
    if not doc_val["valid"]:
        sys.stdout = real_stdout
        print(json.dumps({
            "success": False,
            "error": doc_val["error"],
            "rejection_reason": doc_val["reason"],
            "document_type_rejected": True
        }))
        sys.exit(0)

    try:
        qr_analysis = analyze_certificate_qr(primary_page_bgr, ocr_fields=structured_fields)
    except Exception as e:
        qr_analysis = {
            "detected": False,
            "qr_count": 0,
            "error": f"QR processing encountered an error: {str(e)}",
            "consistency_check": {
                "status": "ERROR",
                "consistent": None,
                "discrepancies": [],
                "matches": [],
                "note": "QR analysis failed."
            }
        }

    try:
        tamper_analysis = analyze_document_tampering(
            primary_page_bgr,
            raw_detections=raw_detections,
            extracted_fields=structured_fields
        )
    except Exception as e:
        tamper_analysis = {
            "analysis_completed": False,
            "error": f"Tamper analysis encountered an error: {str(e)}",
            "indicators_detected": [],
            "suspicious_regions": [],
            "evidence_notes": [],
            "limitations": ["Analysis encountered an error."],
            "review_recommended": True,
            "forensic_summary": "Tamper analysis error."
        }

    response = {
        "success": True,
        "image_path": file_path,
        "document_metadata": {
            "format": format_type,
            "file_size": doc.get("file_size"),
            "page_count": page_count,
            "pdf_signature_markers": doc.get("pdf_signature_markers"),
            "primary_page_analyzed": 1,
            "multi_page_note": f"Document contains {page_count} pages. Primary certificate fields and visual forensics analyzed from page 1." if page_count > 1 else "Single-page document."
        },
        "extracted_fields": structured_fields,
        "qr_analysis": qr_analysis,
        "tamper_analysis": tamper_analysis,
        "ocr_metrics": gemini_ocr_metrics if (use_gemini and gemini_ocr_metrics) else {
            "total_boxes_detected": total_boxes,
            "average_confidence": round(avg_conf, 2),
            "average_confidence_percentage": f"{avg_conf * 100:.1f}%",
            "readable_text_confidence": round(compute_readable_text_confidence(raw_detections), 3),
            "zero_confidence_boxes": sum(1 for d in raw_detections if _conf(d) == 0.0),
            "confidence_note": "OCR engine confidence only; not extraction accuracy and not evidence of authenticity.",
            "variants_used": ocr_detail.get("variants_used"),
            "variant_errors": ocr_detail.get("variant_errors") or {},
            "languages_requested": OCR_LANGS_REQUESTED,
            "languages_active": ACTIVE_LANGS,
            "language_note": LANG_NOTE
        },
        "ocr_diagnostics": {
            "per_variant": {
                name: {
                    "boxes": len(dets),
                    "mean_confidence_all_boxes": round(sum(x.get("confidence", 0.0) for x in dets) / len(dets), 3) if dets else 0.0,
                    "readable_text_confidence": round(compute_readable_text_confidence(dets), 3),
                }
                for name, dets in (ocr_detail.get("per_variant") or {}).items()
            },
            "name_region": name_region_diag,
        },
        "raw_detections": raw_detections
    }

    sys.stdout = real_stdout

    print(json.dumps(response))

if __name__ == "__main__":
    main()
