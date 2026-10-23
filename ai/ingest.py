"""
ai/ingest.py - DeepTrust Nexus General Document Ingestion Pipeline
-----------------------------------------------------------------
Supports JPG, JPEG, PNG, and PDF certificate/marksheet uploads.
Validates file size, real file format via magic bytes, and page counts.
Handles both text-based and scanned PDFs, normalizes EXIF orientations,
applies adaptive deskewing and quality enhancement, while strictly
preserving the original uploaded files untouched.
"""

import os
import io
import re
import math
import cv2
import numpy as np
from PIL import Image, ExifTags
import pypdf
import pypdfium2 as pdfium

# Allowed file formats and magic byte signatures
MAGIC_BYTES = {
    "JPEG": [b"\xFF\xD8\xFF"],
    "PNG": [b"\x89PNG\r\n\x1a\n"],
    "PDF": [b"%PDF-"]
}

MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB
MAX_PDF_PAGES = 10                       # Standard educational certificates are 1-2 pages

def detect_file_type(file_path):
    """
    Detects actual file format from header magic bytes rather than trusting file extension.
    Returns 'JPEG', 'PNG', 'PDF', or 'UNKNOWN'.
    """
    if not os.path.exists(file_path):
        return "NOT_FOUND"

    try:
        with open(file_path, "rb") as f:
            header = f.read(16)
            for fmt, signatures in MAGIC_BYTES.items():
                for sig in signatures:
                    if header.startswith(sig):
                        return fmt
    except Exception:
        return "UNREADABLE"

    return "UNKNOWN"


def correct_exif_orientation(pil_image):
    """
    Inspects and applies EXIF orientation tag from mobile phone cameras.
    Returns orientation-corrected PIL Image.
    """
    try:
        exif = pil_image.getexif()
        if not exif:
            return pil_image

        orientation_tag = None
        for tag, value in ExifTags.TAGS.items():
            if value == "Orientation":
                orientation_tag = tag
                break

        if orientation_tag and orientation_tag in exif:
            orientation = exif[orientation_tag]
            if orientation == 3:
                return pil_image.rotate(180, expand=True)
            elif orientation == 6:
                return pil_image.rotate(270, expand=True)
            elif orientation == 8:
                return pil_image.rotate(90, expand=True)
    except Exception:
        pass

    return pil_image


def detect_and_deskew_image(cv2_bgr):
    """
    Detects slight rotation / skew in marksheet scans using horizontal text line projection
    or minAreaRect of text contours, and rotates if angle is between -25 and +25 degrees.
    """
    try:
        gray = cv2.cvtColor(cv2_bgr, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape[:2]

        # Use Otsu inversion to find text components
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # Morphological closing along horizontal axis to merge words into text lines
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 3))
        dilated = cv2.dilate(thresh, kernel, iterations=1)

        contours, _ = cv2.findContours(dilated, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        angles = []

        for c in contours:
            area = cv2.contourArea(c)
            if area < 500:
                continue
            rect = cv2.minAreaRect(c)
            angle = rect[-1]
            rect_w, rect_h = rect[1]

            if rect_w < rect_h:
                angle = angle - 90.0

            # Only accept gentle skew angles, ignore vertical borders or tables
            if -25.0 <= angle <= 25.0 and abs(angle) > 0.4:
                angles.append(angle)

        if len(angles) >= 5:
            median_angle = float(np.median(angles))
            if abs(median_angle) >= 0.5:
                # Rotate image to correct skew
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
                deskewed = cv2.warpAffine(
                    cv2_bgr, M, (w, h),
                    flags=cv2.INTER_CUBIC,
                    borderMode=cv2.BORDER_REPLICATE
                )
                return deskewed, round(median_angle, 2)
    except Exception:
        pass

    return cv2_bgr, 0.0


def enhance_for_analysis(cv2_bgr):
    """
    Prepares a clean, high-clarity copy of the image for OCR and QR detection.
    Does NOT overwrite the original image.
    Scales low-resolution images up to standard document resolution (~1600px width).
    """
    h, w = cv2_bgr.shape[:2]

    # Target minimum width: 1400px for clear text recognition
    scale = 1.0
    if w < 1200 or h < 1200:
        scale = max(1400.0 / max(w, 1), 1.5)
        # Cap scaling so we don't blow up memory
        if scale > 3.0:
            scale = 3.0
        new_w = int(round(w * scale))
        new_h = int(round(h * scale))
        upscaled = cv2.resize(cv2_bgr, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
    else:
        upscaled = cv2_bgr.copy()

    # Gentle bilateral filtering to smooth JPEG blocking artifacts while keeping text edges crisp
    denoised = cv2.bilateralFilter(upscaled, d=5, sigmaColor=30, sigmaSpace=30)
    return denoised, scale


def detect_pdf_signature_markers(file_path):
    """Detects (it does NOT verify) structural markers of an embedded digital signature in a PDF:
    a signature dictionary carries /ByteRange together with /Type /Sig or a /SubFilter.

    This tells the dashboard "an embedded signature appears to exist, but nothing has checked it".
    Cryptographic validation (integrity of the signed byte ranges, certificate chain, trust anchor,
    revocation) is NOT implemented here. Signatures inside compressed object streams can be missed.
    A handwritten or printed signature image is never reported by this function.
    """
    try:
        with open(file_path, "rb") as fh:
            data = fh.read()
    except Exception as exc:
        return {"detected": False, "verified": False, "error": f"{type(exc).__name__}: {exc}"}
    byte_ranges = len(re.findall(rb"/ByteRange\s*\[", data))
    sig_dicts = len(re.findall(rb"/Type\s*/Sig\b", data)) + len(re.findall(rb"/FT\s*/Sig\b", data))
    sub_filters = sorted({m.decode("latin-1") for m in re.findall(rb"/SubFilter\s*/([A-Za-z0-9._\-]+)", data)})
    detected = byte_ranges > 0 and (sig_dicts > 0 or bool(sub_filters))
    return {
        "detected": detected,
        "signature_count_estimate": byte_ranges if detected else 0,
        "sub_filters": sub_filters,
        "verified": False,
        "note": ("Embedded PDF signature structure found; cryptographic verification is not implemented, "
                 "so it is reported as unverified." if detected else "No embedded PDF signature structure found."),
    }


def ingest_document(file_path):
    """
    Main entry point for document ingestion.
    Validates file format, pages, extracts embedded text (for PDFs),
    and produces high-resolution raster images for each page.

    Returns dict with structure:
    {
        "success": bool,
        "format": "JPEG" | "PNG" | "PDF",
        "file_size": int,
        "page_count": int,
        "pages": [
            {
                "page_number": int,
                "image_bgr": np.ndarray,
                "deskew_angle": float,
                "scale_factor": float,
                "embedded_text": str or None,
                "is_text_pdf": bool
            }
        ],
        "error": str or None
    }
    """
    if not os.path.exists(file_path):
        return {
            "success": False,
            "error": f"File does not exist: {file_path}"
        }

    file_size = os.path.getsize(file_path)
    if file_size > MAX_FILE_SIZE_BYTES:
        return {
            "success": False,
            "error": f"File size ({file_size / (1024*1024):.1f} MB) exceeds maximum allowed limit of {MAX_FILE_SIZE_BYTES // (1024*1024)} MB."
        }
    if file_size == 0:
        return {
            "success": False,
            "error": "The uploaded file is empty (0 bytes)."
        }

    fmt = detect_file_type(file_path)
    if fmt not in ["JPEG", "PNG", "PDF"]:
        return {
            "success": False,
            "error": f"Unsupported or unrecognized file format. Only standard JPG, PNG, and PDF files are supported."
        }

    pages_output = []

    # Case A: PDF Document Ingestion
    if fmt == "PDF":
        try:
            # 1. Inspect PDF structure and embedded text via pypdf
            reader = pypdf.PdfReader(file_path)
            if getattr(reader, "is_encrypted", False):
                return {
                    "success": False,
                    "error": "The PDF document is password-protected or encrypted. Please upload an unencrypted marksheet."
                }

            num_pages = len(reader.pages)
            if num_pages == 0:
                return {
                    "success": False,
                    "error": "The PDF document contains 0 pages or is corrupted."
                }
            if num_pages > MAX_PDF_PAGES:
                return {
                    "success": False,
                    "error": f"PDF contains {num_pages} pages, which exceeds the allowed maximum of {MAX_PDF_PAGES} pages for marksheet verification."
                }

            # 2. Render each page to image via pypdfium2 at high resolution (300 DPI / scale 3.0)
            pdf = pdfium.PdfDocument(file_path)
            for page_idx in range(num_pages):
                # Extract any embedded native text
                page_text = ""
                try:
                    page_text = reader.pages[page_idx].extract_text() or ""
                except Exception:
                    page_text = ""

                # Render page with adaptive scale (capped at ~1800px long side to avoid 20+ megapixel bloat)
                page = pdf[page_idx]
                w_pt, h_pt = page.get_size()
                target_long = 1800
                max_pt = max(w_pt, h_pt, 1)
                scale = min(2.0, max(1.0, round(target_long / max_pt, 2)))
                pil_image = page.render(scale=scale).to_pil()

                # Convert PIL RGB to cv2 BGR
                cv2_bgr = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

                # Deskew and enhance
                deskewed, deskew_angle = detect_and_deskew_image(cv2_bgr)
                enhanced, scale_factor = enhance_for_analysis(deskewed)

                pages_output.append({
                    "page_number": page_idx + 1,
                    "image_bgr": enhanced,
                    "deskew_angle": deskew_angle,
                    "scale_factor": scale_factor,
                    "embedded_text": page_text.strip() if page_text else None,
                    "is_text_pdf": len(page_text.strip()) > 50
                })

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to parse or render PDF document: {str(e)}"
            }

    # Case B: Image Ingestion (JPEG, PNG)
    else:
        try:
            # Open via PIL first to handle EXIF orientation properly
            pil_img = Image.open(file_path)
            pil_img = correct_exif_orientation(pil_img)

            # Convert to RGB if needed (handling RGBA, palette, 1-bit)
            if pil_img.mode != "RGB":
                pil_img = pil_img.convert("RGB")

            cv2_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

            # Deskew and enhance
            deskewed, deskew_angle = detect_and_deskew_image(cv2_bgr)
            enhanced, scale_factor = enhance_for_analysis(deskewed)

            pages_output.append({
                "page_number": 1,
                "image_bgr": enhanced,
                "deskew_angle": deskew_angle,
                "scale_factor": scale_factor,
                "embedded_text": None,
                "is_text_pdf": False
            })

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to decode or process image file: {str(e)}"
            }

    return {
        "success": True,
        "format": fmt,
        "file_size": file_size,
        "page_count": len(pages_output),
        "pages": pages_output,
        "pdf_signature_markers": detect_pdf_signature_markers(file_path) if fmt == "PDF" else None,
        "error": None
    }
