# vehicle_detector.py
# Detects vehicles from camera frames using YOLOv8
# Returns vehicle count, density, bounding boxes
# Also integrates with ANPR and signal control

import cv2
import numpy as np
import threading
import random
from datetime import datetime

# Try to import YOLO - fall back to simulation if not available
try:
    from ultralytics import YOLO
    yolo_available = True
except ImportError:
    yolo_available = False
    print("[DETECTOR] YOLOv8 not available - using simulation mode")

# ─── Configuration ────────────────────────────────────────────
# YOLO classes that are vehicles
ALLOWED_CLASSES = [2, 3, 5, 7]  # car, motorcycle, bus, truck

# Density thresholds
DENSITY_LOW    = 3   # 0-3 vehicles
DENSITY_MEDIUM = 8   # 4-8 vehicles
# 9+ = High

# Global YOLO model (loaded once)
_model = None
_model_lock = threading.Lock()

# Latest detection results shared across system
latest_results = {
    "North": {"vehicle_count": 0, "density": "Low",  "boxes": [], "frame": None},
    "South": {"vehicle_count": 0, "density": "Low",  "boxes": [], "frame": None},
    "East":  {"vehicle_count": 0, "density": "Low",  "boxes": [], "frame": None},
    "West":  {"vehicle_count": 0, "density": "Low",  "boxes": [], "frame": None},
}

# ─── Load YOLO Model ──────────────────────────────────────────
def get_model():
    """
    Loads YOLOv8 nano model once and reuses it.
    Thread-safe using a lock.
    """
    global _model
    if not yolo_available:
        return None
    with _model_lock:
        if _model is None:
            try:
                _model = YOLO("yolov8n.pt")
                print("[DETECTOR] ✅ YOLOv8 model loaded")
            except Exception as e:
                print(f"[DETECTOR] ❌ Model load failed: {e}")
                _model = None
    return _model

# ─── Get Density Level ────────────────────────────────────────
def get_density(count):
    """
    Returns density level string based on vehicle count.
    """
    if count <= DENSITY_LOW:
        return "Low"
    elif count <= DENSITY_MEDIUM:
        return "Medium"
    return "High"

# ─── Get Latest Counts ────────────────────────────────────────
def get_latest_counts():
    """
    Returns current vehicle counts for all lanes.
    Used by route suggestion and analytics.
    """
    return {
        lane: data["vehicle_count"]
        for lane, data in latest_results.items()
    }

# ─── Simulate Detection ───────────────────────────────────────
def simulate_detection(lane_name):
    """
    Generates fake vehicle detection data when no camera
    or YOLO is available. Used for demo/testing.
    """
    count = random.randint(0, 12)
    density = get_density(count)

    # Create fake bounding boxes
    boxes = []
    for i in range(count):
        x = random.randint(50, 500)
        y = random.randint(50, 400)
        w = random.randint(60, 120)
        h = random.randint(40, 80)
        boxes.append((x, y, w, h))

    return {
        "vehicle_count": count,
        "density":       density,
        "boxes":         boxes,
        "simulated":     True,
    }

# ─── Detect Vehicles in Single Frame ─────────────────────────
def detect_vehicles_in_frame(frame, lane_name="Unknown"):
    """
    Runs YOLO detection on a single camera frame.
    Falls back to simulation if YOLO unavailable.
    Returns dict with count, density, boxes, annotated frame.
    """
    # Use simulation if frame is None
    if frame is None:
        sim = simulate_detection(lane_name)
        sim["annotated_frame"] = None
        return sim

    model = get_model()

    # Use simulation if YOLO not available
    if model is None:
        sim = simulate_detection(lane_name)
        sim["annotated_frame"] = frame
        return sim

    try:
        # Run YOLO inference
        results = model(frame, verbose=False, conf=0.4)
        boxes   = []
        count   = 0

        # Process detections
        for result in results:
            for box in result.boxes:
                cls = int(box.cls[0])
                if cls in ALLOWED_CLASSES:
                    # Get bounding box coordinates
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    conf = float(box.conf[0])
                    boxes.append((x1, y1, x2-x1, y2-y1))
                    count += 1

                    # Draw box on frame
                    cv2.rectangle(frame, (x1,y1), (x2,y2),
                                  (0,255,0), 2)
                    cv2.putText(frame,
                                f"Vehicle {conf:.0%}",
                                (x1, y1-8),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.5, (0,255,0), 1)

        density = get_density(count)

        # Draw count overlay on frame
        cv2.rectangle(frame, (0,0), (280,50), (0,0,0), -1)
        cv2.putText(frame,
                    f"{lane_name}: {count} vehicles | {density}",
                    (10, 32),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, (0,255,100), 2)

        result_data = {
            "vehicle_count":  count,
            "density":        density,
            "boxes":          boxes,
            "annotated_frame": frame,
            "simulated":      False,
        }

        # Update global latest results
        latest_results[lane_name] = result_data
        return result_data

    except Exception as e:
        print(f"[DETECTOR] Error on {lane_name}: {e}")
        sim = simulate_detection(lane_name)
        sim["annotated_frame"] = frame
        return sim

# ─── Run Detection on All Lanes ───────────────────────────────
def run_on_all_lanes(frames_dict):
    """
    Runs vehicle detection on all lane frames simultaneously.
    Uses threading for speed.
    frames_dict: {lane_name: frame} from camera_manager
    Returns: {lane_name: detection_results}
    """
    results  = {}
    threads  = []
    lock     = threading.Lock()

    def detect_one(lane, frame):
        result = detect_vehicles_in_frame(frame, lane)
        with lock:
            results[lane]         = result
            latest_results[lane]  = result

    for lane, frame in frames_dict.items():
        t = threading.Thread(
            target = detect_one,
            args   = (lane, frame),
            daemon = True
        )
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=5)

    # Fill missing lanes with simulation
    for lane in ["North", "South", "East", "West"]:
        if lane not in results:
            results[lane] = simulate_detection(lane)

    return results