# violation_detector.py
# Detects traffic violations from camera frames
# Types: signal violation, speed violation, document violation
# Logs violations to database and sends notifications

import cv2
import os
import csv
import random
import numpy as np
from datetime import datetime

# ─── Configuration ────────────────────────────────────────────
SPEED_LIMIT        = 40    # km/h
STOP_LINE_POSITION = 0.70  # 70% of frame height
SNAPSHOT_DIR       = "violations_snapshots"
VIOLATIONS_CSV     = "violations_log.csv"

# Fine amounts in Rupees
FINES = {
    "speeding":  500,
    "signal":    1000,
    "document":  1000,
}

# ─── Ensure snapshot directory exists ────────────────────────
os.makedirs(SNAPSHOT_DIR, exist_ok=True)

# ─── Initialize CSV ──────────────────────────────────────────
def init_csv():
    """Creates violations CSV with headers if it doesn't exist."""
    if not os.path.exists(VIOLATIONS_CSV):
        with open(VIOLATIONS_CSV, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp", "lane", "plate_number",
                "violation_type", "fine_amount",
                "is_paid", "snapshot_path", "speed"
            ])

init_csv()

# ─── Save Violation Snapshot ─────────────────────────────────
def save_snapshot(frame, lane, plate, violation_type):
    """
    Saves a snapshot of the violation frame.
    Returns the file path of saved image.
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename  = f"{violation_type}_{lane}_{plate}_{timestamp}.jpg"
        filepath  = os.path.join(SNAPSHOT_DIR, filename)
        cv2.imwrite(filepath, frame)
        return filepath
    except Exception as e:
        print(f"[VIOLATION] Snapshot error: {e}")
        return ""

# ─── Log Violation to CSV ─────────────────────────────────────
def log_to_csv(lane, plate, violation_type,
               fine_amount, snapshot_path, speed=None):
    """Appends violation record to violations_log.csv."""
    try:
        with open(VIOLATIONS_CSV, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                lane, plate, violation_type,
                fine_amount, False,
                snapshot_path, speed or ""
            ])
    except Exception as e:
        print(f"[VIOLATION] CSV log error: {e}")

# ─── Save Violation to Database ───────────────────────────────
def save_to_database(lane, plate, violation_type,
                     fine_amount, snapshot_path, speed=None):
    """
    Saves violation to SQLite database.
    Also triggers notification to vehicle owner.
    """
    try:
        from app import create_app
        from app.extensions import db
        from models.violation_model import Violation
        from models.vehicle_model   import Vehicle
        from models.user_model      import User

        app = create_app()
        with app.app_context():
            # Create violation record
            violation = Violation(
                plate_number   = plate,
                lane_name      = lane,
                violation_type = violation_type,
                detected_speed = speed,
                speed_limit    = SPEED_LIMIT,
                fine_amount    = fine_amount,
                is_paid        = False,
                snapshot_path  = snapshot_path,
                notified       = False,
                timestamp      = datetime.utcnow(),
            )
            db.session.add(violation)
            db.session.commit()

            # Find vehicle owner and send notification
            vehicle = Vehicle.query.filter_by(
                plate_number=plate
            ).first()

            if vehicle:
                owner = User.query.get(vehicle.owner_id)
                if owner and not violation.notified:
                    try:
                        from modules.notification_service import (
                            send_violation_alert
                        )
                        send_violation_alert(
                            driver_name    = owner.full_name,
                            email          = owner.email,
                            phone          = owner.phone_number,
                            plate          = plate,
                            violation_type = violation_type,
                            fine_amount    = fine_amount,
                            lane           = lane,
                            timestamp      = datetime.utcnow(),
                        )
                        violation.notified = True
                        db.session.commit()
                    except Exception as e:
                        print(f"[VIOLATION] Notification error: {e}")

            print(f"[VIOLATION] ✅ Saved: {plate} | "
                  f"{violation_type} | ₹{fine_amount}")

    except Exception as e:
        print(f"[VIOLATION] DB error: {e}")

# ─── Record Full Violation ────────────────────────────────────
def record_violation(frame, lane, plate, violation_type, speed=None):
    """
    Complete violation recording pipeline:
    1. Save snapshot
    2. Log to CSV
    3. Save to database
    4. Send notification
    5. Print alert
    """
    fine_amount = FINES.get(violation_type, 500)

    # Save snapshot
    snapshot_path = ""
    if frame is not None:
        snapshot_path = save_snapshot(
            frame, lane, plate, violation_type
        )

    # Log to CSV
    log_to_csv(lane, plate, violation_type,
               fine_amount, snapshot_path, speed)

    # Save to DB + notify
    save_to_database(lane, plate, violation_type,
                     fine_amount, snapshot_path, speed)

    # Print alert
    print(f"\n⚠️  [VIOLATION DETECTED]")
    print(f"   Lane      : {lane}")
    print(f"   Plate     : {plate}")
    print(f"   Type      : {violation_type.upper()}")
    print(f"   Fine      : ₹{fine_amount}")
    if speed:
        print(f"   Speed     : {speed} km/h")
    print(f"   Time      : {datetime.now().strftime('%H:%M:%S')}\n")

# ─── Signal Violation Detection ───────────────────────────────
def check_signal_violation(frame, lane, boxes, plates, signal_color):
    """
    Detects if any vehicle crossed the stop line on RED.
    Uses virtual stop line at STOP_LINE_POSITION of frame height.
    """
    if signal_color != "RED" or frame is None:
        return False

    height = frame.shape[0]
    stop_line_y = int(height * STOP_LINE_POSITION)

    # Draw stop line on frame (for visualization)
    cv2.line(
        frame,
        (0, stop_line_y),
        (frame.shape[1], stop_line_y),
        (0, 0, 255), 2
    )
    cv2.putText(
        frame, "STOP LINE",
        (10, stop_line_y - 8),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5, (0, 0, 255), 1
    )

    violation_detected = False

    for i, box in enumerate(boxes):
        x, y, w, h = box
        vehicle_bottom = y + h

        # Vehicle crossed stop line on RED
        if vehicle_bottom > stop_line_y:
            plate = plates[i] if i < len(plates) else None
            if not plate:
                from modules.anpr import generate_fake_plate
                plate = generate_fake_plate()

            # Record violation
            record_violation(
                frame, lane, plate, "signal"
            )
            violation_detected = True

            # Draw violation highlight
            cv2.rectangle(
                frame,
                (x, y), (x+w, y+h),
                (0, 0, 255), 3
            )
            cv2.putText(
                frame, "VIOLATION!",
                (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7, (0, 0, 255), 2
            )

    return violation_detected

# ─── Speed Violation Detection ────────────────────────────────
def check_speed_violation(lane, plate, speed):
    """
    Checks if detected speed exceeds speed limit.
    Records violation if over limit.
    """
    if speed and speed > SPEED_LIMIT:
        record_violation(
            None, lane, plate, "speeding", speed
        )
        return True
    return False

# ─── Check All Violations in Frame ───────────────────────────
def check_frame_violations(frame, lane, boxes, plates, signal_color):
    """
    Runs all violation checks for a single frame.
    Called from detection_engine.py every 2 seconds.
    """
    # Signal violation check
    check_signal_violation(frame, lane, boxes, plates, signal_color)

    # Speed check (simulated speed for now)
    for i, plate in enumerate(plates):
        simulated_speed = random.randint(20, 80)
        check_speed_violation(lane, plate, simulated_speed)

# ─── Check All Violations Across Lanes ───────────────────────
def check_violations_all_lanes(frames, signal_status):
    """
    Runs violation detection across all lanes simultaneously.
    Called from main detection loop.
    """
    from modules.detection_engine import detection_state, state_lock

    for lane in ["North","South","East","West"]:
        frame = frames.get(lane)
        if frame is None:
            continue

        with state_lock:
            signal_color = detection_state[lane].get("signal","RED")
            plates       = detection_state[lane].get(
                "plates_detected", []
            )

        # Get boxes from latest detection
        from modules.vehicle_detector import latest_results
        boxes = latest_results.get(lane, {}).get("boxes", [])

        check_frame_violations(
            frame, lane, boxes, plates, signal_color
        )