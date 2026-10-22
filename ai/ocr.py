"""
OCR layer for DeepTrust Nexus.

Compared with the original single-pass implementation this module:
  * runs several preprocessing variants (configurable) and MERGES them by box overlap, keeping every
    alternative reading and an agreement count so that downstream code can tell a stable reading
    from one that changes with the preprocessing;
  * adds a background-normalisation variant that suppresses decorative guilloche / watermark
    patterns before recognition;
  * loads OCR languages safely: a non-English model is only used if it is already installed
    (or DEEPTRUST_OCR_ALLOW_DOWNLOAD=1 is set); otherwise it falls back to English and reports why.

Environment variables
  DEEPTRUST_OCR_LANGS           comma list, default "en" (e.g. "ta,en" for Tamil + English)
  DEEPTRUST_OCR_ALLOW_DOWNLOAD  "1" lets EasyOCR download a missing NON-English model (default "0")
  DEEPTRUST_OCR_VARIANTS        comma list of variants, default "upscaled_clahe,bg_normalized"
                                (set to "upscaled_clahe" to reproduce the previous single-pass behaviour)
"""
import os
import re

import cv2
import easyocr
import numpy as np

DEFAULT_VARIANTS = ["upscaled_clahe", "bg_normalized"]


def _env_list(name, default):
    raw = os.environ.get(name, "")
    items = [x.strip() for x in raw.split(",") if x.strip()]
    return items or list(default)


# --------------------------------------------------------------------------------------
# Reader construction (no silent model downloads for non-English languages)
# --------------------------------------------------------------------------------------
def build_reader(langs, allow_download=False, factory=None):
    """Returns (reader, active_languages, note). Falls back to English if the requested
    language model is unavailable. `factory` is injectable for tests."""
    factory = factory or easyocr.Reader
    langs = list(langs) or ["en"]
    if langs == ["en"]:
        return factory(["en"]), ["en"], None
    try:
        return factory(langs, download_enabled=allow_download), langs, None
    except Exception as exc:  # missing model, unsupported combination, offline, ...
        note = (
            f"Requested OCR languages {langs} could not be loaded ({type(exc).__name__}: {str(exc)[:120]}). "
            "Using English only. Tamil text (including the Tamil half of bilingual labels) is NOT being read. "
            "To enable it, run once with DEEPTRUST_OCR_ALLOW_DOWNLOAD=1 (downloads an additional EasyOCR "
            "recognition model) and keep DEEPTRUST_OCR_LANGS=ta,en."
        )
        return factory(["en"]), ["en"], note


OCR_LANGS_REQUESTED = _env_list("DEEPTRUST_OCR_LANGS", ["en"])
reader, ACTIVE_LANGS, LANG_NOTE = build_reader(
    OCR_LANGS_REQUESTED, allow_download=os.environ.get("DEEPTRUST_OCR_ALLOW_DOWNLOAD", "0") == "1"
)


# --------------------------------------------------------------------------------------
# Preprocessing variants. Each returns (image, scale) where scale maps variant->original coords.
# --------------------------------------------------------------------------------------
def _gray(image):
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image


def _adaptive_factor(image, target_long=1800):
    h, w = image.shape[:2]
    long_side = max(h, w)
    if long_side < 1200:
        return max(2.0, round(float(target_long) / float(long_side), 2))
    return 2.0


def _upscale(gray, factor=2):
    h, w = gray.shape[:2]
    return cv2.resize(gray, (int(round(w * factor)), int(round(h * factor))), interpolation=cv2.INTER_CUBIC)


def variant_original(image):
    return _gray(image), 1.0


def variant_upscaled_2x(image):
    factor = _adaptive_factor(image, 1800)
    return _upscale(_gray(image), factor=factor), factor


def variant_upscaled_clahe(image):
    """Adaptive upscaling (bicubic to target resolution) + CLAHE contrast enhancement."""
    factor = _adaptive_factor(image, 1800)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(_upscale(_gray(image), factor=factor)), factor


def variant_bg_normalized(image):
    """Divides by an estimate of the local background. Upscales first so small text strokes
    are preserved rather than wiped out by morphological dilation, then applies CLAHE."""
    factor = _adaptive_factor(image, 1800)
    gray = _upscale(_gray(image), factor=factor)
    k = max(21, (min(gray.shape[:2]) // 40) | 1)
    bg = cv2.medianBlur(cv2.dilate(gray, np.ones((7, 7), np.uint8)), k if k % 2 else k + 1)
    flat = cv2.divide(gray, bg, scale=255)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(flat), factor


def variant_adaptive_threshold(image):
    factor = _adaptive_factor(image, 1800)
    up = _upscale(_gray(image), factor=factor)
    up = cv2.GaussianBlur(up, (3, 3), 0)
    return cv2.adaptiveThreshold(up, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15), factor



VARIANTS = {
    "original": variant_original,
    "upscaled_2x": variant_upscaled_2x,
    "upscaled_clahe": variant_upscaled_clahe,
    "bg_normalized": variant_bg_normalized,
    "adaptive_threshold": variant_adaptive_threshold,
}


# --------------------------------------------------------------------------------------
# Merging
# --------------------------------------------------------------------------------------
def _rect(box):
    if not box:
        return None
    try:
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        return (min(xs), min(ys), max(xs), max(ys))
    except Exception:
        return None


def _iou(a, b):
    ix0, iy0 = max(a[0], b[0]), max(a[1], b[1])
    ix1, iy1 = min(a[2], b[2]), min(a[3], b[3])
    iw, ih = max(0, ix1 - ix0), max(0, iy1 - iy0)
    inter = iw * ih
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


def _norm_text(t):
    return re.sub(r"[^A-Z0-9]", "", (t or "").upper())


def sort_reading_order(dets):
    """Top-to-bottom, then left-to-right within a row. Boxes without geometry keep their order at the end."""
    with_box = [d for d in dets if _rect(d.get("box"))]
    without = [d for d in dets if not _rect(d.get("box"))]
    if not with_box:
        return list(dets)
    heights = [(_rect(d["box"])[3] - _rect(d["box"])[1]) for d in with_box]
    tol = 0.5 * (sum(heights) / len(heights)) if heights else 10
    cy = lambda d: (_rect(d["box"])[1] + _rect(d["box"])[3]) / 2.0
    ordered, row, row_cy = [], [], None
    for d in sorted(with_box, key=cy):
        if row_cy is None or abs(cy(d) - row_cy) <= tol:
            row.append(d)
            row_cy = cy(d) if row_cy is None else (row_cy * (len(row) - 1) + cy(d)) / len(row)
        else:
            ordered.extend(sorted(row, key=lambda x: _rect(x["box"])[0]))
            row, row_cy = [d], cy(d)
    ordered.extend(sorted(row, key=lambda x: _rect(x["box"])[0]))
    return ordered + without


def merge_variant_detections(per_variant, iou_threshold=0.5):
    """Merges detections from several variants (already in ORIGINAL image coordinates).

    For each cluster of overlapping boxes the highest-confidence reading wins, but the result also
    carries:
      agreement        number of variants that produced the same normalised text as the winner
      variants_seen    number of variants that detected something in this place
      mean_confidence  mean over all members (not biased upwards by picking the max)
      alternatives     differing readings from other variants (diagnostics / disagreement checks)
    """
    clusters = []
    for vname, dets in per_variant.items():
        for det in dets:
            r = _rect(det.get("box"))
            target = None
            if r:
                for c in clusters:
                    if c["rect"] and _iou(r, c["rect"]) >= iou_threshold:
                        target = c
                        break
            if target is None:
                target = {"rect": r, "members": []}
                clusters.append(target)
            target["members"].append((vname, det))

    merged = []
    for c in clusters:
        members = c["members"]
        best_v, best = max(members, key=lambda m: float(m[1].get("confidence", 0.0)))
        norm = _norm_text(best.get("text"))
        agree = sum(1 for _, m in members if norm and _norm_text(m.get("text")) == norm)
        out = dict(best)
        out["variant"] = best_v
        out["agreement"] = agree
        out["variants_seen"] = len({v for v, _ in members})
        out["mean_confidence"] = round(sum(float(m.get("confidence", 0.0)) for _, m in members) / len(members), 3)
        alts = [
            {"variant": v, "text": m.get("text"), "confidence": round(float(m.get("confidence", 0.0)), 2)}
            for v, m in members
            if m is not best and _norm_text(m.get("text")) != norm
        ]
        if alts:
            out["alternatives"] = alts
        merged.append(out)
    return sort_reading_order(merged)


# --------------------------------------------------------------------------------------
# Running OCR
# --------------------------------------------------------------------------------------
def _format(results, scale):
    out = []
    for det in results:
        try:
            box = [[int(round(pt[0] / scale)), int(round(pt[1] / scale))] for pt in det[0]]
        except Exception:
            box = None
        out.append({"text": det[1], "confidence": round(float(det[2]), 2), "box": box})
    return out


def _load_image(image_input):
    if isinstance(image_input, np.ndarray):
        return image_input
    if isinstance(image_input, str):
        if not os.path.exists(image_input):
            raise FileNotFoundError(f"Image file not found: {image_input}")
        if os.path.splitext(image_input)[1].lower() == ".pdf":
            from ingest import ingest_document
            doc = ingest_document(image_input)
            if not doc.get("success"):
                raise ValueError(doc.get("error", f"Failed to ingest PDF: {image_input}"))
            if not doc.get("pages"):
                raise ValueError("PDF document contains no renderable pages.")
            return doc["pages"][0]["image_bgr"]
        image = cv2.imread(image_input)
        if image is None:
            raise ValueError(f"Could not read or decode image at: {image_input}")
        return image
    raise ValueError(f"Unsupported image input type: {type(image_input)}. Expected filepath or numpy array.")


def read_variant(image, variant_name, ocr_reader=None, **readtext_kwargs):
    ocr_reader = ocr_reader or reader
    img, scale = VARIANTS[variant_name](image)
    return _format(ocr_reader.readtext(img, **readtext_kwargs), scale)


def extract_text_detailed(image_input, variants=None, ocr_reader=None):
    """Runs the configured variants and returns
    {"detections": merged, "per_variant": {name: [...]}, "variants_used": [...], "variant_errors": {...}}"""
    image = _load_image(image_input)
    names = [v for v in (variants or _env_list("DEEPTRUST_OCR_VARIANTS", DEFAULT_VARIANTS)) if v in VARIANTS]
    if not names:
        names = ["upscaled_clahe"]
    per_variant, errors = {}, {}
    for name in names:
        try:
            per_variant[name] = read_variant(image, name, ocr_reader)
        except Exception as exc:  # one failing variant must not lose the others
            errors[name] = f"{type(exc).__name__}: {exc}"
    if not per_variant:
        raise RuntimeError(f"All OCR variants failed: {errors}")
    if len(per_variant) > 1:
        detections = merge_variant_detections(per_variant)
    else:  # single variant: keep EasyOCR's own order, exactly as the original pipeline did
        detections = list(next(iter(per_variant.values())))
    return {"detections": detections, "per_variant": per_variant, "variants_used": list(per_variant), "variant_errors": errors}


def extract_text(image_input):
    """Backward-compatible entry point: returns the merged detection list
    (each item has text, confidence, box and, when several variants ran, agreement metadata)."""
    return extract_text_detailed(image_input)["detections"]
