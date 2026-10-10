import os
import cv2
import easyocr

# Create OCR reader (initialized once at module level)
reader = easyocr.Reader(["en"])


def extract_text(image_path):
    """
    Extracts text and confidence scores from an image using EasyOCR.
    Applies image preprocessing (grayscale, 2x bicubic upscaling, and CLAHE)
    to improve character edge clarity on certificate scans.
    """
    # 1. Validate file path
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")

    # 2. Read and decode image
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Could not read or decode image at: {image_path}")

    # 3. Preprocessing pipeline
    # Grayscale conversion
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # 2x bicubic upscaling to enlarge small certificate text
    orig_h, orig_w = gray.shape[:2]
    upscaled = cv2.resize(gray, (orig_w * 2, orig_h * 2), interpolation=cv2.INTER_CUBIC)

    # Contrast Limited Adaptive Histogram Equalization (CLAHE)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    preprocessed_image = clahe.apply(upscaled)

    # 4. Perform OCR on the preprocessed image
    results = reader.readtext(preprocessed_image)

    # 5. Format results into structured list
    extracted_text = []

    for detection in results:
        text = detection[1]
        confidence = detection[2]

        extracted_text.append({
            "text": text,
            "confidence": round(float(confidence), 2)
        })

    return extracted_text