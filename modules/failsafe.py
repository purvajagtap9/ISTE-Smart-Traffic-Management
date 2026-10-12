# failsafe.py
# This module cross-verifies camera and ultrasonic sensor readings
# If readings don't match, it flags a fault and uses safe values
# All faults are logged to fault_log.txt and simulated cloud upload

import random
import os
from datetime import datetime

# ─── Configuration ───────────────────────────────────────────
# If difference between camera and sensor is more than this % → fault
MISMATCH_THRESHOLD = 0.30  # 30%

# File to save fault logs
FAULT_LOG = "fault_log.txt"

# ─── Simulate Ultrasonic Sensor Reading ──────────────────────
def get_ultrasonic_reading(lane_name, camera_count):
    """
    Simulates an ultrasonic sensor reading for a lane.
    In real hardware, this would read from actual sensor.
    For simulation, we generate a value close to camera count
    but occasionally with a big difference to test failsafe.
    lane_name: name of the lane
    camera_count: vehicle count from camera/YOLO detection
    Returns: simulated sensor vehicle count (integer)
    """
    # 85% of the time sensor reading is close to camera
    # 15% of the time we simulate a faulty sensor reading
    if random.random() < 0.85:
        # Normal reading: within ±2 vehicles of camera count
        variation = random.randint(-2, 2)
        sensor_count = max(0, camera_count + variation)
    else:
        # Faulty reading: very different from camera count
        sensor_count = random.randint(0, 20)

    return sensor_count

# ─── Check for Mismatch ───────────────────────────────────────
def check_mismatch(camera_count, sensor_count):
    """
    Compares camera count and sensor count.
    Returns True if difference is more than MISMATCH_THRESHOLD.
    camera_count: vehicles detected by camera/YOLO
    sensor_count: vehicles detected by ultrasonic sensor
    """
    # Avoid division by zero
    if camera_count == 0 and sensor_count == 0:
        return False

    # Use the larger value as denominator for percentage calculation
    max_count = max(camera_count, sensor_count)

    # Calculate percentage difference
    difference = abs(camera_count - sensor_count)
    percentage  = difference / max_count

    # Return True if difference exceeds threshold
    return percentage > MISMATCH_THRESHOLD

# ─── Get Safe Vehicle Count ───────────────────────────────────
def get_safe_count(camera_count, sensor_count):
    """
    When mismatch is detected, returns the safer (higher) value.
    Using higher count is safer because:
    - Better to allocate more green time than needed
    - Prevents traffic buildup if one sensor is wrong
    camera_count: vehicles detected by camera
    sensor_count: vehicles detected by ultrasonic sensor
    Returns: safe vehicle count to use
    """
    return max(camera_count, sensor_count)

# ─── Log Fault to File ────────────────────────────────────────
def log_fault(lane_name, camera_count, sensor_count, safe_count):
    """
    Saves fault details to fault_log.txt
    Each line contains timestamp, lane, and both sensor readings.
    """
    try:
        # Open in append mode to keep all previous logs
        with open(FAULT_LOG, "a") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(
                f"{timestamp} | Lane: {lane_name} | "
                f"Camera: {camera_count} | "
                f"Ultrasonic: {sensor_count} | "
                f"Safe Count Used: {safe_count}\n"
            )
    except Exception as e:
        print(f"[FAILSAFE] Error writing fault log: {e}")

# ─── Simulate Cloud Upload ────────────────────────────────────
def upload_to_cloud(lane_name, fault_data):
    """
    Simulates uploading fault data to cloud server.
    In real system this would use an API call.
    For simulation, we just print the upload message.
    """
    print(f"[CLOUD] Uploading fault log for {lane_name} lane...")
    print(f"[CLOUD] Data: {fault_data}")
    print(f"[CLOUD] ✅ Upload successful (simulated)")

# ─── Run Failsafe Check for One Lane ─────────────────────────
def run_failsafe_check(lane_name, camera_count):
    """
    Runs complete failsafe check for a single lane.
    1. Gets ultrasonic sensor reading
    2. Compares with camera reading
    3. If mismatch → logs fault, uses safe count
    4. Returns final verified vehicle count

    lane_name: name of the lane to check
    camera_count: vehicle count from camera detection
    Returns: dictionary with check results
    """
    # Get simulated ultrasonic reading
    sensor_count = get_ultrasonic_reading(lane_name, camera_count)

    # Check if readings match
    mismatch = check_mismatch(camera_count, sensor_count)

    if mismatch:
        # Get safe count to use
        safe_count = get_safe_count(camera_count, sensor_count)

        # Print warning
        print(f"\n⚠️  [FAILSAFE] Mismatch detected on {lane_name} lane!")
        print(f"   Camera count    : {camera_count}")
        print(f"   Ultrasonic count: {sensor_count}")
        print(f"   Using safe count: {safe_count}\n")

        # Log the fault
        log_fault(lane_name, camera_count, sensor_count, safe_count)

        # Prepare fault data for cloud upload
        fault_data = {
            "lane":          lane_name,
            "camera_count":  camera_count,
            "sensor_count":  sensor_count,
            "safe_count":    safe_count,
            "timestamp":     datetime.now().isoformat(),
        }

        # Simulate cloud upload
        upload_to_cloud(lane_name, fault_data)

        return {
            "lane":          lane_name,
            "camera_count":  camera_count,
            "sensor_count":  sensor_count,
            "safe_count":    safe_count,
            "mismatch":      True,
            "status":        "FAULT DETECTED - Safe override applied",
        }

    else:
        # No mismatch - readings are consistent
        return {
            "lane":          lane_name,
            "camera_count":  camera_count,
            "sensor_count":  sensor_count,
            "safe_count":    camera_count,
            "mismatch":      False,
            "status":        "OK - Sensors consistent",
        }

# ─── Run Failsafe for All Lanes ───────────────────────────────
def run_all_lanes_failsafe(detection_results):
    """
    Runs failsafe check on all 4 lanes at once.
    detection_results: dictionary from vehicle_detector.py
    Returns: dictionary with verified counts for all lanes
    """
    verified_results = {}

    for lane_name, results in detection_results.items():
        # Get camera vehicle count
        camera_count = results.get("vehicle_count", 0)

        # Run failsafe check for this lane
        check = run_failsafe_check(lane_name, camera_count)

        # Use verified safe count going forward
        verified_results[lane_name] = {
            "vehicle_count": check["safe_count"],
            "density":       results.get("density", "Low"),
            "mismatch":      check["mismatch"],
            "status":        check["status"],
        }

    return verified_results

# ─── Get Fault Count ──────────────────────────────────────────
def get_fault_count():
    """
    Returns total number of faults logged so far.
    Used by analytics module and admin dashboard.
    """
    if not os.path.exists(FAULT_LOG):
        return 0

    try:
        with open(FAULT_LOG, "r") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
            return len(lines)
    except Exception:
        return 0

# ─── Get Recent Faults ────────────────────────────────────────
def get_recent_faults(limit=10):
    """
    Returns the most recent fault log entries.
    limit: how many recent entries to return
    Used by admin dashboard system log section.
    """
    if not os.path.exists(FAULT_LOG):
        return []

    try:
        with open(FAULT_LOG, "r") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
            # Return last 'limit' lines
            return lines[-limit:]
    except Exception:
        return []