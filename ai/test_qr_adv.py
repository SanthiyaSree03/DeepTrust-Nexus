"""
ai/test_qr_adv.py - Test advanced multi-strategy QR detection & 4-state reporting
"""

import os
import sys
import cv2
import numpy as np
import qrcode

def generate_test_qrs():
    # 1. Clean synthetic QR
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data("https://cbse.gov.in/verify?id=TEST1234")
    qr.make(fit=True)
    clean_img = np.array(qr.make_image(fill_color="black", back_color="white").convert("RGB"))
    clean_bgr = cv2.cvtColor(clean_img, cv2.COLOR_BGR2GRAY)

    # 2. Downscaled & re-upscaled with mild blur (typical camera artifact)
    small = cv2.resize(clean_bgr, (70, 70), interpolation=cv2.INTER_AREA)
    small_blur = cv2.GaussianBlur(small, (3, 3), 1.2)
    re_up = cv2.resize(small_blur, (300, 300), interpolation=cv2.INTER_LINEAR)

    # 3. Clean background with no QR
    blank_bgr = np.ones((400, 400), dtype=np.uint8) * 255

    return clean_bgr, re_up, blank_bgr

if __name__ == "__main__":
    clean, degraded, blank = generate_test_qrs()
    detector = cv2.QRCodeDetector()

    # Clean
    v1, p1, _ = detector.detectAndDecode(clean)
    print(f"Clean QR: decoded={bool(v1)}")

    # Degraded
    ret_d, pts_d = detector.detect(degraded)
    val_d, _, _ = detector.detectAndDecode(degraded)
    print(f"Degraded QR: detect={ret_d}, pts={pts_d is not None}, val='{val_d}'")

    # Blank
    ret_blank, pts_blank = detector.detect(blank)
    print(f"Blank: detect={ret_blank}, pts={pts_blank is not None}")

    # Real marksheet
    real_path = "ai/santhiya 12th ms.jpeg"
    if os.path.exists(real_path):
        real_img = cv2.imread(real_path)
        ret_r, pts_r = detector.detect(real_img)
        val_r, _, _ = detector.detectAndDecode(real_img)
        print(f"Real marksheet: detect={ret_r}, pts={pts_r is not None}, val='{val_r}'")
