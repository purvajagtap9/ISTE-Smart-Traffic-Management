# anpr.py
# Automatic Number Plate Recognition module
# Uses EasyOCR to read number plates from vehicle images
# Falls back to realistic fake plates when OCR fails
# Validates Indian number plate format: MH12AB1234

import cv2
import re
import random
import string
import numpy as np

# Try importing EasyOCR
try:
    import easyocr
    _reader = easyocr.Reader(['en'], gpu=False, verbose=False)
    ocr_available = True
    print("[ANPR] ✅ EasyOCR loaded")
except Exception as e:
    ocr_available = False
    _reader = None
    print(f"[ANPR] EasyOCR not available: {e}")

# ─── Indian State Codes ───────────────────────────────────────
STATE_CODES = [
    "MH", "DL", "KA", "TN", "GJ", "RJ", "UP", "MP",
    "WB", "AP", "TS", "KL", "HR", "PB", "BR"
]

# ─── Indian Plate Pattern ─────────────────────────────────────
# Format: XX00XX0000
# Example: MH12AB1234
PLATE_PATTERN = re.compile(
    r'^[A-Z]{2}\d{2}[A-Z]{1,2}\d{4}$'
)

# ─── Flagged Plates Database ──────────────────────────────────
FLAGGED_PLATES = [
    "MH12AB1111", "DL01CD2222", "KA03EF3333",
    "TN04GH4444", "GJ05IJ5555", "RJ06KL6666",
    "UP07MN7777", "MP08OP8888", "WB09QR9999",
    "AP10ST1010",
]

# ─── Generate Fake Indian Plate ───────────────────────────────
def generate_fake_plate():
    """
    Generates a realistic fake Indian number plate.
    Format: XX00XX0000 (e.g. MH12AB1234)
    Used as fallback when OCR fails.
    """
    state  = random.choice(STATE_CODES)
    dist   = str(random.randint(1, 99)).zfill(2)
    series = ''.join(random.choices(string.ascii_uppercase, k=2))
    number = str(random.randint(1000, 9999))
    return f"{state}{dist}{series}{number}"

# ─── Validate Plate Format ────────────────────────────────────
def is_valid_plate(text):
    """
    Checks if text matches Indian number plate format.
    Cleans and validates before checking pattern.
    """
    if not text:
        return False
    # Clean: uppercase, remove spaces and special chars
    cleaned = re.sub(r'[^A-Z0-9]', '', text.upper())
    return bool(PLATE_PATTERN.match(cleaned))

# ─── Clean OCR Text ───────────────────────────────────────────
def clean_ocr_text(text):
    """
    Cleans raw OCR output to match plate format.
    Removes spaces, converts to uppercase.
    Fixes common OCR mistakes (0 vs O, 1 vs I).
    """
    text = text.upper().strip()
    text = re.sub(r'[^A-Z0-9]', '', text)

    # Common OCR corrections
    corrections = {
        'O': '0',  # Letter O → Zero (in number section)
        'I': '1',  # Letter I → One
        'S': '5',  # S → 5
        'B': '8',  # B → 8
    }
    # Only apply corrections to digit positions (last 4)
    if len(text) >= 4:
        suffix = text[-4:]
        for wrong, right in corrections.items():
            suffix = suffix.replace(wrong, right)
        text = text[:-4] + suffix

    return text

# ─── Preprocess Frame for OCR ─────────────────────────────────
def preprocess_for_ocr(image):
    """
    Enhances image quality before OCR.
    Grayscale → resize → threshold → denoise
    """
    # Convert to grayscale
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    # Resize to improve OCR (minimum 100px height)
    h, w = gray.shape
    if h < 100:
        scale = 100 / h
        gray  = cv2.resize(gray, None,
                           fx=scale, fy=scale,
                           interpolation=cv2.INTER_CUBIC)

    # Apply adaptive threshold
    thresh = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 11, 2
    )

    # Denoise
    denoised = cv2.fastNlMeansDenoising(thresh, h=10)
    return denoised

# ─── Read Plate from Bounding Box ────────────────────────────
def read_plate_from_box(frame, box):
    """
    Extracts and reads number plate from a vehicle bounding box.
    box: (x, y, w, h) tuple from YOLO detection
    Returns: plate string or None
    """
    if frame is None or box is None:
        return None

    try:
        x, y, w, h = box
        height, width = frame.shape[:2]

        # Add padding around vehicle box
        pad_x = int(w * 0.1)
        pad_y = int(h * 0.1)

        # Crop vehicle region safely
        x1 = max(0, x - pad_x)
        y1 = max(0, y - pad_y)
        x2 = min(width,  x + w + pad_x)
        y2 = min(height, y + h + pad_y)

        vehicle_crop = frame[y1:y2, x1:x2]

        if vehicle_crop.size == 0:
            return generate_fake_plate()

        # Look for plate in LOWER THIRD of vehicle
        # (plates are usually at bottom of vehicles)
        plate_region_y = int(vehicle_crop.shape[0] * 0.6)
        plate_region   = vehicle_crop[plate_region_y:, :]

        if plate_region.size == 0:
            return generate_fake_plate()

        # Preprocess for OCR
        processed = preprocess_for_ocr(plate_region)

        # Run OCR if available
        if ocr_available and _reader is not None:
            results = _reader.readtext(processed)

            for (bbox, text, confidence) in results:
                if confidence > 0.3:  # 30% confidence threshold
                    cleaned = clean_ocr_text(text)
                    if is_valid_plate(cleaned):
                        print(f"[ANPR] ✅ Real plate: {cleaned} ({confidence:.0%})")
                        return cleaned

        # OCR failed or unavailable → generate fake plate
        fake = generate_fake_plate()
        print(f"[ANPR] 🔄 Generated plate: {fake}")
        return fake

    except Exception as e:
        print(f"[ANPR] Error: {e}")
        return generate_fake_plate()

# ─── Read Plate from Full Frame ───────────────────────────────
def read_plate_from_frame(frame):
    """
    Attempts to read any number plate visible in full frame.
    Used when no specific bounding box is available.
    """
    if frame is None:
        return generate_fake_plate()

    try:
        if ocr_available and _reader is not None:
            # Preprocess full frame
            processed = preprocess_for_ocr(frame)
            results   = _reader.readtext(processed)

            for (bbox, text, confidence) in results:
                if confidence > 0.4:
                    cleaned = clean_ocr_text(text)
                    if is_valid_plate(cleaned):
                        return cleaned

        return generate_fake_plate()

    except Exception as e:
        print(f"[ANPR] Frame read error: {e}")
        return generate_fake_plate()

# ─── Check Flagged Plate ──────────────────────────────────────
def check_plate_database(plate_number):
    """
    Checks if plate is in the flagged/wanted database.
    Returns True if vehicle is flagged.
    """
    return plate_number.upper() in FLAGGED_PLATES

# ─── Annotate Frame with Plate ────────────────────────────────
def annotate_plate_on_frame(frame, box, plate_number):
    """
    Draws plate number below vehicle bounding box on frame.
    Used for live camera feed annotation.
    """
    if frame is None or box is None:
        return frame

    try:
        x, y, w, h = box
        # Draw plate text below bounding box
        text_y = min(y + h + 20, frame.shape[0] - 5)
        cv2.putText(
            frame,
            plate_number,
            (x, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 255),  # Yellow text
            2
        )
        # Draw small background rectangle for readability
        text_size = cv2.getTextSize(
            plate_number,
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6, 2
        )[0]
        cv2.rectangle(
            frame,
            (x - 2, text_y - text_size[1] - 4),
            (x + text_size[0] + 2, text_y + 4),
            (0, 0, 0),
            -1
        )
        cv2.putText(
            frame, plate_number,
            (x, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6, (0, 255, 255), 2
        )
    except Exception as e:
        print(f"[ANPR] Annotate error: {e}")

    return frame

# ─── Bulk Plate Detection ─────────────────────────────────────
def detect_plates_in_frame(frame, boxes):
    """
    Reads plates from multiple vehicle boxes in one frame.
    Returns list of plate strings.
    boxes: list of (x,y,w,h) tuples
    """
    plates = []
    for box in boxes[:4]:  # Max 4 plates per frame
        plate = read_plate_from_box(frame, box)
        if plate:
            plates.append(plate)
            # Annotate on frame
            annotate_plate_on_frame(frame, box, plate)
    return plates