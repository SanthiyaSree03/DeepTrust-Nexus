"""
ai/test_ocr_clarity.py - Tests OCR extraction on real marksheet with ingestion preprocessing
"""

import os
import sys
import cv2
import easyocr
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ingest import ingest_document

def test_marksheet_ocr():
    img_path = "ai/santhiya 12th ms.jpeg"
    if not os.path.exists(img_path):
        print("Image not found")
        return

    # Ingest document with adaptive scaling & deskewing
    doc = ingest_document(img_path)
    prep_bgr = doc["pages"][0]["image_bgr"]
    h, w = prep_bgr.shape[:2]
    print(f"Ingested shape: {w}x{h}, scale: {doc['pages'][0]['scale_factor']}")

    reader = easyocr.Reader(["en"])

    # Grayscale + CLAHE on scaled image
    gray = cv2.cvtColor(prep_bgr, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    results = reader.readtext(enhanced)
    print(f"Total detections: {len(results)}")

    # Print detections with confidence >= 0.20
    confident_boxes = [r for r in results if r[2] >= 0.20]
    all_confidences = [r[2] for r in results]
    avg_all = sum(all_confidences) / len(all_confidences) if all_confidences else 0
    avg_confident = sum(r[2] for r in confident_boxes) / len(confident_boxes) if confident_boxes else 0

    print(f"All boxes avg confidence: {avg_all*100:.1f}%")
    print(f"Confident boxes (>=20%) count: {len(confident_boxes)}, avg: {avg_confident*100:.1f}%")

    print("\nSample detections near top/middle:")
    for r in results[:25]:
        print(f"  conf={r[2]:.2f}: '{r[1]}'")

if __name__ == "__main__":
    test_marksheet_ocr()
