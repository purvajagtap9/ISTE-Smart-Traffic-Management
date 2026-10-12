# app/admin/routes.py
# This file handles all Admin dashboard pages
# Only users with role="admin" can access these routes
# Each route renders a different admin page

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime

# Import models to query database
from models.user_model      import User
from models.vehicle_model   import Vehicle
from models.violation_model import Violation
from models.emergency_log_model import EmergencyLog
from app.extensions import db

# Import traffic modules
from modules.analytics        import get_analytics_summary
from modules.signal_control   import get_signal_status, set_manual_green, release_all_overrides
from modules.emergency_detector import manual_trigger, get_emergency_status, cancel_emergency
from modules.failsafe         import get_recent_faults

# Create admin blueprint
# All routes in this file will start with /admin/
admin_bp = Blueprint("admin_bp", __name__)

# ─── Admin Access Check ───────────────────────────────────────
def admin_required(f):
    """
    Decorator to protect admin routes.
    Redirects to login if user is not admin.
    """
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "admin":
            flash("Admin access required.", "danger")
            return redirect(url_for("auth_bp.login"))
        return f(*args, **kwargs)
    return decorated

# ─── Admin Overview Dashboard ─────────────────────────────────
@admin_bp.route("/dashboard")
@login_required
@admin_required
def dashboard():
    """
    Main admin overview page.
    Shows stats cards, signal status, recent violations.
    """
    # Get counts for stats cards
    total_users      = User.query.count()
    total_vehicles   = Vehicle.query.count()
    total_violations = Violation.query.count()
    unpaid_fines     = Violation.query.filter_by(is_paid=False).count()

    # Get recent violations (last 10)
    recent_violations = Violation.query.order_by(
        Violation.timestamp.desc()
    ).limit(10).all()

    # Get current signal status for all lanes
    signal_status = get_signal_status()

    # Get emergency status
    emergency_status = get_emergency_status()

    # Check if any emergency is active
    any_emergency = any(
        state["active"] for state in emergency_status.values()
    )

    return render_template(
        "admin/dashboard.html",
        total_users      = total_users,
        total_vehicles   = total_vehicles,
        total_violations = total_violations,
        unpaid_fines     = unpaid_fines,
        recent_violations= recent_violations,
        signal_status    = signal_status,
        emergency_status = emergency_status,
        any_emergency    = any_emergency,
        current_time     = datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

# ─── Live Camera Feeds ────────────────────────────────────────
@admin_bp.route("/cameras")
@login_required
@admin_required
def cameras():
    """
    Shows live camera feeds from all 4 lanes.
    Each feed streams from phone camera via IP Webcam.
    """
    # Import shared camera state from main controller
    try:
        from main import camera_urls, detection_results
    except Exception:
        camera_urls      = {}
        detection_results = {}

    signal_status = get_signal_status()

    return render_template(
        "admin/cameras.html",
        camera_urls      = camera_urls,
        detection_results= detection_results,
        signal_status    = signal_status,
    )

# ─── Signal Control Page ──────────────────────────────────────
@admin_bp.route("/signals")
@login_required
@admin_required
def signals():
    """
    Admin can manually control traffic signals here.
    Shows current signal state and allows overrides.
    """
    signal_status = get_signal_status()
    return render_template(
        "admin/signals.html",
        signal_status = signal_status,
    )

# ─── Manual Signal Override (API) ────────────────────────────
@admin_bp.route("/signals/override", methods=["POST"])
@login_required
@admin_required
def signal_override():
    lane     = request.form.get("lane")
    duration = int(request.form.get("duration", 30))

    result = set_manual_green(lane, duration)

    # Sync with detection engine
    try:
        from modules.detection_engine import detection_state, state_lock
        from modules.signal_control   import signal_state
        lanes = ["North","South","East","West"]
        with state_lock:
            for l in lanes:
                detection_state[l]["signal"]         = "RED"
                detection_state[l]["time_remaining"]  = 0
            detection_state[lane]["signal"]         = "GREEN"
            detection_state[lane]["time_remaining"]  = duration
            detection_state[lane]["green_time"]     = duration
        for l in lanes:
            signal_state[l]["color"]          = "RED"
            signal_state[l]["time_remaining"] = 0
        signal_state[lane]["color"]          = "GREEN"
        signal_state[lane]["time_remaining"] = duration
    except Exception as e:
        print(f"[OVERRIDE] {e}")

    return jsonify(result)

# ─── Release All Signal Overrides ────────────────────────────
@admin_bp.route("/signals/release", methods=["POST"])
@login_required
@admin_required
def signal_release():
    """
    Releases all manual overrides - returns to auto mode.
    """
    release_all_overrides()
    return jsonify({"success": True, "message": "Auto mode restored"})

# ─── Emergency Page ───────────────────────────────────────────
@admin_bp.route("/emergency")
@login_required
@admin_required
def emergency():
    """
    Emergency management page.
    Shows emergency history and manual trigger button.
    """
    emergency_status = get_emergency_status()

    # Read emergency log file
    emergency_logs = []
    try:
        with open("emergency_log.txt", "r") as f:
            lines = f.readlines()
            # Show last 20 entries
            emergency_logs = [l.strip() for l in lines[-20:] if l.strip()]
            emergency_logs.reverse()  # Most recent first
    except FileNotFoundError:
        emergency_logs = []

    return render_template(
        "admin/emergency.html",
        emergency_status = emergency_status,
        emergency_logs   = emergency_logs,
    )

# ─── Trigger Emergency (API) ──────────────────────────────────
@admin_bp.route("/emergency/trigger", methods=["POST"])
@login_required
@admin_required
def trigger_emergency():
    """
    Manually triggers emergency for a specific lane.
    Called when admin clicks the big red button.
    """
    lane = request.form.get("lane", "North")
    manual_trigger(lane)
    return jsonify({
        "success": True,
        "message": f"Emergency triggered for {lane} lane"
    })

# ─── Cancel Emergency (API) ───────────────────────────────────
@admin_bp.route("/emergency/cancel", methods=["POST"])
@login_required
@admin_required
def cancel_emergency_route():
    """
    Cancels active emergency and restores normal operation.
    """
    lane = request.form.get("lane", "North")
    cancel_emergency(lane)
    return jsonify({
        "success": True,
        "message": f"Emergency cancelled for {lane} lane"
    })

# ─── Violations Page ──────────────────────────────────────────
@admin_bp.route("/violations")
@login_required
@admin_required
def violations():
    """
    Shows all violations with filtering and pagination.
    Admin can mark fines as paid or send reminders.
    """
    # Get filter parameters from URL
    page           = request.args.get("page", 1, type=int)
    violation_type = request.args.get("type", "all")
    status         = request.args.get("status", "all")
    lane           = request.args.get("lane", "all")

    # Start with all violations query
    query = Violation.query

    # Apply filters if selected
    if violation_type != "all":
        query = query.filter_by(violation_type=violation_type)
    if status == "paid":
        query = query.filter_by(is_paid=True)
    elif status == "unpaid":
        query = query.filter_by(is_paid=False)
    if lane != "all":
        query = query.filter_by(lane_name=lane)

    # Order by newest first and paginate
    violations_page = query.order_by(
        Violation.timestamp.desc()
    ).paginate(page=page, per_page=10, error_out=False)

    # Summary counts
    total_fines    = db.session.query(
        db.func.sum(Violation.fine_amount)
    ).scalar() or 0
    pending_fines  = db.session.query(
        db.func.sum(Violation.fine_amount)
    ).filter_by(is_paid=False).scalar() or 0

    return render_template(
        "admin/violations.html",
        violations     = violations_page,
        total_fines    = total_fines,
        pending_fines  = pending_fines,
        filter_type    = violation_type,
        filter_status  = status,
        filter_lane    = lane,
    )

# ─── Mark Violation as Paid ───────────────────────────────────
@admin_bp.route("/violations/<int:violation_id>/pay", methods=["POST"])
@login_required
@admin_required
def mark_paid(violation_id):
    """
    Marks a specific violation fine as paid.
    """
    violation = Violation.query.get_or_404(violation_id)
    violation.is_paid     = True
    violation.payment_date = datetime.utcnow()
    db.session.commit()
    return jsonify({"success": True})

# ─── Analytics Page ───────────────────────────────────────────
@admin_bp.route("/analytics")
@login_required
@admin_required
def analytics():
    """
    Shows traffic analytics with charts.
    All chart data comes from analytics.py module.
    """
    # Get full analytics summary
    summary = get_analytics_summary()

    return render_template(
        "admin/analytics.html",
        summary = summary,
    )

# ─── Documents Page ───────────────────────────────────────────
@admin_bp.route("/documents")
@login_required
@admin_required
def documents():
    """
    Shows all vehicle document statuses.
    Highlights expired and expiring documents.
    """
    from datetime import timedelta

    vehicles = Vehicle.query.all()
    now      = datetime.utcnow()
    soon     = now + timedelta(days=30)  # Expiring within 30 days

    # Categorize vehicles by document status
    expired  = []
    expiring = []
    valid    = []

    for v in vehicles:
        # Check if any document is expired
        if (v.puc_expiry_date       < now or
            v.insurance_expiry_date < now or
            v.rc_expiry_date        < now):
            expired.append(v)
        # Check if any document expires within 30 days
        elif (v.puc_expiry_date       < soon or
              v.insurance_expiry_date < soon or
              v.rc_expiry_date        < soon):
            expiring.append(v)
        else:
            valid.append(v)

    return render_template(
        "admin/documents.html",
        expired  = expired,
        expiring = expiring,
        valid    = valid,
        now      = now,
    )

# ─── Users Management Page ────────────────────────────────────
@admin_bp.route("/users")
@login_required
@admin_required
def users():
    """
    Shows all registered users.
    Admin can change roles or suspend accounts.
    """
    all_users   = User.query.order_by(User.created_at.desc()).all()
    total_admins = User.query.filter_by(role="admin").count()
    total_users  = User.query.filter_by(role="user").count()

    return render_template(
        "admin/users.html",
        users        = all_users,
        total_admins = total_admins,
        total_users  = total_users,
    )

# ─── Change User Role ─────────────────────────────────────────
@admin_bp.route("/users/<int:user_id>/role", methods=["POST"])
@login_required
@admin_required
def change_role(user_id):
    """
    Changes a user's role between admin and user.
    """
    user     = User.query.get_or_404(user_id)
    new_role = request.form.get("role")

    if new_role in ["admin", "user"]:
        user.role = new_role
        db.session.commit()
        return jsonify({"success": True, "new_role": new_role})

    return jsonify({"error": "Invalid role"}), 400

# ─── Delete User ──────────────────────────────────────────────
@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    """
    Deletes a user account from the system.
    Cannot delete your own account.
    """
    # Prevent admin from deleting themselves
    if user_id == current_user.id:
        return jsonify({"error": "Cannot delete your own account"}), 400

    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return jsonify({"success": True})