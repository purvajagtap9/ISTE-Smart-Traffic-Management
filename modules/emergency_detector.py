# emergency_detector.py
# This module detects emergency vehicles from camera frames
# It uses two methods: color detection and size detection
# It also allows manual triggering for demo purposes

import cv2
import numpy as np
import threading
import time
from datetime import datetime

# ─── Global State ───────────────────────────────────────────
# Stores active emergency status for each lane
emergency_state = {
    "North": {"active": False, "detected_at": None, "triggered_by": "none"},
    "South": {"active": False, "detected_at": None, "triggered_by": "none"},
    "East":  {"active": False, "detected_at": None, "triggered_by": "none"},
    "West":  {"active": False, "detected_at": None, "triggered_by": "none"},
}

# How long emergency mode stays active (in seconds)
EMERGENCY_DURATION = 20

# ─── Method 1: Detect Red/Blue Flashing Lights ──────────────
def detect_emergency_lights(frame):
    """
    Looks for red or blue colored regions in the frame.
    Ambulances and police vehicles have red/blue flashing lights.
    Returns True if emergency lights are detected.
    """
    if frame is None:
        return False

    # Convert frame from BGR (OpenCV default) to HSV color space
    # HSV makes it easier to detect specific colors
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # Define red color range in HSV
    # Red appears at both ends of the HSV hue spectrum
    red_lower1 = np.array([0, 120, 70])
    red_upper1 = np.array([10, 255, 255])
    red_lower2 = np.array([170, 120, 70])
    red_upper2 = np.array([180, 255, 255])

    # Define blue color range in HSV
    blue_lower = np.array([100, 150, 70])
    blue_upper = np.array([130, 255, 255])

    # Create masks for red and blue colors
    red_mask1 = cv2.inRange(hsv, red_lower1, red_upper1)
    red_mask2 = cv2.inRange(hsv, red_lower2, red_upper2)
    red_mask = cv2.bitwise_or(red_mask1, red_mask2)
    blue_mask = cv2.inRange(hsv, blue_lower, blue_upper)

    # Count how many pixels match red or blue
    red_pixels = cv2.countNonZero(red_mask)
    blue_pixels = cv2.countNonZero(blue_mask)

    # Get total pixels in frame
    total_pixels = frame.shape[0] * frame.shape[1]

    # If more than 1% of frame is red or blue → possible emergency vehicle
    red_ratio = red_pixels / total_pixels
    blue_ratio = blue_pixels / total_pixels

    if red_ratio > 0.01 or blue_ratio > 0.01:
        return True

    return False

# ─── Method 2: Detect Large Vehicles (Ambulance Size) ───────
def detect_large_vehicle(vehicle_boxes):
    """
    Checks if any detected vehicle bounding box is unusually large.
    Ambulances and fire trucks are bigger than regular cars.
    vehicle_boxes: list of (x, y, w, h) bounding boxes from YOLO
    Returns True if a large vehicle is found.
    """
    for box in vehicle_boxes:
        x, y, w, h = box
        area = w * h
        # If vehicle area is more than 15000 pixels → large vehicle
        if area > 15000:
            return True
    return False

# ─── Combined Detection Logic ────────────────────────────────
def detect_emergency(frame, lane_name, vehicle_boxes=None):
    """
    Combines both methods to detect emergency vehicles.
    If either method triggers → emergency is confirmed.
    frame: camera frame for this lane
    lane_name: "North", "South", "East", or "West"
    vehicle_boxes: optional list of bounding boxes from YOLO
    Returns True if emergency detected.
    """
    if vehicle_boxes is None:
        vehicle_boxes = []

    # Run both detection methods
    lights_detected = detect_emergency_lights(frame)
    large_vehicle = detect_large_vehicle(vehicle_boxes)

    # If either method detects emergency
    if lights_detected or large_vehicle:
        # Only trigger if not already active for this lane
        if not emergency_state[lane_name]["active"]:
            trigger_emergency(lane_name, triggered_by="auto")
        return True

    return False

# ─── Trigger Emergency Mode ──────────────────────────────────
def trigger_emergency(lane_name, triggered_by="auto"):
    """
    Activates emergency mode for a specific lane.
    Sets the lane to green immediately.
    Auto-cancels after EMERGENCY_DURATION seconds.
    lane_name: which lane has the emergency
    triggered_by: "auto" (detected) or "manual" (button press)
    """
    # Check if lane name is valid
    if lane_name not in emergency_state:
        print(f"[EMERGENCY] Invalid lane: {lane_name}")
        return

    # Set emergency state as active
    emergency_state[lane_name]["active"] = True
    emergency_state[lane_name]["detected_at"] = datetime.now().isoformat()
    emergency_state[lane_name]["triggered_by"] = triggered_by

    # Print green corridor message
    print(f"\n🚨 EMERGENCY DETECTED on {lane_name} lane!")
    print(f"   Triggered by: {triggered_by}")
    print(f"   GREEN CORRIDOR activated for {lane_name}")
    print(f"   All other lanes set to RED\n")

    # Log to file
    log_emergency(lane_name, triggered_by)

    # Start a timer to auto-cancel after EMERGENCY_DURATION seconds
    timer = threading.Timer(EMERGENCY_DURATION, cancel_emergency, args=[lane_name])
    timer.daemon = True  # Timer stops if main program stops
    timer.start()

# ─── Cancel Emergency Mode ───────────────────────────────────
def cancel_emergency(lane_name):
    """
    Deactivates emergency mode for a lane.
    Called automatically after EMERGENCY_DURATION seconds.
    """
    if lane_name in emergency_state:
        emergency_state[lane_name]["active"] = False
        emergency_state[lane_name]["triggered_by"] = "none"
        print(f"✅ Emergency cleared on {lane_name} lane. Normal operation resumed.")

# ─── Manual Trigger (for Demo Button) ───────────────────────
def manual_trigger(lane_name):
    """
    Allows the demo presenter to manually trigger emergency
    from the dashboard with a button click.
    This is very useful during live demo to the panel.
    """
    print(f"[MANUAL] Emergency manually triggered for {lane_name}")
    trigger_emergency(lane_name, triggered_by="manual")

# ─── Get Emergency Status ────────────────────────────────────
def get_emergency_status():
    """
    Returns current emergency state for all lanes.
    Used by Flask dashboard to show emergency alerts.
    """
    return emergency_state

# ─── Check if Any Lane Has Emergency ────────────────────────
def any_emergency_active():
    """
    Returns True if any lane currently has active emergency.
    Used by signal controller to override normal signal cycle.
    """
    for lane, state in emergency_state.items():
        if state["active"]:
            return True
    return False

# ─── Get Emergency Lane ──────────────────────────────────────
def get_emergency_lane():
    """
    Returns the name of the lane with active emergency.
    Returns None if no emergency is active.
    """
    for lane, state in emergency_state.items():
        if state["active"]:
            return lane
    return None

# ─── Log Emergency to File ───────────────────────────────────
def log_emergency(lane_name, triggered_by):
    """
    Saves emergency event to emergency_log.txt file.
    Each line has: timestamp, lane, triggered_by
    """
    try:
        # Open file in append mode so previous logs are not deleted
        with open("emergency_log.txt", "a") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"{timestamp} | Lane: {lane_name} | Triggered by: {triggered_by}\n")
    except Exception as e:
        print(f"[EMERGENCY LOG ERROR] {e}")

# ─── Annotate Frame with Emergency Warning ──────────────────
def annotate_emergency_frame(frame, lane_name):
    """
    Draws a red emergency warning banner on the camera frame.
    This appears on the live camera feed in the dashboard.
    """
    if frame is None:
        return frame

    if emergency_state[lane_name]["active"]:
        # Draw red rectangle at top of frame
        cv2.rectangle(frame, (0, 0), (frame.shape[1], 50), (0, 0, 255), -1)
        # Write emergency text on frame
        cv2.putText(frame, "🚨 EMERGENCY - GREEN CORRIDOR ACTIVE",
                    (10, 35), cv2.FONT_HERSHEY_SIMPLEX,
                    0.8, (255, 255, 255), 2)

    return frame