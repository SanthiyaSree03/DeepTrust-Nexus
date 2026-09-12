import easyocr

# Create OCR reader
reader = easyocr.Reader(["en"])


def extract_text(image_path):
    results = reader.readtext(image_path)

    extracted_text = []

    for detection in results:
        text = detection[1]
        confidence = detection[2]

        extracted_text.append({
            "text": text,
            "confidence": round(float(confidence), 2)
        })

    return extracted_text