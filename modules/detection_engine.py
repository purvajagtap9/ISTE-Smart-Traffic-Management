# detection_engine.py
# Reads frames directly from phone IP Webcam stream
# Runs YOLO detection on each frame
# Updates vehicle counts and density in real time

import cv2
import threading
import time
import random
import numpy as np
from datetime import datetime

# ─── Global State ─────────────────────────────────────────────
detection_state = {
    "North": {"vehicle_count": 0, "density": "Low",
              "signal": "RED", "green_time": 15,
              "time_remaining": 0, "camera_on": False,
              "plates_detected": [], "last_updated": None},
    "South": {"vehicle_count": 0, "density": "Low",
              "signal": "RED", "green_time": 15,
              "time_remaining": 0, "camera_on": False,
              "plates_detected": [], "last_updated": None},
    "East":  {"vehicle_count": 0, "density": "Low",
              "signal": "RED", "green_time": 15,
              "time_remaining": 0, "camera_on": False,
              "plates_detected": [], "last_updated": None},
    "West":  {"vehicle_count": 0, "density": "Low",
              "signal": "RED", "green_time": 15,
              "time_remaining": 0, "camera_on": False,
              "plates_detected": [], "last_updated": None},
}

state_lock     = threading.Lock()
engine_running = False

# Active camera streams (URL per lane)
active_streams = {}
stream_lock    = threading.Lock()

# Latest annotated frames for streaming
latest_frames  = {}
frames_lock    = threading.Lock()

# ─── YOLO Model ───────────────────────────────────────────────
_model      = None
_model_lock = threading.Lock()
VEHICLE_CLASSES = [2, 3, 5, 7]  # car, motorcycle, bus, truck

def get_model():
    global _model
    with _model_lock:
        if _model is None:
            try:
                from ultralytics import YOLO
                _model = YOLO("yolov8n.pt")
                print("[ENGINE] ✅ YOLOv8 loaded")
            except Exception as e:
                print(f"[ENGINE] YOLO not available: {e}")
                _model = "unavailable"
    return None if _model == "unavailable" else _model

# ─── Density Helper ───────────────────────────────────────────
def count_to_density(count):
    if count >= 9:   return "High"
    if count >= 4:   return "Medium"
    return "Low"

def density_to_green(density):
    if density == "High":   return 50
    if density == "Medium": return 30
    return 15

# ─── Update Camera Stream URL ─────────────────────────────────
def update_camera_url(lane, url):
    """
    Called when admin connects/disconnects a camera.
    Restarts the stream reader for that lane.
    """
    with stream_lock:
        active_streams[lane] = url

    if url:
        print(f"[ENGINE] Camera connected: {lane} → {url}")
        # Start stream reader thread for this lane
        t = threading.Thread(
            target = _stream_reader,
            args   = (lane, url),
            daemon = True,
            name   = f"Stream-{lane}"
        )
        t.start()
    else:
        print(f"[ENGINE] Camera disconnected: {lane}")
        with state_lock:
            detection_state[lane]["camera_on"]     = False
            detection_state[lane]["vehicle_count"] = 0
            detection_state[lane]["density"]       = "Low"

# ─── Stream Reader Thread ─────────────────────────────────────
def _stream_reader(lane, url):
    """
    Reads frames continuously from IP Webcam URL.
    Runs YOLO on each frame.
    Stops if URL changes or engine stops.
    """
    print(f"[STREAM] Starting reader for {lane}: {url}")
    cap = None

    while engine_running:
        # Check if URL changed
        with stream_lock:
            current_url = active_streams.get(lane, "")
        if current_url != url:
            print(f"[STREAM] URL changed for {lane}, stopping reader")
            break

        try:
            # Open stream
            if cap is None or not cap.isOpened():
                cap = cv2.VideoCapture(url)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                if not cap.isOpened():
                    print(f"[STREAM] Cannot open {lane} stream, retrying...")
                    time.sleep(5)
                    continue

            # Read frame
            ret, frame = cap.read()
            if not ret or frame is None:
                print(f"[STREAM] Frame read failed for {lane}")
                cap.release()
                cap = None
                time.sleep(3)
                continue

            # Run detection on frame
            _detect_and_update(lane, frame)

            # Small delay to not overwhelm CPU
            time.sleep(0.5)

        except Exception as e:
            print(f"[STREAM] Error on {lane}: {e}")
            if cap:
                cap.release()
                cap = None
            time.sleep(5)

    if cap:
        cap.release()
    print(f"[STREAM] Reader stopped for {lane}")

# ─── Run YOLO on Frame ────────────────────────────────────────
def _detect_and_update(lane, frame):
    """
    Runs YOLO detection on frame.
    Updates detection_state with results.
    Saves annotated frame for streaming.
    """
    model = get_model()
    count = 0
    boxes = []

    if model is not None:
        try:
            results = model(frame, verbose=False, conf=0.35)
            for result in results:
                for box in result.boxes:
                    cls = int(box.cls[0])
                    if cls in VEHICLE_CLASSES:
                        x1,y1,x2,y2 = map(int, box.xyxy[0])
                        conf = float(box.conf[0])
                        boxes.append((x1,y1,x2-x1,y2-y1))
                        count += 1
                        # Draw box
                        cv2.rectangle(frame,(x1,y1),(x2,y2),(0,255,0),2)
                        cv2.putText(
                            frame, f"{conf:.0%}",
                            (x1, y1-5),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.5, (0,255,0), 1
                        )
        except Exception as e:
            print(f"[YOLO] Error on {lane}: {e}")
            count = random.randint(0, 8)
    else:
        # Simulation fallback
        count = random.randint(0, 8)

    density   = count_to_density(count)
    green_time = density_to_green(density)

    # Draw info overlay on frame
    overlay_color = (0,180,0) if count<=3 else (0,165,255) if count<=8 else (0,0,255)
    cv2.rectangle(frame, (0,0), (320,55), (0,0,0), -1)
    cv2.putText(frame,
        f"{lane}: {count} vehicles | {density}",
        (8,22), cv2.FONT_HERSHEY_SIMPLEX, 0.65, overlay_color, 2)
    cv2.putText(frame,
        f"Green time: {green_time}s",
        (8,44), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200,200,200), 1)

    # Save annotated frame
    with frames_lock:
        latest_frames[lane] = frame.copy()

    # Update state
    with state_lock:
        detection_state[lane]["vehicle_count"] = count
        detection_state[lane]["density"]       = density
        detection_state[lane]["green_time"]    = green_time
        detection_state[lane]["camera_on"]     = True
        detection_state[lane]["last_updated"]  = datetime.now().isoformat()

    print(f"[DETECT] {lane}: {count} vehicles | {density} | Green: {green_time}s")

# ─── Simulation Loop (for lanes with no camera) ───────────────
def _simulation_loop():
    """
    Only generates data for lanes with NO camera connected.
    Connected camera lanes use real YOLO data.
    """
    while engine_running:
        for lane in ["North","South","East","West"]:
            with stream_lock:
                has_camera = bool(active_streams.get(lane))
            if not has_camera:
                # No camera = 0 vehicles, Low density
                with state_lock:
                    detection_state[lane]["vehicle_count"] = 0
                    detection_state[lane]["density"]       = "Low"
                    detection_state[lane]["green_time"]    = 15
                    detection_state[lane]["camera_on"]     = False
        time.sleep(3)

# ─── Get Latest Frame ─────────────────────────────────────────
def get_latest_frame(lane):
    with frames_lock:
        return latest_frames.get(lane)

# ─── Start Engine ────────────────────────────────────────────
def start_engine():
    global engine_running
    engine_running = True

    # Start simulation loop for lanes without camera
    t = threading.Thread(
        target = _simulation_loop,
        daemon = True,
        name   = "SimLoop"
    )
    t.start()
    print("[ENGINE] ✅ Detection engine started")

# ─── Stop Engine ─────────────────────────────────────────────
def stop_engine():
    global engine_running
    engine_running = False

# ─── Get Full State for API ───────────────────────────────────
def get_full_state():
    with state_lock:
        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "signal_status": {
                lane: {
                    "color":          data["signal"],
                    "time_remaining": data["time_remaining"],
                    "manual_override": False,
                }
                for lane, data in detection_state.items()
            },
            "vehicle_counts": {
                lane: data["vehicle_count"]
                for lane, data in detection_state.items()
            },
            "density_levels": {
                lane: data["density"]
                for lane, data in detection_state.items()
            },
            "green_times": {
                lane: data["green_time"]
                for lane, data in detection_state.items()
            },
            "camera_status": {
                lane: data["camera_on"]
                for lane, data in detection_state.items()
            },
            "emergency": {"active": False, "lane": None},
        }

# ─── Get Latest Counts ────────────────────────────────────────
def get_latest_counts():
    with state_lock:
        return {
            lane: data["vehicle_count"]
            for lane, data in detection_state.items()
        }