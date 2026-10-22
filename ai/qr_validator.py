"""
ai/qr_validator.py - DeepTrust Nexus QR Code Detection & Consistency Engine
----------------------------------------------------------------------------
Detects, decodes, and classifies QR codes from educational certificates.
Extracts readable credential fields and compares them against visible OCR text.

IMPORTANT SECURITY POLICIES:
1. Never automatically open or fetch URLs found in QR codes.
2. QR detection alone or an official-looking URL is NEVER proof of authenticity.
3. Cryptographic and proprietary payloads without open verification keys are
   reported as unverified/inconclusive, never guessed or fabricated.
4. Report discrepancies as evidence of inconsistency, not automatic proof of forgery.
"""

import os
import re
import json
import urllib.parse
import cv2
import numpy as np

try:
    import zxingcpp
    HAS_ZXING = True
except ImportError:
    HAS_ZXING = False

# Trusted educational board & government domain suffixes in India
TRUSTED_GOV_DOMAINS = [
    "gov.in",
    "nic.in",
    "cbse.gov.in",
    "cbse.nic.in",
    "dge.tn.gov.in",
    "dge1.tn.gov.in",
    "dgeverification.tn.gov.in",
    "tn.gov.in",
    "tndge.org",
    "certverify.tndge.org",
    "digilocker.gov.in",
    "apisetu.gov.in"
]


def is_trusted_domain(hostname):
    """
    Checks if a hostname strictly ends with one of the trusted government domains.
    Prevents homograph or subdomain spoofing (e.g., 'fake-cbse.gov.in.attacker.com').
    """
    if not hostname:
        return False
    host = hostname.lower().strip(".")
    for trusted in TRUSTED_GOV_DOMAINS:
        if host == trusted or host.endswith("." + trusted):
            return True
    return False

def lev_distance(a, b):
    """Computes basic Levenshtein edit distance between strings a and b."""
    m, n = len(a), len(b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            dp[i][j] = min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost)
    return dp[m][n]

def normalized_similarity(a, b):
    """Returns normalized similarity [0.0, 1.0] between strings a and b."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    max_len = max(len(a), len(b))
    dist = lev_distance(a, b)
    return max(0.0, 1.0 - (dist / max_len))


def detect_and_decode_qr(image_input):
    """
    Detects and decodes QR codes from an image path or pre-loaded numpy image.
    Applies multi-stage image processing:
      - Direct RGB, Grayscale, CLAHE contrast enhancement
      - Multi-scale searches (1.5x, 2.0x, 3.0x for low-res scans)
      - Targeted quadrant / corner ROI searches
      - Adaptive & Otsu binary thresholding
    Distinguishes these outcomes:
      - NOT_DETECTED: No QR visual patterns or finder markers found
      - DETECTED_UNREADABLE: QR visual pattern / finder corners detected, but payload bitstream cannot be decoded
      - DECODED: Payload string successfully decoded
    """
    if isinstance(image_input, str):
        if not os.path.exists(image_input):
            return {
                "detected": False,
                "detection_state": "NOT_DETECTED",
                "raw_payload": None,
                "qr_count": 0,
                "error": f"Image file not found: {image_input}"
            }
        image = cv2.imread(image_input)
        if image is None:
            return {
                "detected": False,
                "detection_state": "NOT_DETECTED",
                "raw_payload": None,
                "qr_count": 0,
                "error": f"Failed to read image at: {image_input}"
            }
    elif isinstance(image_input, np.ndarray):
        image = image_input
    else:
        return {
            "detected": False,
            "detection_state": "NOT_DETECTED",
            "raw_payload": None,
            "qr_count": 0,
            "error": "Unsupported image input type."
        }

    h_orig, w_orig = image.shape[:2]

    # Quick pass: Use zxingcpp (fast, robust against distortion and low resolution)
    if HAS_ZXING:
        for z_pass, z_img in [("zxing_direct", image), ("zxing_gray", cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image)]:
            try:
                barcodes = zxingcpp.read_barcodes(z_img)
                for b in barcodes:
                    if b.text and b.text.strip():
                        pts = None
                        if hasattr(b, "position"):
                            pts = [[[p.x, p.y] for p in [b.position.top_left, b.position.top_right, b.position.bottom_right, b.position.bottom_left]]]
                        return {
                            "detected": True,
                            "detection_state": "DECODED",
                            "raw_payload": b.text.strip(),
                            "qr_count": 1,
                            "decoding_pass": z_pass,
                            "points": pts
                        }
            except Exception:
                pass

    detector = cv2.QRCodeDetector()

    # Convert to grayscale
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    candidate_pts = None

    # Helper function to test a candidate image variant
    def try_decode_variant(img_var, pass_label):
        nonlocal candidate_pts
        # 1. Try detectAndDecode
        val, pts, _ = detector.detectAndDecode(img_var)

        if val and val.strip():
            return {
                "detected": True,
                "detection_state": "DECODED",
                "raw_payload": val.strip(),
                "qr_count": 1,
                "decoding_pass": pass_label,
                "points": pts.tolist() if pts is not None else None
            }
        # 2. If decoding failed, check if detect found corners
        ret, d_pts = detector.detect(img_var)
        if ret and d_pts is not None and len(d_pts) > 0:
            if candidate_pts is None:
                candidate_pts = d_pts
            # Try decoding cropped patch if corners form a reasonable polygon
            try:
                pts_int = d_pts[0].astype(int)
                x_min = max(0, int(np.min(pts_int[:, 0])))
                x_max = min(img_var.shape[1], int(np.max(pts_int[:, 0])))
                y_min = max(0, int(np.min(pts_int[:, 1])))
                y_max = min(img_var.shape[0], int(np.max(pts_int[:, 1])))
                cw = x_max - x_min
                ch = y_max - y_min
                if cw > 20 and ch > 20 and cw < img_var.shape[1] * 0.9:
                    margin = 15
                    y1 = max(0, y_min - margin)
                    y2 = min(img_var.shape[0], y_max + margin)
                    x1 = max(0, x_min - margin)
                    x2 = min(img_var.shape[1], x_max + margin)
                    crop = img_var[y1:y2, x1:x2]
                    for scale in [2.0, 3.0]:
                        up_crop = cv2.resize(crop, (int(crop.shape[1] * scale), int(crop.shape[0] * scale)), interpolation=cv2.INTER_CUBIC)
                        v_crop, p_crop, _ = detector.detectAndDecode(up_crop)
                        if v_crop and v_crop.strip():
                            return {
                                "detected": True,
                                "detection_state": "DECODED",
                                "raw_payload": v_crop.strip(),
                                "qr_count": 1,
                                "decoding_pass": f"{pass_label}_crop_upscaled",
                                "points": d_pts.tolist()
                            }
            except Exception:
                pass
        return None

    # Pass 1: Direct RGB
    res = try_decode_variant(image, "original_rgb")
    if res:
        return res

    # Pass 2: Grayscale
    res = try_decode_variant(gray, "grayscale")
    if res:
        return res

    # Pass 3: CLAHE contrast enhancement
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    res = try_decode_variant(enhanced, "clahe_enhanced")
    if res:
        return res

    # Pass 4: Adaptive scaling (crucial for small or low-res images like 423px scans)
    if max(h_orig, w_orig) < 1600:
        scale_target = min(2000.0 / max(h_orig, w_orig), 3.0)
        scaled = cv2.resize(enhanced, (int(round(w_orig * scale_target)), int(round(h_orig * scale_target))), interpolation=cv2.INTER_CUBIC)
        res = try_decode_variant(scaled, "upscaled_clahe")
        if res:
            return res

    # Pass 5: Otsu & Adaptive binary thresholding
    _, thresh_otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    res = try_decode_variant(thresh_otsu, "otsu_binary")
    if res:
        return res

    thresh_adapt = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 3)
    res = try_decode_variant(thresh_adapt, "adaptive_binary")
    if res:
        return res

    # Pass 6: Targeted Quadrant / Corner Search (top-right, top-left, bottom-right, bottom-left)
    rois = [
        ("top_right", 0, int(h_orig * 0.45), int(w_orig * 0.50), w_orig),
        ("top_left", 0, int(h_orig * 0.45), 0, int(w_orig * 0.50)),
        ("bottom_right", int(h_orig * 0.55), h_orig, int(w_orig * 0.50), w_orig),
        ("bottom_left", int(h_orig * 0.55), h_orig, 0, int(w_orig * 0.50))
    ]
    for roi_name, y1, y2, x1, x2 in rois:
        sub = enhanced[y1:y2, x1:x2]
        res = try_decode_variant(sub, f"roi_{roi_name}")
        if res:
            return res
        sub_2x = cv2.resize(sub, (sub.shape[1] * 2, sub.shape[0] * 2), interpolation=cv2.INTER_CUBIC)
        res = try_decode_variant(sub_2x, f"roi_{roi_name}_2x")
        if res:
            return res

    # If decoding failed across all passes, but candidate QR corners were detected:
    if candidate_pts is not None:
        return {
            "detected": True,
            "detection_state": "DETECTED_UNREADABLE",
            "raw_payload": None,
            "qr_count": 1,
            "decoding_pass": "detected_unreadable",
            "points": candidate_pts.tolist() if hasattr(candidate_pts, "tolist") else None,
            "note": "A QR code is visually present on the document, but the payload could not be decoded due to scan resolution, blur, or compression. A higher-resolution scan is recommended."
        }

    # If no QR patterns detected anywhere:
    return {
        "detected": False,
        "detection_state": "NOT_DETECTED",
        "raw_payload": None,
        "qr_count": 0,
        "decoding_pass": "none",
        "note": "No QR code was visually detected in the document scan."
    }


def classify_payload(raw_payload):
    """
    Classifies the decoded QR payload without performing any external network requests.
    Identifies URLs, DigiLocker URIs, structured text, JSON, cryptographic tokens, or binary blobs.
    """
    if not raw_payload or not raw_payload.strip():
        return {
            "payload_type": "EMPTY",
            "description": "Empty payload string",
            "is_url": False,
            "domain": None,
            "is_official_domain": False,
            "security_flags": ["EMPTY_PAYLOAD"]
        }

    cleaned = raw_payload.strip()

    # 1. URL Check
    if cleaned.lower().startswith("http://") or cleaned.lower().startswith("https://"):
        try:
            parsed = urllib.parse.urlparse(cleaned)
            hostname = parsed.hostname or ""
            trusted = is_trusted_domain(hostname)

            security_flags = []
            if not trusted:
                security_flags.append("UNVERIFIED_THIRD_PARTY_DOMAIN")
            if parsed.scheme == "http":
                security_flags.append("INSECURE_HTTP_PROTOCOL")

            return {
                "payload_type": "OFFICIAL_GOV_URL" if trusted else "EXTERNAL_URL",
                "description": (
                    "URL under a government/education-board domain suffix (page not fetched; issuer and content NOT validated; NOT proof of authenticity)"
                    if trusted
                    else "Third-party or external web URL (NOT proof of authenticity)"
                ),
                "is_url": True,
                "url": cleaned,
                "scheme": parsed.scheme,
                "domain": hostname,
                "path": parsed.path,
                "query": parsed.query,
                "is_official_domain": trusted,
                "security_flags": security_flags
            }
        except Exception as e:
            return {
                "payload_type": "MALFORMED_URL",
                "description": f"Malformed URL string: {str(e)}",
                "is_url": True,
                "domain": None,
                "is_official_domain": False,
                "security_flags": ["MALFORMED_URL"]
            }

    # 2. DigiLocker Document URI Format
    # E.g. CBSE-MSTN-12345678 or in.gov.cbse:certificate:... or digilocker:...
    if (
        re.match(r"^(?:CBSE|TNDGE|CISCE|KSEEB|MSBSHSE)-[A-Z0-9]+-[A-Z0-9]+", cleaned, re.I)
        or re.match(r"^in\.gov\.[a-z0-9\.\-]+", cleaned, re.I)
        or cleaned.lower().startswith("digilocker:")
    ):
        return {
            "payload_type": "DIGILOCKER_URI",
            "description": "Standardized DigiLocker Document Repository URI",
            "is_url": False,
            "domain": "digilocker.gov.in",
            # A text pattern anyone can print on a forged page says nothing about the issuer.
            "is_official_domain": False,
            "security_flags": ["UNVALIDATED_TEXT_PATTERN"]
        }

    # 3. JSON Object Credential
    if (cleaned.startswith("{") and cleaned.endswith("}")) or (cleaned.startswith("[") and cleaned.endswith("]")):
        try:
            parsed_json = json.loads(cleaned)
            return {
                "payload_type": "JSON_CREDENTIAL",
                "description": "Structured JSON certificate data object",
                "is_url": False,
                "domain": None,
                "is_official_domain": False,
                "has_valid_json": True,
                "security_flags": []
            }
        except Exception:
            pass

    # 4. Signed JWT Token Pattern (Three Base64URL dot-separated segments)
    jwt_parts = cleaned.split(".")
    if len(jwt_parts) == 3:
        # Check base64url characters
        if all(re.match(r"^[A-Za-z0-9_\-]+$", part) for part in jwt_parts if part):
            return {
                "payload_type": "SIGNED_TOKEN",
                "description": "Compact cryptographic token (e.g., JWT / JWS)",
                "is_url": False,
                "domain": None,
                "is_official_domain": False,
                "security_flags": ["REQUIRES_ISSUER_PUBLIC_KEY"]
            }

    # 5. Delimited Structured Text (e.g., Name|RegNo|Marks or Key=Value)
    has_delimiters = any(d in cleaned for d in ["|", ";", "\t", "\n"])
    has_keywords = any(k in cleaned.upper() for k in ["REG", "ROLL", "NAME", "MARKS", "TOTAL", "DOB", "CERT", "PASS", "FAIL"])
    if has_delimiters and has_keywords:
        return {
            "payload_type": "STRUCTURED_DELIMITED",
            "description": "Delimited text containing candidate credential attributes",
            "is_url": False,
            "domain": None,
            "is_official_domain": False,
            "security_flags": []
        }

    # 6. High-Entropy Hexadecimal / Encrypted Binary Blob
    if re.match(r"^[0-9a-fA-F]{32,}$", cleaned) or (len(cleaned) > 60 and re.match(r"^[A-Za-z0-9+/=]{60,}$", cleaned)):
        return {
            "payload_type": "ENCRYPTED_OR_OPAQUE_BLOB",
            "description": "Encrypted or proprietary opaque data string (cannot be decrypted offline without issuer keys)",
            "is_url": False,
            "domain": None,
            "is_official_domain": False,
            "security_flags": ["ENCRYPTED_UNVERIFIABLE_OFFLINE"]
        }

    # 7. Unstructured Plain Text
    return {
        "payload_type": "PLAIN_TEXT",
        "description": "Unstructured text payload",
        "is_url": False,
        "domain": None,
        "is_official_domain": False,
        "security_flags": []
    }


def parse_qr_fields(raw_payload, classification):
    """
    Extracts identifiable academic metadata fields from readable QR payloads
    (Structured delimited, JSON, or URL query parameters).
    """
    fields = {
        "candidate_name": None,
        "registration_number": None,
        "certificate_number": None,
        "total_marks": None,
        "board": None,
        "course": None,
        "examination_year": None,
        "is_readable": False,
        "raw_attributes": {}
    }

    if not raw_payload:
        return fields

    cleaned = raw_payload.strip()
    ptype = classification.get("payload_type", "")

    # A. JSON Credential
    if ptype == "JSON_CREDENTIAL":
        try:
            data = json.loads(cleaned)
            fields["is_readable"] = True
            fields["raw_attributes"] = data

            # Extract fields with common variations
            for k, v in data.items():
                k_clean = k.lower().replace("_", "").replace(" ", "")
                v_str = str(v).strip()

                if "name" in k_clean and "board" not in k_clean and "school" not in k_clean:
                    fields["candidate_name"] = v_str
                elif "reg" in k_clean or "roll" in k_clean:
                    fields["registration_number"] = v_str
                elif "cert" in k_clean or "serial" in k_clean:
                    fields["certificate_number"] = v_str
                elif "total" in k_clean or "marks" in k_clean:
                    fields["total_marks"] = v_str
                elif "board" in k_clean:
                    fields["board"] = v_str
                elif "class" in k_clean or "course" in k_clean:
                    fields["course"] = v_str
                elif "year" in k_clean or "session" in k_clean:
                    fields["examination_year"] = v_str
            return fields
        except Exception:
            pass

    # B. URL Query Parameters & Path Roll Number (e.g. Tamil Nadu DGE certverify portal)
    if classification.get("is_url", False):
        try:
            parsed = urllib.parse.urlparse(cleaned)
            params = urllib.parse.parse_qs(parsed.query)
            if params:
                fields["is_readable"] = True
                flat_params = {k: v[0] for k, v in params.items() if v}
                fields["raw_attributes"] = flat_params

                for k, v in flat_params.items():
                    k_clean = k.lower()
                    if k_clean in ["name", "cname", "candidate", "student"]:
                        fields["candidate_name"] = v
                    elif k_clean in ["regno", "reg_no", "rollno", "roll_no", "reg", "roll"]:
                        fields["registration_number"] = v
                    elif k_clean in ["certno", "cert_no", "certificate", "serial"]:
                        fields["certificate_number"] = v
                    elif k_clean in ["total", "marks", "totmarks", "tot"]:
                        fields["total_marks"] = v
                    elif k_clean in ["year", "session", "examyear"]:
                        fields["examination_year"] = v
                    elif k_clean in ["board"]:
                        fields["board"] = v

            # Check URL path for official board roll numbers (e.g., https://certverify.tndge.org/ceti-verify/<hash1>/<roll_number>/<hash2>)
            path_segments = [seg for seg in parsed.path.split("/") if seg]
            for seg in path_segments:
                if re.match(r"^\d{6,8}$", seg):
                    fields["is_readable"] = True
                    fields["roll_number"] = seg
                    if not fields.get("registration_number"):
                        fields["registration_number"] = seg
                    fields["raw_attributes"]["roll_number"] = seg
                    fields["raw_attributes"]["verification_endpoint"] = cleaned
                    if any(t_dom in parsed.netloc for t_dom in ["tndge", "tn.gov"]):
                        fields["board"] = "State Board of School Examinations, Tamil Nadu"
                    break

            return fields
        except Exception:
            pass


    # C. Structured Delimited Text (key-value pairs or tokenized string)
    if ptype == "STRUCTURED_DELIMITED" or any(delim in cleaned for delim in ["|", ";", "\n"]):
        # First try delimiter split
        delimiter = "|" if "|" in cleaned else (";" if ";" in cleaned else "\n")
        segments = [s.strip() for s in cleaned.split(delimiter) if s.strip()]

        for seg in segments:
            # Check for Key:Value or Key=Value
            kv_match = re.match(r"^([^:=]+)[:=]\s*(.+)$", seg)
            if kv_match:
                k, v = kv_match.group(1).strip().upper(), kv_match.group(2).strip()
                fields["is_readable"] = True
                fields["raw_attributes"][k] = v

                if any(x in k for x in ["NAME", "CANDIDATE", "STUDENT"]) and "BOARD" not in k and "SCHOOL" not in k:
                    fields["candidate_name"] = v
                elif any(x in k for x in ["REG", "ROLL"]):
                    fields["registration_number"] = v
                elif any(x in k for x in ["CERT", "SERIAL"]):
                    fields["certificate_number"] = v
                elif any(x in k for x in ["TOTAL", "MARKS"]):
                    fields["total_marks"] = v
                elif "BOARD" in k:
                    fields["board"] = v
                elif any(x in k for x in ["CLASS", "COURSE"]):
                    fields["course"] = v
                elif any(x in k for x in ["YEAR", "SESSION"]):
                    fields["examination_year"] = v

        # If positional (e.g. "REG: 12345678" or just raw tokens)
        if not fields["registration_number"]:
            reg_m = re.search(r"\b(\d{7,10})\b", cleaned)
            if reg_m:
                fields["registration_number"] = reg_m.group(1)
                fields["is_readable"] = True

        return fields

    # D. DigiLocker Document URI
    if ptype == "DIGILOCKER_URI":
        fields["is_readable"] = True
        parts = cleaned.split("-")
        if len(parts) >= 3:
            fields["board"] = parts[0]
            fields["course"] = parts[1]
            fields["certificate_number"] = parts[2]
            fields["raw_attributes"] = {"issuer": parts[0], "doc_type": parts[1], "doc_id": parts[2]}
        return fields

    return fields


def compare_qr_with_ocr(qr_fields, ocr_fields):
    """
    Compares readable fields extracted from QR code against visible text extracted via OCR.
    Discrepancies indicate possible document alteration or a QR code copied from another certificate.

    NOTE: Discrepancies are reported as evidence of inconsistency, not automatic proof of forgery.
    """
    if not qr_fields or not qr_fields.get("is_readable"):
        return {
            "status": "INCONCLUSIVE",
            "consistent": None,
            "discrepancies": [],
            "matches": [],
            "note": "QR code did not contain readable plain-text metadata to compare against OCR visible text.",
            "field_comparisons": []
        }

    field_comparisons = []
    discrepancies = []
    matches = []

    # 1. Candidate Name Comparison
    qr_name = qr_fields.get("candidate_name")
    ocr_name = ocr_fields.get("candidate_name") if ocr_fields else None

    if qr_name and ocr_name:
        q_clean = re.sub(r"[^A-Za-z\s]", " ", qr_name.upper()).strip()
        q_clean = re.sub(r"\s+", " ", q_clean)
        o_clean = re.sub(r"[^A-Za-z\s]", " ", ocr_name.upper()).strip()
        o_clean = re.sub(r"\s+", " ", o_clean)

        sim = normalized_similarity(q_clean, o_clean)
        # Check token overlap
        q_tokens = set(q_clean.split())
        o_tokens = set(o_clean.split())
        token_overlap = bool(q_tokens.intersection(o_tokens))

        if sim >= 0.75 or (token_overlap and sim >= 0.60):
            matches.append({
                "field": "Candidate Name",
                "qr_value": qr_name,
                "ocr_value": ocr_name,
                "similarity": round(sim, 2),
                "note": "Candidate name consistent with minor character variation" if sim < 1.0 else "Exact candidate name match"
            })
            field_comparisons.append({
                "field": "Candidate Name",
                "matched": True,
                "qr_value": qr_name,
                "ocr_value": ocr_name,
                "note": f"{round(sim * 100)}% name alignment"
            })
        else:
            disc_note = f"Candidate name discrepancy: QR payload has '{qr_name}', but visible certificate OCR extracted '{ocr_name}'"
            discrepancies.append(disc_note)
            field_comparisons.append({
                "field": "Candidate Name",
                "matched": False,
                "qr_value": qr_name,
                "ocr_value": ocr_name,
                "note": disc_note
            })

    # 2. Registration Number / Roll Number Comparison
    qr_reg = qr_fields.get("registration_number") or qr_fields.get("roll_number")
    ocr_reg = ocr_fields.get("registration_number") if ocr_fields else None
    ocr_roll = ocr_fields.get("roll_number") if ocr_fields else None

    if qr_reg and (ocr_reg or ocr_roll):
        q_r = re.sub(r"\D", "", str(qr_reg))
        o_r = re.sub(r"\D", "", str(ocr_reg)) if ocr_reg else ""
        o_roll = re.sub(r"\D", "", str(ocr_roll)) if ocr_roll else ""

        matched = False
        matched_field = "Registration Number"
        matched_val = ""

        if o_roll and (q_r == o_roll or q_r in o_roll or o_roll in q_r):
            matched = True
            matched_field = "Roll Number"
            matched_val = ocr_roll
        elif o_r and (q_r == o_r or (len(q_r) >= 6 and len(o_r) >= 6 and (q_r.endswith(o_r) or o_r.endswith(q_r))) or q_r in o_r):
            matched = True
            matched_field = "Registration Number"
            matched_val = ocr_reg

        if matched:
            matches.append({
                "field": matched_field,
                "qr_value": qr_reg,
                "ocr_value": matched_val,
                "note": f"{matched_field} verified consistent between QR and visible document"
            })
            field_comparisons.append({
                "field": matched_field,
                "matched": True,
                "qr_value": qr_reg,
                "ocr_value": matched_val,
                "note": f"{matched_field} verified consistent between QR and visible document"
            })
        else:
            disc_note = f"Roll / Registration number discrepancy: QR encodes '{qr_reg}', visible document displays '{ocr_roll or ocr_reg}'"
            discrepancies.append(disc_note)
            field_comparisons.append({
                "field": "Registration Number",
                "matched": False,
                "qr_value": qr_reg,
                "ocr_value": ocr_roll or ocr_reg,
                "note": disc_note
            })


    # 3. Certificate Number Comparison
    qr_cert = qr_fields.get("certificate_number")
    ocr_cert = ocr_fields.get("certificate_number") if ocr_fields else None

    if qr_cert and ocr_cert:
        q_c = str(qr_cert).strip().upper()
        o_c = str(ocr_cert).strip().upper()

        if q_c == o_c:
            matches.append({
                "field": "Certificate Number",
                "qr_value": qr_cert,
                "ocr_value": ocr_cert,
                "note": "Certificate serial numbers match exactly"
            })
            field_comparisons.append({
                "field": "Certificate Number",
                "matched": True,
                "qr_value": qr_cert,
                "ocr_value": ocr_cert,
                "note": "Exact match"
            })
        else:
            disc_note = f"Certificate number discrepancy: QR has '{qr_cert}', visible certificate has '{ocr_cert}'"
            discrepancies.append(disc_note)
            field_comparisons.append({
                "field": "Certificate Number",
                "matched": False,
                "qr_value": qr_cert,
                "ocr_value": ocr_cert,
                "note": disc_note
            })

    # 4. Total Marks Comparison
    qr_marks = qr_fields.get("total_marks")
    ocr_marks = ocr_fields.get("total_marks") if ocr_fields else None

    if qr_marks and ocr_marks:
        q_m = re.sub(r"\D", "", str(qr_marks))
        o_m = re.sub(r"\D", "", str(ocr_marks))

        if q_m and o_m:
            if q_m == o_m:
                matches.append({
                    "field": "Total Marks",
                    "qr_value": qr_marks,
                    "ocr_value": ocr_marks,
                    "note": f"Total marks match ({qr_marks})"
                })
                field_comparisons.append({
                    "field": "Total Marks",
                    "matched": True,
                    "qr_value": qr_marks,
                    "ocr_value": ocr_marks,
                    "note": "Total marks match"
                })
            else:
                disc_note = f"Marks discrepancy: QR records total of {qr_marks}, while visible text records {ocr_marks}"
                discrepancies.append(disc_note)
                field_comparisons.append({
                    "field": "Total Marks",
                    "matched": False,
                    "qr_value": qr_marks,
                    "ocr_value": ocr_marks,
                    "note": disc_note
                })

    # Evaluation
    if discrepancies:
        return {
            "status": "DISCREPANCY_DETECTED",
            "consistent": False,
            "discrepancies": discrepancies,
            "matches": matches,
            "field_comparisons": field_comparisons,
            "note": f"Discrepancy detected between QR payload and visible document text ({len(discrepancies)} mismatch(es)).",
            "disclaimer": "Discrepancies indicate conflicting evidence (such as a copied QR code or altered visible text). Not standalone proof of forgery."
        }
    elif matches:
        return {
            "status": "CONSISTENT",
            "consistent": True,
            "discrepancies": [],
            "matches": matches,
            "field_comparisons": field_comparisons,
            "note": f"Readable QR data is consistent with visible document fields across {len(matches)} checked item(s).",
            "disclaimer": "Consistency indicates agreement between QR and visible text, but does not substitute for cryptographic issuer validation."
        }
    else:
        return {
            "status": "INCONCLUSIVE",
            "consistent": None,
            "discrepancies": [],
            "matches": [],
            "field_comparisons": [],
            "note": "No common fields could be compared between QR payload and OCR output.",
            "disclaimer": "QR code payload does not share common structured fields with visible OCR text."
        }


def analyze_certificate_qr(image_path, ocr_fields=None):
    """
    Main orchestration function for QR code analysis.
    Executes detection, payload classification, field extraction, and OCR consistency comparison.
    Distinguishes 4 outcomes:
      - NOT_DETECTED
      - DETECTED_UNREADABLE
      - DECODED
      - DECODED_RECOGNIZED
    """
    # 1. Detection
    det_result = detect_and_decode_qr(image_path)
    detection_state = det_result.get("detection_state", "NOT_DETECTED" if not det_result.get("detected") else "DECODED")

    if not det_result.get("detected") or detection_state == "NOT_DETECTED":
        return {
            "detected": False,
            "detection_state": "NOT_DETECTED",
            "qr_count": 0,
            "payload_classification": {
                "payload_type": "NONE",
                "description": "No QR code detected"
            },
            "qr_fields": {
                "is_readable": False
            },
            "consistency_check": {
                "status": "NO_QR_DETECTED",
                "consistent": None,
                "discrepancies": [],
                "matches": [],
                "note": "Document scan does not contain a detectable QR code."
            },
            "summary_note": "No QR code was detected on the certificate.",
            "disclaimer": "Physical certificates without QR codes are common in legacy examinations and are not inherently forged."
        }

    # Case: Visually detected, but payload unreadable due to blur / resolution
    if detection_state == "DETECTED_UNREADABLE":
        return {
            "detected": True,
            "detection_state": "DETECTED_UNREADABLE",
            "qr_count": 1,
            "raw_payload": None,
            "raw_payload_preview": None,
            "raw_payload_length": 0,
            "decoding_pass": det_result.get("decoding_pass"),
            "points": det_result.get("points"),
            "payload_classification": {
                "payload_type": "UNREADABLE_IMAGE",
                "description": "QR code is visually present on certificate, but data is unreadable due to low scan resolution, camera blur, or compression artifacts."
            },
            "qr_fields": {
                "is_readable": False
            },
            "consistency_check": {
                "status": "QR_UNREADABLE",
                "consistent": None,
                "discrepancies": [],
                "matches": [],
                "note": "QR code was visually detected, but payload could not be decoded. Higher-resolution scan recommended."
            },
            "summary_note": "QR code visually detected on document, but payload bits could not be decoded at current resolution.",
            "disclaimer": "Unreadable QR codes often occur with low-resolution mobile camera uploads and are NOT proof of forgery."
        }

    raw_payload = det_result.get("raw_payload") or ""

    # 2. Classification
    classification = classify_payload(raw_payload)

    # 3. Field Extraction
    qr_fields = parse_qr_fields(raw_payload, classification)

    # 4. Consistency check with OCR fields (if provided)
    consistency = compare_qr_with_ocr(qr_fields, ocr_fields)

    # 5. Determine recognized vs decoded state
    if classification.get("payload_type") not in ["EMPTY", "UNKNOWN", "NONE"]:
        final_state = "DECODED_RECOGNIZED"
    else:
        final_state = "DECODED"

    # 6. Build summary note
    summary_note = f"QR code detected ({classification['payload_type']}). "
    if consistency["status"] == "CONSISTENT":
        summary_note += f"Data matches visible certificate details across {len(consistency['matches'])} field(s)."
    elif consistency["status"] == "DISCREPANCY_DETECTED":
        summary_note += f"Warning: {len(consistency['discrepancies'])} data discrepancy(ies) between QR and visible text."
    elif classification.get("is_official_domain"):
        summary_note += (f"URL domain ({classification.get('domain')}) is under a government/board suffix. "
                         "The page was not fetched and the link is not validated, so this is not proof of authenticity.")
    else:
        summary_note += classification["description"]

    return {
        "detected": True,
        "detection_state": final_state,
        "qr_count": 1,
        "raw_payload": raw_payload,
        "raw_payload_preview": raw_payload[:120] + ("..." if len(raw_payload) > 120 else ""),
        "raw_payload_length": len(raw_payload),
        "decoding_pass": det_result.get("decoding_pass"),
        "points": det_result.get("points"),
        "payload_classification": classification,
        "qr_fields": qr_fields,
        "consistency_check": consistency,
        "summary_note": summary_note,
        "disclaimer": "QR code presence or plausible payload is NOT standalone proof of certificate authenticity."
    }
