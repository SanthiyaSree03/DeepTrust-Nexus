from ocr import extract_text

image_path = "sample_marksheet.jpg"

results = extract_text(image_path)

print("\n===== OCR RESULT =====\n")

for item in results:
    print(f"{item['text']}  |  Confidence: {item['confidence']}")