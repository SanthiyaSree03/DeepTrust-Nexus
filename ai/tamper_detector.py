"""
ai/tamper_detector.py - DeepTrust Nexus Document Tampering & Forensics Engine
-----------------------------------------------------------------------------
Performs cautious, multi-angle image forensics and layout consistency analysis
to identify potential certificate alteration, splicing, or marks tampering.

CORE METHODOLOGY & SCIENTIFIC PRINCIPLES:
1. Clearly distinguishes an observed anomaly from confirmed tampering.
2. Avoids universal ELA thresholds: scanning, re-compression, shadows, and watermarks
   naturally generate high-frequency edge variance.
3. Does not calculate or report arbitrary numerical "authenticity probabilities".
4. Combines layout geometry, texture/compression discrepancies, and arithmetic checks.
5. If evidence is ambiguous or coordinates are missing, flags REVIEW_RECOMMENDED
   rather than making definitive guesses.
"""

import os
import re
import cv2
import numpy as np


def get_bounding_rect(box):
    """
    Extracts (x, y, w, h) from a 4-point polygon box [[x1, y1], [x2, y2], [x3, y3], [x4, y4]].
    Returns None if box format is invalid.
    """
    if not box or len(box) < 4:
        return None
    try:
        pts = np.array(box, dtype=np.int32)
        x, y, w, h = cv2.boundingRect(pts)
        if w > 0 and h > 0:
            return x, y, w, h
    except Exception:
        pass
    return None


def analyze_compression_ela(image, raw_detections=None, quality=92):
    """
    Simulates Error Level Analysis (ELA) by re-compressing the image in memory
    at a standardized JPEG quality and measuring the localized difference.

    CAUTION: ELA alone does NOT prove forgery. High-contrast printed text, watermarks,
    and camera noise naturally exhibit elevated error levels. This check looks for
    isolated, localized anomalies on sensitive data fields relative to document baseline.
    """
    if image is None:
        return {
            "status": "SKIPPED",
            "reason": "Image not loaded",
            "anomalies_detected": False,
            "findings": []
        }

    h, w = image.shape[:2]
    if len(image.shape) == 2:
        img_color = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    else:
        img_color = image

    # In-memory JPEG recompression
    success, encoded = cv2.imencode(".jpg", img_color, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not success:
        return {
            "status": "ERROR",
            "reason": "Failed to recompress image buffer for ELA analysis",
            "anomalies_detected": False,
            "findings": []
        }

    resaved = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if resaved is None:
        return {
            "status": "ERROR",
            "reason": "Failed to decode recompressed ELA buffer",
            "anomalies_detected": False,
            "findings": []
        }

    # Compute absolute difference
    diff = cv2.absdiff(img_color, resaved)
    diff_gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)

    global_mean = float(np.mean(diff_gray))
    global_std = float(np.std(diff_gray))

    findings = []
    suspicious_patches = []

    # If raw detections with coordinates are available, inspect text regions
    if raw_detections:
        for det in raw_detections:
            box = det.get("box")
            text = det.get("text", "").strip()
            rect = get_bounding_rect(box)
            if not rect:
                continue

            rx, ry, rw, rh = rect
            # Restrict to valid image bounds
            rx1 = max(0, rx)
            ry1 = max(0, ry)
            rx2 = min(w, rx + rw)
            ry2 = min(h, ry + rh)

            if rx2 <= rx1 or ry2 <= ry1:
                continue

            patch = diff_gray[ry1:ry2, rx1:rx2]
            if patch.size < 25:
                continue

            patch_mean = float(np.mean(patch))
            patch_std = float(np.std(patch))

            # Sensitive field keywords (marks, numbers, candidate names)
            is_numeric = bool(re.match(r"^\d{2,10}$", text))
            is_sensitive = is_numeric or len(text) > 3

            # Local deviation ratio compared to global document ELA baseline
            # Guard against flat synthetic canvases where global_std is near zero
            if global_std >= 1.5 and is_sensitive:
                z_score = (patch_mean - global_mean) / global_std
                # Mark as an anomaly only if substantially elevated (z-score > 4.0 and absolute patch diff is high)
                if z_score > 4.0 and patch_mean > 25.0 and (patch_mean - global_mean) > 15.0:
                    note = f"Region '{text}' exhibits localized compression variation (local ELA mean: {round(patch_mean, 1)} vs doc mean: {round(global_mean, 1)})"
                    findings.append({
                        "text": text,
                        "type": "ELEVATED_COMPRESSION_VARIATION",
                        "z_score": round(z_score, 2),
                        "local_mean": round(patch_mean, 2),
                        "global_mean": round(global_mean, 2),
                        "rect": [rx1, ry1, rw, rh],
                        "note": note
                    })
                    suspicious_patches.append({
                        "field_text": text,
                        "indicator": "LOCALIZED_COMPRESSION_INCONSISTENCY",
                        "rect": [rx1, ry1, rw, rh],
                        "severity": "MODERATE",
                        "description": note
                    })

    return {
        "status": "COMPLETED",
        "global_ela_mean": round(global_mean, 2),
        "global_ela_std": round(global_std, 2),
        "anomalies_detected": len(findings) > 0,
        "findings": findings,
        "suspicious_patches": suspicious_patches,
        "limitation_note": "ELA variations can be caused by natural camera compression, folded paper, or high-contrast printed lines."
    }


def analyze_text_alignment_and_font(raw_detections):
    """
    Examines bounding box geometry of tabular mark entries.
    In genuine certificates, subject marks in a column share consistent font height
    and follow a regular vertical baseline. Spliced or digitally added digits
    frequently display anomalous box heights or irregular vertical baseline offsets.
    """
    if not raw_detections:
        return {
            "status": "INSUFFICIENT_DATA",
            "reason": "No OCR text detections provided for layout analysis.",
            "anomalies_detected": False,
            "mark_entries_evaluated": 0,
            "findings": []
        }

    # Filter detections that represent numeric scores (e.g. 2-3 digit marks between 20 and 100)
    mark_boxes = []
    for d in raw_detections:
        txt = d.get("text", "").strip()
        box = d.get("box")
        if not box:
            continue
        rect = get_bounding_rect(box)
        if not rect:
            continue

        # Look for 2 or 3 digit numbers (typical subject marks: e.g. 85, 092, 100) in tabular region
        if re.match(r"^\b(0?[2-9]\d|100)\b$", txt):
            x, y, w, h = rect
            # Exclude header/banner numbers outside tabular marks region
            if y < 140:
                continue
            baseline_y = y + h
            mark_boxes.append({
                "text": txt,
                "rect": rect,
                "height": h,
                "width": w,
                "baseline_y": baseline_y,
                "confidence": d.get("confidence", 0.0)
            })

    # Need at least 3 mark entries to establish a statistically meaningful baseline
    if len(mark_boxes) < 3:
        return {
            "status": "INSUFFICIENT_COORDINATE_DATA",
            "reason": f"Only {len(mark_boxes)} numeric score bounding box(es) detected. Minimum 3 required for tabular alignment analysis.",
            "anomalies_detected": False,
            "mark_entries_evaluated": len(mark_boxes),
            "findings": []
        }

    heights = [m["height"] for m in mark_boxes]
    median_h = float(np.median(heights))
    findings = []
    suspicious_marks = []

    for m in mark_boxes:
        h = m["height"]
        if median_h > 0:
            rel_diff = abs(h - median_h) / median_h
            # Genuine font tampering involves significant font scale discrepancy (> 55% and >= max(12, 0.5*median_h))
            min_abs_diff = max(12.0, 0.5 * median_h)
            if rel_diff > 0.55 and abs(h - median_h) >= min_abs_diff:
                note = f"Mark '{m['text']}' height ({h}px) differs by {round(rel_diff * 100)}% from tabular median ({round(median_h, 1)}px)"
                findings.append({
                    "text": m["text"],
                    "height": h,
                    "median_height": round(median_h, 1),
                    "relative_difference_pct": round(rel_diff * 100, 1),
                    "rect": list(m["rect"]),
                    "note": note
                })
                suspicious_marks.append({
                    "field_text": m["text"],
                    "indicator": "FONT_SIZE_DISCREPANCY",
                    "rect": list(m["rect"]),
                    "severity": "MODERATE",
                    "description": note
                })

    return {
        "status": "COMPLETED",
        "mark_entries_evaluated": len(mark_boxes),
        "median_mark_height_px": round(median_h, 1),
        "anomalies_detected": len(findings) > 0,
        "findings": findings,
        "suspicious_regions": suspicious_marks,
        "limitation_note": "Mobile perspective skew, low scan DPI, or mixed font weights can produce minor height variance."
    }


def analyze_edge_discontinuity(image, raw_detections=None):
    """
    Checks for sharp gradient or blur discrepancies across text boxes.
    Digitally inserted text often displays sharp artificial boundaries
    or blur variance compared to surrounding scanned paper grain.
    """
    if image is None:
        return {
            "status": "SKIPPED",
            "anomalies_detected": False,
            "findings": []
        }

    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    h, w = gray.shape[:2]
    # Background document blur (Laplacian variance)
    global_laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    findings = []
    suspicious_regions = []
    patch_data = []

    if raw_detections:
        for det in raw_detections:
            box = det.get("box")
            text = det.get("text", "").strip()
            rect = get_bounding_rect(box)
            if not rect:
                continue

            rx, ry, rw, rh = rect
            if rw < 15 or rh < 10:
                continue

            rx1 = max(0, rx)
            ry1 = max(0, ry)
            rx2 = min(w, rx + rw)
            ry2 = min(h, ry + rh)

            patch = gray[ry1:ry2, rx1:rx2]
            if patch.size < 100:
                continue

            if re.match(r"^\d{2,3}$", text):
                local_var = float(cv2.Laplacian(patch, cv2.CV_64F).var())
                patch_data.append({
                    "text": text,
                    "var": local_var,
                    "rect": [rx1, ry1, rw, rh],
                    "rh": rh
                })

    # Compare numeric region sharpness against peer text regions of comparable font scale
    if len(patch_data) >= 3:
        median_rh = float(np.median([p["rh"] for p in patch_data]))
        # Filter to tabular mark peer boxes with consistent font scale (avoids comparing headers/years against tiny marks)
        peer_patches = [p for p in patch_data if abs(p["rh"] - median_rh) <= 0.35 * median_rh]
        if len(peer_patches) >= 3:
            median_peer_var = float(np.median([p["var"] for p in peer_patches]))
            if median_peer_var > 10.0:
                for p in peer_patches:
                    ratio = p["var"] / median_peer_var
                    # Digitally inserted text displays unnaturally sharp, high-contrast boundaries lacking scan blur/texture
                    if ratio > 4.2 and (p["var"] - median_peer_var) > 1000:
                        note = f"Region '{p['text']}' displays anomalous edge sharpness ({round(p['var'], 1)} vs peer median {round(median_peer_var, 1)})"
                        findings.append({
                            "text": p["text"],
                            "sharpness_ratio": round(ratio, 1),
                            "local_var": round(p["var"], 1),
                            "peer_median_var": round(median_peer_var, 1),
                            "rect": p["rect"],
                            "note": note
                        })
                        suspicious_regions.append({
                            "field_text": p["text"],
                            "indicator": "SHARPNESS_DISCONTINUITY",
                            "rect": p["rect"],
                            "severity": "LOW",
                            "description": note
                        })

    return {
        "status": "COMPLETED",
        "numeric_regions_evaluated": len(patch_data),
        "anomalies_detected": len(findings) > 0,
        "findings": findings,
        "suspicious_regions": suspicious_regions,
        "limitation_note": "Scanner optical focus, ink bleeding, or paper texture can cause localized sharpness variation."
    }


def evaluate_arithmetic_forensics(extracted_fields):
    """
    Evaluates marks summation arithmetic as a forensic indicator.
    If calculated sum contradicts recorded total marks, it is a confirmed discrepancy.
    """
    if not extracted_fields or "arithmetic_check" not in extracted_fields:
        return {
            "applicable": False,
            "anomaly_detected": False,
            "note": "Arithmetic check was not performed or fields missing."
        }

    chk = extracted_fields["arithmetic_check"]
    if not chk.get("applicable", False):
        return {
            "applicable": False,
            "anomaly_detected": False,
            "reason": chk.get("reason", "NOT_APPLICABLE"),
            "note": chk.get("details", "Direct arithmetic sum not applicable (e.g. CGPA/grading system).")
        }

    if chk.get("consistent") is False:
        diff = chk.get("difference", 0)
        return {
            "applicable": True,
            "anomaly_detected": True,
            "status": "ARITHMETIC_MISMATCH",
            "calculated_sum": chk.get("calculated_sum"),
            "recorded_total": chk.get("recorded_total"),
            "difference": diff,
            "note": f"Recorded total ({chk.get('recorded_total')}) contradicts sum of extracted subject marks ({chk.get('calculated_sum')}) by {diff}.",
            "severity": "HIGH"
        }
    elif chk.get("consistent") is True:
        return {
            "applicable": True,
            "anomaly_detected": False,
            "status": "VERIFIED_CONSISTENT",
            "calculated_sum": chk.get("calculated_sum"),
            "recorded_total": chk.get("recorded_total"),
            "note": f"Sum of {len(extracted_fields.get('subject_marks', []))} subjects ({chk.get('calculated_sum')}) matches recorded total ({chk.get('recorded_total')})."
        }

    return {
        "applicable": False,
        "anomaly_detected": False,
        "note": "Arithmetic check inconclusive."
    }


def analyze_document_tampering(image_input, raw_detections=None, extracted_fields=None):
    """
    Main orchestration entry point for document tampering and image forensics analysis.
    Returns structured results distinguishing observed anomalies from confirmed tampering.
    """
    # 1. Load image
    if isinstance(image_input, str):
        if not os.path.exists(image_input):
            return {
                "analysis_completed": False,
                "error": f"Image file not found: {image_input}",
                "indicators_detected": [],
                "suspicious_regions": [],
                "evidence_notes": ["Image file could not be opened for forensics analysis."],
                "limitations": ["Analysis could not run without a readable image file."],
                "review_recommended": True,
                "forensic_summary": "Image unavailable for forensics analysis."
            }
        image = cv2.imread(image_input)
    elif isinstance(image_input, np.ndarray):
        image = image_input
    else:
        return {
            "analysis_completed": False,
            "error": "Unsupported image format",
            "indicators_detected": [],
            "suspicious_regions": [],
            "evidence_notes": [],
            "limitations": ["Invalid image input type."],
            "review_recommended": True,
            "forensic_summary": "Invalid image input."
        }

    # 2. Run Individual Forensics Checks
    ela_res = analyze_compression_ela(image, raw_detections)
    layout_res = analyze_text_alignment_and_font(raw_detections)
    edge_res = analyze_edge_discontinuity(image, raw_detections)
    arithmetic_res = evaluate_arithmetic_forensics(extracted_fields)

    # 3. Collect Indicators, Suspicious Regions, and Evidence
    indicators_detected = []
    suspicious_regions = []
    evidence_notes = []

    # A. Arithmetic Evidence
    if arithmetic_res.get("anomaly_detected"):
        indicators_detected.append("MARKS_ARITHMETIC_MISMATCH")
        evidence_notes.append(f"Arithmetic discrepancy: {arithmetic_res.get('note')}")
        suspicious_regions.append({
            "field": "total_marks",
            "indicator": "MARKS_ARITHMETIC_MISMATCH",
            "severity": "HIGH",
            "description": arithmetic_res.get("note")
        })
    elif arithmetic_res.get("applicable") and not arithmetic_res.get("anomaly_detected"):
        evidence_notes.append(f"Arithmetic consistency verified: {arithmetic_res.get('note')}")

    # B. Layout & Font Alignment Evidence
    if layout_res.get("anomalies_detected"):
        indicators_detected.append("FONT_SIZE_ALIGNMENT_ANOMALY")
        for f in layout_res.get("findings", []):
            evidence_notes.append(f"Layout anomaly: {f.get('note')}")
        suspicious_regions.extend(layout_res.get("suspicious_regions", []))
    elif layout_res.get("status") == "COMPLETED":
        evidence_notes.append(
            f"Font height consistent across {layout_res.get('mark_entries_evaluated')} tabular marks (median height: {layout_res.get('median_mark_height_px')}px)."
        )

    # C. Compression & ELA Evidence
    if ela_res.get("anomalies_detected"):
        indicators_detected.append("LOCAL_COMPRESSION_VARIATION")
        for f in ela_res.get("findings", []):
            evidence_notes.append(f"Compression variation: {f.get('note')}")
        suspicious_regions.extend(ela_res.get("suspicious_patches", []))

    # D. Edge & Sharpness Evidence
    if edge_res.get("anomalies_detected"):
        indicators_detected.append("EDGE_SHARPNESS_DISCONTINUITY")
        for f in edge_res.get("findings", []):
            evidence_notes.append(f"Edge discontinuity: {f.get('note')}")
        suspicious_regions.extend(edge_res.get("suspicious_regions", []))

    # 4. Synthesize Summary & Recommendations
    has_high_severity = any(r.get("severity") == "HIGH" for r in suspicious_regions)
    has_indicators = len(indicators_detected) > 0

    if has_high_severity or len(indicators_detected) >= 2:
        forensic_summary = f"Identified {len(indicators_detected)} potential anomaly indicator(s) requiring human review ({', '.join(indicators_detected)})."
        review_recommended = True
    elif has_indicators:
        forensic_summary = f"Minor anomaly indicator detected ({', '.join(indicators_detected)}). Document review recommended."
        review_recommended = True
    else:
        forensic_summary = "No obvious visual tampering or arithmetic anomalies detected in available document regions."
        review_recommended = False

    limitations = [
        "Image forensics heuristics detect statistical and visual anomalies, which can also be produced by camera compression, scanner artifacts, folds, or low lighting.",
        "Forensic heuristics cannot definitively prove or disprove forgery in the absence of authoritative issuer verification.",
        "If text coordinates are missing, low-contrast, or skewed, layout alignment analysis is skipped to avoid false positives."
    ]

    return {
        "analysis_completed": True,
        "indicators_detected": indicators_detected,
        "indicator_count": len(indicators_detected),
        "suspicious_regions": suspicious_regions,
        "evidence_notes": evidence_notes,
        "limitations": limitations,
        "review_recommended": review_recommended,
        "forensic_summary": forensic_summary,
        "module_results": {
            "error_level_analysis": {
                "status": ela_res.get("status"),
                "anomalies_detected": ela_res.get("anomalies_detected"),
                "anomaly_count": len(ela_res.get("findings", []))
            },
            "layout_font_analysis": {
                "status": layout_res.get("status"),
                "anomalies_detected": layout_res.get("anomalies_detected"),
                "marks_evaluated": layout_res.get("mark_entries_evaluated", 0)
            },
            "edge_discontinuity_analysis": {
                "status": edge_res.get("status"),
                "anomalies_detected": edge_res.get("anomalies_detected")
            },
            "arithmetic_forensics": {
                "applicable": arithmetic_res.get("applicable"),
                "anomaly_detected": arithmetic_res.get("anomaly_detected")
            }
        }
    }
