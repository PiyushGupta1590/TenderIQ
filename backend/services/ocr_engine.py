"""
OCR Engine — image pre-processing + Tesseract OCR
Falls back gracefully if Tesseract is not installed.
"""
import os
import sys
from pathlib import Path
from typing import Tuple
import numpy as np
from PIL import Image
import cv2
from backend.config import TESSERACT_PATH

# Configure tesseract path
try:
    import pytesseract
    if os.path.exists(TESSERACT_PATH):
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False


def _pil_to_cv(img: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)


def _cv_to_pil(img: np.ndarray) -> Image.Image:
    return Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))


def preprocess_image(img: Image.Image) -> Tuple[Image.Image, float]:
    """
    Clean an image for OCR:
    1. Grayscale
    2. Deskew (simple heuristic)
    3. Denoise
    4. Binarize (Otsu's threshold)
    Returns (processed_image, estimated_quality_score 0-1)
    """
    cv_img = _pil_to_cv(img)

    # 1. Grayscale
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)

    # 2. Deskew
    coords = np.column_stack(np.where(gray < 200))
    if len(coords) > 50:
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        if abs(angle) < 30:  # only correct small skews
            h, w = gray.shape
            M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
            gray = cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

    # 3. Denoise
    gray = cv2.fastNlMeansDenoising(gray, h=10)

    # 4. Binarize (Otsu)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Estimate quality: ratio of non-white pixels (proxy for ink density / contrast)
    non_white = np.sum(binary < 128)
    total = binary.size
    density = non_white / total
    quality = min(1.0, density * 10)  # crude proxy
    quality = round(quality, 2)

    result = _cv_to_pil(cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR))
    return result, quality


def ocr_image(img: Image.Image) -> Tuple[str, float]:
    """
    Run OCR on a PIL image.
    Returns (text, confidence 0-1).
    """
    if not TESSERACT_AVAILABLE:
        return "", 0.0

    processed, quality = preprocess_image(img)

    try:
        data = pytesseract.image_to_data(
            processed,
            output_type=pytesseract.Output.DICT,
            config="--oem 3 --psm 6"
        )
        confs = [c for c in data["conf"] if c > 0]
        avg_conf = (sum(confs) / len(confs) / 100.0) if confs else 0.0
        text = pytesseract.image_to_string(processed, config="--oem 3 --psm 6")
        return text, round(min(avg_conf, quality + 0.1), 2)
    except Exception:
        return "", 0.0


def ocr_file(path: str) -> Tuple[str, float]:
    """OCR an image file. Returns (text, confidence)."""
    img = Image.open(path)
    return ocr_image(img)
