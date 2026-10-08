from ocr import extract_text

image_path = "sample_marksheet.jpg"

results = extract_text(image_path)

print("\n===== OCR RESULT =====\n")

total_confidence = 0

for item in results:
    print(f"{item['text']} | Confidence: {item['confidence']}")
    total_confidence += item["confidence"]

if results:
    average = total_confidence / len(results)
    print("\n===== OVERALL CONFIDENCE =====")
    print(f"Average Confidence: {average:.2f}")
    print(f"Percentage: {average * 100:.2f}%")