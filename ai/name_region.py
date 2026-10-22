"""
Targeted re-reading of the candidate-name VALUE region.

Why: on bilingual / decorated marksheets a whole-page pass often reads the name value badly (it is
printed in a different font on a patterned background, next to a bilingual label). Once the NAME
label has been located, only the region to its right and the band below it can contain the value,
so that area is cropped and re-read with several preprocessing variants and a letters-only
allowlist. The result is trusted only when independent variants agree; otherwise it stays UNCERTAIN.

Everything here is pure / injectable (no EasyOCR import) so it can be unit-tested.
"""
import difflib
import re

NAME_LABEL_PATTERNS = [
    r"NAME\s+OF\s+THE\s+CANDIDATE",
    r"NAME\s+OF\s+CANDIDATE",
    r"CANDIDATE(?:'S)?\s+NAME",
    r"STUDENT(?:'S)?\s+NAME",
    r"NAME\s*:",
    r"பெயர்",  # Tamil "name"
    r"தேர்வரின்",
    r"TFECIDIL",  # OCR garble of bilingual Tamil/English label on Tamil Nadu marksheets
    r"neoF\s*TFeCIDIL",
    r"Tarst.*Cnndi",
    r"ineof.*Cnndi",
    r"Tarsttlttineof7HeCnndiL",
    r".*OF\s*[7T]HE\s*C[A-Z0-9]+",
    r".*C[A-Z0-9]{2,6}ndi[A-Za-z]*",
    r"\bCANDI[A-Z]*\b",
]
FUZZY_NAME_LABELS = ["NAME OF THE CANDIDATE", "NAME OF CANDIDATE", "CANDIDATES NAME", "STUDENTS NAME"]
NAME_ALLOWLIST = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz. "
REGION_VARIANTS = ["bg_normalized", "upscaled_clahe", "adaptive_threshold"]


def rect_of(box):
    if not box:
        return None
    try:
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        return (min(xs), min(ys), max(xs), max(ys))
    except Exception:
        return None


def _letters_upper(text):
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z ]", " ", (text or "").upper())).strip()


def fuzzy_label_score(text, labels):
    """Best similarity (0..1) between `text` and any label, comparing word windows of similar length.
    Tolerates OCR damage such as 'NAMF OF THF CANDIDATF' but not unrelated text."""
    words = _letters_upper(text).split()
    best = 0.0
    for label in labels:
        n = len(label.split())
        for size in {max(1, n - 1), n, n + 1}:
            for i in range(0, max(1, len(words) - size + 1)):
                window = " ".join(words[i:i + size])
                if window:
                    best = max(best, difflib.SequenceMatcher(None, window, label).ratio())
    return best


def find_name_label(dets, fuzzy_min=0.8, page_h=None, page_w=None):
    """Returns (index, kind) with kind 'EXACT' or 'FUZZY', or (None, None)."""
    for i, d in enumerate(dets):
        txt = (d.get("text") or "").upper()
        if any(re.search(p, txt, re.I) for p in NAME_LABEL_PATTERNS):
            return i, "EXACT"
    best_i, best_s = None, 0.0
    for i, d in enumerate(dets):
        s = fuzzy_label_score(d.get("text"), FUZZY_NAME_LABELS)
        if s > best_s:
            best_i, best_s = i, s
    if best_i is not None and best_s >= fuzzy_min:
        return best_i, "FUZZY"

    # Geometric fallback: In Tamil Nadu marksheets, candidate name header sits on the left cell (y: 18-35%)
    for i, d in enumerate(dets):
        r = rect_of(d.get("box"))
        if not r:
            continue
        txt = (d.get("text") or "").upper()
        # Look for partial corruptions of bilingual candidate label
        if any(k in txt for k in ["TARST", "INEOF", "CNNDI", "CANDI", "NAME", "பெயர்", "தேர்வர்"]):
            return i, "FUZZY"

    return None, None


def name_search_regions(label_rect, page_w, page_h, dets=None, label_idx=None):
    """Regions that can hold the name value: right of the label on the same row, and the band below."""
    x0, y0, x1, y1 = label_rect
    h = max(12, y1 - y0)
    cy_lbl = (y0 + y1) / 2.0

    cell_x0 = x0
    if dets and label_idx is not None:
        for k, d in enumerate(dets):
            if k == label_idx:
                continue
            r = rect_of(d.get("box"))
            if not r:
                continue
            cy = (r[1] + r[3]) / 2.0
            if abs(cy - cy_lbl) <= 0.8 * h and r[2] <= x0 + h:
                cell_x0 = min(cell_x0, r[0])

    # In tabular marksheets, the cell can extend to the left margin / preceding content
    cell_x0 = max(0, min(cell_x0 - int(1.5 * h), int(page_w * 0.05), x0 - int(15 * h)))
    # Ensure cell_x1 covers the candidate name column width (typically 40-52% of page width)
    cell_x1 = max(min(page_w, x1 + int(2.5 * h)), int(page_w * 0.48))

    regions = [
        ("below_label", (cell_x0, y1, cell_x1, min(page_h, y1 + int(4.5 * h)))),
        ("candidate_cell", (int(page_w * 0.02), int(y1), int(page_w * 0.50), min(page_h, y1 + int(4.5 * h)))),
        ("right_of_label", (int(x1 + 0.3 * h), int(max(0, y0 - 0.4 * h)), page_w, int(min(page_h, y1 + 0.6 * h)))),
    ]
    out = []
    for name, (a, b, c, d) in regions:
        a, b, c, d = int(max(0, a)), int(max(0, b)), int(min(page_w, c)), int(min(page_h, d))
        if c - a >= 24 and d - b >= 10:
            out.append({"name": name, "rect": (a, b, c, d)})
    return out


def group_rows(results):
    """EasyOCR results [(box, text, conf)] -> list of {text, confidence} per visual row, left to right."""
    items = []
    for r in results:
        rect = rect_of(r[0])
        if rect and (r[1] or "").strip():
            items.append((rect, r[1].strip(), float(r[2])))
    if not items:
        return []
    avg_h = sum(i[0][3] - i[0][1] for i in items) / len(items)
    tol = 0.6 * avg_h
    items.sort(key=lambda i: (i[0][1] + i[0][3]) / 2)
    rows, cur, cur_cy = [], [], None
    for it in items:
        cy = (it[0][1] + it[0][3]) / 2
        if cur_cy is None or abs(cy - cur_cy) <= tol:
            cur.append(it)
            cur_cy = cy if cur_cy is None else sum((c[0][1] + c[0][3]) / 2 for c in cur) / len(cur)
        else:
            rows.append(cur)
            cur, cur_cy = [it], cy
    rows.append(cur)
    out = []
    for row in rows:
        row.sort(key=lambda i: i[0][0])
        chars = [max(1, len(re.findall(r"[A-Za-z]", i[1]))) for i in row]
        conf = sum(i[2] * w for i, w in zip(row, chars)) / sum(chars)
        out.append({"text": " ".join(i[1] for i in row), "confidence": round(conf, 3)})
    return out


def _key(name):
    return re.sub(r"[^A-Z]", "", (name or "").upper())


def reocr_name_region(image_bgr, dets, ocr_reader, variant_funcs, clean_fn, valid_fn, plausible_fn,
                      variants=None, max_attempts_reported=24):
    """Re-reads the name value region. Returns a diagnostics dict; `best` is set only when at least one
    plausible, valid name was read. `variant_funcs` maps variant name -> f(image)->(image, scale)."""
    idx, kind = find_name_label(dets)
    if idx is None:
        return {"attempted": False, "reason": "NAME_LABEL_NOT_LOCATED"}
    rect = rect_of(dets[idx].get("box"))
    if not rect:
        return {"attempted": False, "reason": "NAME_LABEL_HAS_NO_GEOMETRY", "label_match": kind}
    page_h, page_w = image_bgr.shape[:2]
    attempts = []
    for region in name_search_regions(rect, page_w, page_h, dets, idx):
        x0, y0, x1, y1 = region["rect"]
        crop = image_bgr[y0:y1, x0:x1]
        if crop.size == 0:
            continue
        for vname in (variants or REGION_VARIANTS):
            if vname not in variant_funcs:
                continue
            try:
                img, _scale = variant_funcs[vname](crop)
                results = ocr_reader.readtext(img, allowlist=NAME_ALLOWLIST, paragraph=False)
            except Exception as exc:
                attempts.append({"region": region["name"], "variant": vname, "error": f"{type(exc).__name__}: {exc}"})
                continue
            for row in group_rows(results):
                cleaned = clean_fn(row["text"])
                ok = bool(cleaned) and valid_fn(cleaned) and plausible_fn(cleaned)
                attempts.append({"region": region["name"], "variant": vname, "raw": row["text"],
                                 "cleaned": cleaned, "confidence": row["confidence"], "usable": ok})

    groups = {}
    for a in attempts:
        if a.get("usable"):
            groups.setdefault(_key(a["cleaned"]), []).append(a)
    best = None
    for members in groups.values():
        variants_agree = len({m["variant"] for m in members})
        mean_conf = sum(m["confidence"] for m in members) / len(members)
        cand = {"name": max(members, key=lambda m: m["confidence"])["cleaned"], "agreement": variants_agree,
                "confidence": round(mean_conf, 3), "regions": sorted({m["region"] for m in members})}
        if best is None or (cand["agreement"], cand["confidence"]) > (best["agreement"], best["confidence"]):
            best = cand
    return {"attempted": True, "label_match": kind, "label_text": dets[idx].get("text"),
            "label_box": list(rect), "best": best, "attempts": attempts[:max_attempts_reported]}


def decide_name_override(first_pass, region_result, min_confident_conf=0.55, min_agreement=1):
    """Decides whether the region re-read should replace the first-pass name.
    first_pass: {"name", "confidence", "plausible"}. Returns None or a dict with name/confidence/status/source.
    CONFIDENT requires: label match, >= min_agreement variants, enough confidence, and >= 2 words."""
    if not region_result or not region_result.get("best"):
        return None
    best = region_result["best"]
    best_words = len((best["name"] or "").split())
    confirmed = ((region_result.get("label_match") in ("EXACT", "FUZZY"))
                 and best["agreement"] >= min_agreement
                 and best["confidence"] >= min_confident_conf
                 and best_words >= 2)
    if confirmed:
        return {"name": best["name"], "confidence": best["confidence"], "status": "CONFIDENT",
                "source": "HEADER_REGION_REOCR", "agreement": best["agreement"]}
    first_name = (first_pass or {}).get("name")
    first_words = len((first_name or "").split())
    if first_words >= 2 and best_words < 2:
        return None
    better = (not first_name) or (not (first_pass or {}).get("plausible", False)) \
        or (best["confidence"] > float((first_pass or {}).get("confidence", 0.0)) and best_words >= first_words)
    if better:
        return {"name": best["name"], "confidence": best["confidence"], "status": "UNCERTAIN",
                "source": "HEADER_REGION_REOCR_UNCONFIRMED", "agreement": best["agreement"]}
    return None

