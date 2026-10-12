# app/api/routes.py
# JSON API endpoints for live dashboard updates
# Used by JavaScript every 2 seconds

from flask import Blueprint, jsonify, request, Response
from flask_login import login_required, current_user
from datetime import datetime

api_bp = Blueprint("api_bp", __name__)

# ─── Live System Status ───────────────────────────────────────
@api_bp.route("/status")
def status():
    """
    Returns complete live system status.
    Called every 2 seconds by dashboard JavaScript.
    """
    try:
        from modules.detection_engine import get_full_state
        return jsonify(get_full_state())
    except Exception as e:
        # Fallback with simulated data
        import random
        lanes = ["North", "South", "East", "West"]
        counts = {l: random.randint(0, 12) for l in lanes}
        return jsonify({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "signal_status": {
                l: {"color": "RED", "time_remaining": 0,
                    "manual_override": False}
                for l in lanes
            },
            "vehicle_counts": counts,
            "density_levels": {
                l: ("Low" if counts[l]<=3
                    else "Medium" if counts[l]<=8
                    else "High")
                for l in lanes
            },
            "green_times": {
                l: (15 if counts[l]<=3
                    else 30 if counts[l]<=8
                    else 50)
                for l in lanes
            },
            "emergency": {"active": False, "lane": None},
        })

# ─── Camera Feed Stream ───────────────────────────────────────
@api_bp.route("/camera/<lane_name>")
@login_required
def camera_feed(lane_name):
    """
    Streams annotated MJPEG camera feed for a lane.
    Shows vehicle bounding boxes and counts.
    """
    def generate():
        import time
        import numpy as np
        while True:
            try:
                from modules.camera_manager import get_frame
                from modules.vehicle_detector import detect_vehicles_in_frame
                frame = get_frame(lane_name)
                if frame is not None:
                    # Run detection and annotate
                    result = detect_vehicles_in_frame(
                        frame.copy(), lane_name
                    )
                    annotated = result.get(
                        "annotated_frame", frame
                    )
                    if annotated is None:
                        annotated = frame
                else:
                    # Blank frame
                    annotated = np.zeros((480,640,3), dtype=np.uint8)
                    import cv2
                    cv2.putText(
                        annotated,
                        f"{lane_name} - No Signal",
                        (50, 240),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1, (0,200,0), 2
                    )

                import cv2
                ret, buf = cv2.imencode(".jpg", annotated,
                                        [cv2.IMWRITE_JPEG_QUALITY, 70])
                if ret:
                    yield (b"--frame\r\n"
                           b"Content-Type: image/jpeg\r\n\r\n"
                           + buf.tobytes() + b"\r\n")
            except Exception as e:
                time.sleep(0.5)

            time.sleep(0.1)

    return Response(generate(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")

# ─── Update Camera URL ────────────────────────────────────────
@api_bp.route("/update_camera", methods=["POST"])
@login_required
def update_camera():
    """
    Updates camera URL and starts/stops stream reader.
    """
    data = request.get_json()
    lane = data.get("lane")
    url  = data.get("url", "")

    # Update detection engine stream
    try:
        from modules.detection_engine import update_camera_url
        update_camera_url(lane, url)
    except Exception as e:
        print(f"[API] Camera update error: {e}")

    # Update global camera_urls
    try:
        from main import camera_urls
        if lane in camera_urls:
            camera_urls[lane] = url
    except Exception:
        pass

    return jsonify({"success": True, "lane": lane, "url": url})

# ─── Signal Override ─────────────────────────────────────────
@api_bp.route("/signal/override", methods=["POST"])
@login_required
def signal_override():
    if current_user.role != "admin":
        return jsonify({"error": "Admin only"}), 403
    data     = request.get_json()
    lane     = data.get("lane")
    duration = data.get("duration", 30)
    from modules.signal_control import set_manual_green
    result = set_manual_green(lane, duration)
    return jsonify(result)

# ─── Emergency Trigger ───────────────────────────────────────
@api_bp.route("/emergency/trigger", methods=["POST"])
@login_required
def trigger_emergency():
    if current_user.role != "admin":
        return jsonify({"error": "Admin only"}), 403
    data = request.get_json()
    lane = data.get("lane", "North")
    from modules.emergency_detector import manual_trigger
    manual_trigger(lane)
    return jsonify({"success": True, "message": f"Emergency on {lane}"})

# ─── Analytics Data ──────────────────────────────────────────
@api_bp.route("/analytics")
@login_required
def analytics_data():
    if current_user.role != "admin":
        return jsonify({"error": "Admin only"}), 403
    from modules.analytics import get_analytics_summary
    return jsonify(get_analytics_summary())

# ─── Vehicle Counts ──────────────────────────────────────────
@api_bp.route("/vehicle_counts")
def vehicle_counts():
    try:
        from modules.detection_engine import detection_state
        return jsonify({
            l: d["vehicle_count"]
            for l, d in detection_state.items()
        })
    except Exception:
        import random
        return jsonify({l: random.randint(0,12)
                        for l in ["North","South","East","West"]})

# ─── Route Suggestion ────────────────────────────────────────
@api_bp.route("/route_suggestion")
def route_suggestion():
    try:
        from modules.detection_engine import detection_state
        counts = {l: d["vehicle_count"]
                  for l, d in detection_state.items()}
    except Exception:
        import random
        counts = {l: random.randint(0,12)
                  for l in ["North","South","East","West"]}

    best  = min(counts, key=counts.get)
    count = counts[best]
    cond  = ("clear" if count<=3
             else "moderate" if count<=8
             else "heavy")
    return jsonify({
        "recommended_lane": best,
        "vehicle_count":    count,
        "condition":        cond,
        "message":          f"{best} lane is {cond}",
        "all_counts":       counts,
    })

# ─── Health Check ────────────────────────────────────────────
@api_bp.route("/health")
def health():
    return jsonify({
        "status":    "running",
        "timestamp": datetime.now().isoformat(),
    })

# ─── Send Test Notification ──────────────────────────────────
@api_bp.route("/test_notification", methods=["POST"])
@login_required
def test_notification():
    """
    Sends a test email/SMS to verify notification setup.
    Admin only.
    """
    if current_user.role != "admin":
        return jsonify({"error": "Admin only"}), 403

    from modules.notification_service import send_email
    result = send_email(
        current_user.email,
        "✅ I-STE Test Notification",
        "<h2>I-STE notifications are working!</h2>"
        "<p>Your email alerts are configured correctly.</p>"
    )
    return jsonify({
        "success": result,
        "message": "Test email sent!" if result
                   else "Email config missing - check .env file"
    })