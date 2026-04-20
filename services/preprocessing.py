"""
Image Preprocessing Service
=============================
Applies a multi-step OpenCV pipeline to prepare images
for optimal Tesseract OCR accuracy.

Pipeline:
1. Resolution normalization (upscale to ~300 DPI equivalent)
2. Grayscale conversion
3. Noise removal (Non-local means denoising)
4. Otsu's binarization (adaptive thresholding)
5. Deskew (correct rotation using minAreaRect)
"""

import cv2
import numpy as np

from config import TARGET_DPI


def preprocess_image(img: np.ndarray) -> np.ndarray:
    """
    Run the full preprocessing pipeline on an input image.

    Args:
        img: BGR image as numpy array.

    Returns:
        Preprocessed grayscale image as numpy array.
    """
    img = _normalize_resolution(img)
    gray = _to_grayscale(img)
    enhanced = _enhance_contrast(gray)
    denoised = _remove_noise(enhanced)
    sharpened = _sharpen(denoised)
    binary = _threshold(sharpened)
    deskewed = _deskew(binary)
    return deskewed


def _normalize_resolution(img: np.ndarray) -> np.ndarray:
    """
    Upscale small images to ensure sufficient resolution for OCR.
    Target: at least 2000px on the longest side (approx 300 DPI for A4).
    """
    h, w = img.shape[:2]
    target_min_dim = 2500  # Pushed to 2500 for maximum text fidelity

    if max(h, w) < target_min_dim:
        scale = target_min_dim / max(h, w)
        new_w = int(w * scale)
        new_h = int(h * scale)
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)

    return img


def _to_grayscale(img: np.ndarray) -> np.ndarray:
    """Convert BGR image to grayscale."""
    if len(img.shape) == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img


def _enhance_contrast(gray: np.ndarray) -> np.ndarray:
    """
    Apply CLAHE (Contrast Limited Adaptive Histogram Equalization).
    This dramatically improves text visibility against varying backgrounds/shadows.
    """
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    return clahe.apply(gray)


def _remove_noise(gray: np.ndarray) -> np.ndarray:
    """
    Apply Non-local Means Denoising to remove scan artifacts.
    Parameters tuned aggressively for document noise while preserving edges.
    """
    return cv2.fastNlMeansDenoising(
        gray,
        h=12,             # Increased filter strength
        templateWindowSize=7,
        searchWindowSize=21,
    )


def _sharpen(gray: np.ndarray) -> np.ndarray:
    """
    Apply Unsharp Masking to make characters perfectly crisp before binarization.
    It takes the original frame and subtracts a blurred version of itself.
    """
    gaussian = cv2.GaussianBlur(gray, (0, 0), 2.0)
    # addWeighted combines the images: (gray * 1.5) + (gaussian * -0.5)
    return cv2.addWeighted(gray, 1.5, gaussian, -0.5, 0)


def _threshold(gray: np.ndarray) -> np.ndarray:
    """
    Apply Adaptive Gaussian Thresholding.
    Unlike Otsu (which uses a global value), Adaptive handles shadows and gradient
    lighting common in smartphone photos of invoices.
    """
    return cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        41,  # Large block size because we run at 2500px resolution
        5    # Subtractive constant
    )


def _deskew(binary: np.ndarray) -> np.ndarray:
    """
    Detect and correct skew angle using minAreaRect on contours.
    Only corrects angles within ±15° to avoid false rotations.
    """
    # Find contour points
    coords = np.column_stack(np.where(binary < 128))  # dark pixels

    if len(coords) < 100:
        # Not enough points to determine skew
        return binary

    # Get minimum area rectangle
    angle = cv2.minAreaRect(coords)[-1]

    # Normalize the angle
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    # Only correct if skew is significant but not extreme
    if abs(angle) < 0.5 or abs(angle) > 15:
        return binary

    # Rotate to correct skew
    h, w = binary.shape[:2]
    center = (w // 2, h // 2)
    rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        binary, rotation_matrix, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )

    return rotated
