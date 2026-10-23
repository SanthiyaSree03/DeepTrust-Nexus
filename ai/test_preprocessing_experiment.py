import cv2
import easyocr
import numpy as np

def run_experiment():
    print("=" * 60)
    print("DeepTrust Nexus — Milestone 2: Preprocessing Experiment")
    print("=" * 60)

    image_path = "sample_marksheet.jpg"
    print(f"\n[1] Loading image: {image_path}")
    original_img = cv2.imread(image_path)
    if original_img is None:
        print(f"Error: Unable to load {image_path}")
        return

    orig_h, orig_w, _ = original_img.shape
    print(f"    Original dimensions: {orig_w}x{orig_h} (RGB)")

    # 1. Grayscale
    gray = cv2.cvtColor(original_img, cv2.COLOR_BGR2GRAY)

    # 2. 2x Upscaling using Bicubic interpolation
    new_w, new_h = orig_w * 2, orig_h * 2
    upscaled = cv2.resize(gray, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
    print(f"    Upscaled dimensions: {new_w}x{new_h} (Grayscale)")

    # 3. CLAHE (Contrast Limited Adaptive Histogram Equalization)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    preprocessed_img = clahe.apply(upscaled)
    print("    Applied CLAHE contrast enhancement.")

    # Initialize EasyOCR reader (same instance for both to ensure identical configuration)
    print("\n[2] Initializing EasyOCR Reader (English)...")
    reader = easyocr.Reader(["en"])

    # Test A: Original Image
    print("\n[3] Running OCR on ORIGINAL image...")
    results_orig = reader.readtext(original_img)

    # Test B: Preprocessed Image
    print("[4] Running OCR on PREPROCESSED image...")
    results_prep = reader.readtext(preprocessed_img)

    def analyze_results(results, label):
        total_count = len(results)
        if total_count == 0:
            return {
                "label": label,
                "count": 0,
                "avg_conf": 0.0,
                "high": [],
                "med": [],
                "low": []
            }

        confs = [float(det[2]) for det in results]
        avg_conf = sum(confs) / total_count

        high = [det for det in results if float(det[2]) >= 0.70]
        med = [det for det in results if 0.30 <= float(det[2]) < 0.70]
        low = [det for det in results if float(det[2]) < 0.30]

        return {
            "label": label,
            "count": total_count,
            "avg_conf": avg_conf,
            "high": high,
            "med": med,
            "low": low
        }

    stats_orig = analyze_results(results_orig, "Original Image")
    stats_prep = analyze_results(results_prep, "Preprocessed Image")

    print("\n" + "=" * 60)
    print("EXPERIMENT RESULTS COMPARISON")
    print("=" * 60)
    print(f"{'Metric':<35} | {'Original':<12} | {'Preprocessed':<12}")
    print("-" * 65)
    print(f"{'Total detected boxes':<35} | {stats_orig['count']:<12} | {stats_prep['count']:<12}")
    print(f"{'Raw Average Confidence':<35} | {stats_orig['avg_conf']*100:.2f}%{'':<6} | {stats_prep['avg_conf']*100:.2f}%{'':<6}")
    print(f"{'High Confidence (>= 70%) count':<35} | {len(stats_orig['high']):<12} | {len(stats_prep['high']):<12}")
    print(f"{'Medium Confidence (30-69%) count':<35} | {len(stats_orig['med']):<12} | {len(stats_prep['med']):<12}")
    print(f"{'Low Confidence (< 30%) count':<35} | {len(stats_orig['low']):<12} | {len(stats_prep['low']):<12}")

    print("\n" + "-" * 60)
    print("HIGH-CONFIDENCE DETECTIONS SAMPLE (>= 70%)")
    print("-" * 60)
    print("Original Image:")
    if stats_orig['high']:
        for det in stats_orig['high'][:8]:
            print(f"  • '{det[1]}' (confidence: {float(det[2]):.2f})")
    else:
        print("  (None)")

    print("\nPreprocessed Image:")
    if stats_prep['high']:
        for det in stats_prep['high'][:8]:
            print(f"  • '{det[1]}' (confidence: {float(det[2]):.2f})")
    else:
        print("  (None)")

    # Spot-check key marksheet terms
    keywords = [
        "TAMILNADU", "HIGHER SECONDARY", "TAMIL", "ENGLISH",
        "PHYSICS", "CHEMISTRY", "BIOLOGY", "MATHEMATICS", "TOTAL"
    ]

    print("\n" + "-" * 60)
    print("KEY MARKSHEET TERMS RECOGNITION SPOT-CHECK")
    print("-" * 60)
    print(f"{'Keyword':<18} | {'Found in Original':<20} | {'Found in Preprocessed':<20}")
    print("-" * 65)

    def find_keyword(results, kw):
        matches = []
        for det in results:
            if kw.lower() in det[1].lower():
                matches.append(f"{det[1]} ({float(det[2]):.2f})")
        return ", ".join(matches) if matches else "Not found"

    for kw in keywords:
        found_orig = find_keyword(results_orig, kw)
        found_prep = find_keyword(results_prep, kw)
        # truncate long strings for display
        if len(found_orig) > 18:
            found_orig = found_orig[:15] + "..."
        if len(found_prep) > 18:
            found_prep = found_prep[:15] + "..."
        print(f"{kw:<18} | {found_orig:<20} | {found_prep:<20}")

    print("\n" + "=" * 60)
    print("EXPERIMENT COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    run_experiment()
