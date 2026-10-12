# app/user/routes.py
# This file handles all User dashboard pages
# Regular users (public) can access these routes
# Each route shows user-specific data only

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from app.extensions import db

# Import models
from models.user_model      import User
from models.vehicle_model   import Vehicle
from models.violation_model import Violation

# Create user blueprint
# All routes in this file will start with /user/
user_bp = Blueprint("user_bp", __name__)

# ─── User Access Check ────────────────────────────────────────
def user_required(f):
    """
    Makes sure only logged in users can access these pages.
    Redirects to login if not authenticated.
    """
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Please login to continue.", "warning")
            return redirect(url_for("auth_bp.login"))
        return f(*args, **kwargs)
    return decorated

# ─── User Overview Dashboard ──────────────────────────────────
@user_bp.route("/dashboard")
@login_required
def dashboard():
    """
    Main user dashboard page.
    Shows welcome message, alerts, vehicle summary,
    recent activity and live traffic congestion widget.
    """
    # Get all vehicles owned by this user
    my_vehicles = Vehicle.query.filter_by(
        owner_id=current_user.id
    ).all()

    # Get unpaid violations for user's vehicles
    my_plates = [v.plate_number for v in my_vehicles]

    unpaid_violations = Violation.query.filter(
        Violation.plate_number.in_(my_plates),
        Violation.is_paid == False
    ).all() if my_plates else []

    # Check for expiring documents (within 30 days)
    now  = datetime.utcnow()
    soon = now + timedelta(days=30)

    expiring_docs = []
    for vehicle in my_vehicles:
        if vehicle.insurance_expiry_date < soon:
            expiring_docs.append({
                "plate": vehicle.plate_number,
                "doc":   "Insurance",
                "expiry": vehicle.insurance_expiry_date,
            })
        if vehicle.puc_expiry_date < soon:
            expiring_docs.append({
                "plate": vehicle.plate_number,
                "doc":   "PUC",
                "expiry": vehicle.puc_expiry_date,
            })
        if vehicle.rc_expiry_date < soon:
            expiring_docs.append({
                "plate": vehicle.plate_number,
                "doc":   "RC",
                "expiry": vehicle.rc_expiry_date,
            })

    # Get recent activity (last 5 violations)
    recent_activity = Violation.query.filter(
        Violation.plate_number.in_(my_plates)
    ).order_by(
        Violation.timestamp.desc()
    ).limit(5).all() if my_plates else []

    # Get live traffic signal status
    from modules.signal_control import get_signal_status
    signal_status = get_signal_status()

    return render_template(
        "user/dashboard.html",
        my_vehicles       = my_vehicles,
        unpaid_violations = unpaid_violations,
        expiring_docs     = expiring_docs,
        recent_activity   = recent_activity,
        signal_status     = signal_status,
        now               = now,
    )

# ─── My Violations Page ───────────────────────────────────────
@user_bp.route("/my_violations")
@login_required
def my_violations():
    """
    Shows all violations for the logged-in user's vehicles only.
    User cannot see other people's violations.
    """
    # Get user's vehicle plates
    my_vehicles = Vehicle.query.filter_by(
        owner_id=current_user.id
    ).all()
    my_plates = [v.plate_number for v in my_vehicles]

    # Get filter from URL
    status = request.args.get("status", "all")

    # Query violations for user's plates only
    if my_plates:
        query = Violation.query.filter(
            Violation.plate_number.in_(my_plates)
        )
        # Apply paid/unpaid filter
        if status == "paid":
            query = query.filter_by(is_paid=True)
        elif status == "unpaid":
            query = query.filter_by(is_paid=False)

        my_violations_list = query.order_by(
            Violation.timestamp.desc()
        ).all()
    else:
        my_violations_list = []

    # Calculate totals
    total_fines  = sum(v.fine_amount for v in my_violations_list)
    unpaid_fines = sum(
        v.fine_amount for v in my_violations_list if not v.is_paid
    )

    return render_template(
        "user/my_violations.html",
        violations   = my_violations_list,
        total_fines  = total_fines,
        unpaid_fines = unpaid_fines,
        filter_status= status,
    )

# ─── Pay Fine Page ────────────────────────────────────────────
@user_bp.route("/pay_fine/<int:violation_id>")
@login_required
def pay_fine(violation_id):
    """
    Shows payment page for a specific violation fine.
    Simulated payment - no real gateway needed.
    """
    violation = Violation.query.get_or_404(violation_id)

    # Make sure this violation belongs to the current user
    my_vehicles = Vehicle.query.filter_by(
        owner_id=current_user.id
    ).all()
    my_plates = [v.plate_number for v in my_vehicles]

    if violation.plate_number not in my_plates:
        flash("You can only pay your own fines.", "danger")
        return redirect(url_for("user_bp.my_violations"))

    return render_template(
        "user/pay_fine.html",
        violation = violation,
    )

# ─── Process Payment ──────────────────────────────────────────
@user_bp.route("/pay_fine/<int:violation_id>/confirm", methods=["POST"])
@login_required
def confirm_payment(violation_id):
    """
    Processes the simulated payment.
    Marks violation as paid in database.
    Shows success screen with receipt.
    """
    violation = Violation.query.get_or_404(violation_id)

    # Get payment method from form
    payment_method = request.form.get("payment_method", "UPI")

    # Mark as paid
    violation.is_paid      = True
    violation.payment_date = datetime.utcnow()
    db.session.commit()

    # Generate fake receipt number
    import random
    receipt_number = f"ISTE{datetime.now().strftime('%Y%m%d')}{random.randint(1000,9999)}"
    # Send payment confirmation email
    try:
        from modules.notification_service import send_payment_confirmation
        send_payment_confirmation(
            driver_name    = current_user.full_name,
            email          = current_user.email,
            phone          = current_user.phone_number,
            plate          = violation.plate_number,
            fine_amount    = violation.fine_amount,
            receipt_number = receipt_number,
        )
        print(f"[PAYMENT] Confirmation email sent to {current_user.email}")
    except Exception as e:
        print(f"[PAYMENT] Email error: {e}")
    return render_template(
        "user/payment_success.html",
        violation      = violation,
        payment_method = payment_method,
        receipt_number = receipt_number,
        payment_time   = datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

# ─── My Documents Page ────────────────────────────────────────
@user_bp.route("/my_documents")
@login_required
def my_documents():
    """
    Shows document status for all user's vehicles.
    Color coded: Green=valid, Yellow=expiring, Red=expired.
    """
    my_vehicles = Vehicle.query.filter_by(
        owner_id=current_user.id
    ).all()

    now  = datetime.utcnow()
    soon = now + timedelta(days=30)

    return render_template(
        "user/my_documents.html",
        vehicles = my_vehicles,
        now      = now,
        soon     = soon,
    )

# ─── Add Vehicle ──────────────────────────────────────────────
@user_bp.route("/add_vehicle", methods=["POST"])
@login_required
def add_vehicle():
    """
    Adds a new vehicle to user's account.
    Receives vehicle details from form submission.
    """
    plate        = request.form.get("plate_number", "").upper().strip()
    vehicle_type = request.form.get("vehicle_type", "car")

    # Parse expiry dates from form
    try:
        rc_expiry  = datetime.strptime(
            request.form.get("rc_expiry"), "%Y-%m-%d"
        )
        ins_expiry = datetime.strptime(
            request.form.get("insurance_expiry"), "%Y-%m-%d"
        )
        puc_expiry = datetime.strptime(
            request.form.get("puc_expiry"), "%Y-%m-%d"
        )
    except Exception:
        flash("Invalid date format. Please use YYYY-MM-DD.", "danger")
        return redirect(url_for("user_bp.my_documents"))

    # Check if plate already exists
    existing = Vehicle.query.filter_by(plate_number=plate).first()
    if existing:
        flash(f"Vehicle {plate} is already registered.", "warning")
        return redirect(url_for("user_bp.my_documents"))

    # Create new vehicle
    vehicle = Vehicle(
        owner_id              = current_user.id,
        plate_number          = plate,
        vehicle_type          = vehicle_type,
        rc_expiry_date        = rc_expiry,
        insurance_expiry_date = ins_expiry,
        puc_expiry_date       = puc_expiry,
        is_flagged            = False,
    )
    db.session.add(vehicle)
    db.session.commit()

    flash(f"Vehicle {plate} added successfully!", "success")
    return redirect(url_for("user_bp.my_documents"))

# ─── Traffic Map Page ─────────────────────────────────────────
@user_bp.route("/traffic_map")
@login_required
def traffic_map():
    """
    Shows live traffic map with lane congestion levels.
    Uses Leaflet.js for interactive map display.
    Lane markers update every 10 seconds via JavaScript.
    """
    from modules.signal_control import get_signal_status
    signal_status = get_signal_status()

    return render_template(
        "user/traffic_map.html",
        signal_status = signal_status,
    )

# ─── Route Suggestion ─────────────────────────────────────────
@user_bp.route("/route_suggestion")
@login_required
def route_suggestion():
    """
    Gives simple route advice based on current lane congestion.
    Returns JSON with recommended lane and reason.
    """
    from modules.signal_control import get_signal_status
    from modules.vehicle_detector import get_latest_counts

    try:
        counts = get_latest_counts()
    except Exception:
        # If no live data use default
        counts = {
            "North": 5, "South": 3,
            "East": 8, "West": 2
        }

    # Find least congested lane
    best_lane  = min(counts, key=counts.get)
    best_count = counts[best_lane]

    # Build suggestion message
    if best_count <= 3:
        condition = "very clear"
    elif best_count <= 7:
        condition = "moderate traffic"
    else:
        condition = "heavy traffic"

    suggestion = {
        "recommended_lane": best_lane,
        "vehicle_count":    best_count,
        "condition":        condition,
        "message": f"Take {best_lane} route - {condition} with only {best_count} vehicles detected.",
        "all_counts":       counts,
    }

    return jsonify(suggestion)

# ─── Vehicle Registration Page ────────────────────────────────
@user_bp.route("/register_vehicle", methods=["GET", "POST"])
@login_required
def register_vehicle():
    """
    GET  → Shows multi-step vehicle registration form
    POST → Processes registration with document uploads
    """
    import os
    from werkzeug.utils import secure_filename
    from datetime import datetime

    UPLOAD_FOLDER   = "app/static/uploads/documents"
    ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}

    def allowed_file(filename):
        return ('.' in filename and
                filename.rsplit('.', 1)[1].lower()
                in ALLOWED_EXTENSIONS)

    def save_file(file, prefix):
        """Saves uploaded file and returns path."""
        if file and file.filename and allowed_file(file.filename):
            filename  = secure_filename(file.filename)
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            filename  = f"{prefix}_{timestamp}_{filename}"
            filepath  = os.path.join(UPLOAD_FOLDER, filename)
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            file.save(filepath)
            return filepath
        return None

    if request.method == "POST":
        # ── Get all form fields ───────────────────────────
        plate = request.form.get("plate_number","").upper().strip()
        plate = plate.replace(" ","")

        # Check if plate already registered
        existing = Vehicle.query.filter_by(
            plate_number=plate
        ).first()
        if existing:
            flash(f"Vehicle {plate} is already registered.", "danger")
            return redirect(url_for("user_bp.register_vehicle"))


        # ── Validate document uploads ─────────────────────
        rc_file  = request.files.get("rc_document")
        ins_file = request.files.get("insurance_document")
        puc_file = request.files.get("puc_document")
        lic_file = request.files.get("license_document")

        missing_docs = []
        if not rc_file  or not rc_file.filename:
            missing_docs.append("RC Book")
        if not ins_file or not ins_file.filename:
            missing_docs.append("Insurance Policy")
        if not puc_file or not puc_file.filename:
            missing_docs.append("PUC Certificate")
        if not lic_file or not lic_file.filename:
            missing_docs.append("Driving License")

        if missing_docs:
            flash(
                f"❌ Missing documents: "
                f"{', '.join(missing_docs)}. "
                f"All documents are mandatory.",
                "danger"
            )
            return redirect(url_for("user_bp.register_vehicle"))   

        # ── Parse dates ───────────────────────────────────
        try:
            rc_expiry  = datetime.strptime(
                request.form.get("rc_expiry"), "%Y-%m-%d"
            )
            ins_expiry = datetime.strptime(
                request.form.get("insurance_expiry"), "%Y-%m-%d"
            )
            puc_expiry = datetime.strptime(
                request.form.get("puc_expiry"), "%Y-%m-%d"
            )
            lic_expiry = datetime.strptime(
                request.form.get("license_expiry"), "%Y-%m-%d"
            )
        except Exception:
            flash("Invalid date format.", "danger")
            return redirect(url_for("user_bp.register_vehicle"))

        # ── Save uploaded documents ───────────────────────
        rc_path  = save_file(
            request.files.get("rc_document"),  "rc"
        )
        ins_path = save_file(
            request.files.get("insurance_document"), "ins"
        )
        puc_path = save_file(
            request.files.get("puc_document"), "puc"
        )
        lic_path = save_file(
            request.files.get("license_document"), "lic"
        )

        # ── Create vehicle record ─────────────────────────
        vehicle = Vehicle(
            owner_id              = current_user.id,
            plate_number          = plate,
            vehicle_type          = request.form.get("vehicle_type","car"),
            vehicle_make          = request.form.get("vehicle_make",""),
            vehicle_model         = request.form.get("vehicle_model",""),
            vehicle_color         = request.form.get("vehicle_color",""),
            engine_number         = request.form.get("engine_number",""),
            chassis_number        = request.form.get("chassis_number",""),
            year_of_mfg           = request.form.get("year_of_mfg") or None,
            fuel_type             = request.form.get("fuel_type","Petrol"),
            license_number        = request.form.get("license_number",""),
            license_expiry        = lic_expiry,
            rc_expiry_date        = rc_expiry,
            insurance_expiry_date = ins_expiry,
            puc_expiry_date       = puc_expiry,
            rc_document_path      = rc_path or "",
            insurance_document_path= ins_path or "",
            puc_document_path     = puc_path or "",
            license_document_path = lic_path or "",
            address               = request.form.get("address",""),
            city                  = request.form.get("city",""),
            state                 = request.form.get("state",""),
            pincode               = request.form.get("pincode",""),
            registration_status   = "Pending",
        )
        db.session.add(vehicle)
        db.session.commit()

        # ── Send confirmation email ───────────────────────
        try:
            from modules.notification_service import send_email
            send_email(
                current_user.email,
                f"✅ Vehicle Registration Received - {plate}",
                f"""
                <div style="font-family:Arial; max-width:600px; margin:0 auto;">
                    <div style="background:#1a5276; padding:24px; text-align:center;">
                        <h2 style="color:#fff; margin:0;">🚗 Registration Received!</h2>
                    </div>
                    <div style="padding:30px; background:#f8f9fa;">
                        <p>Dear <strong>{current_user.full_name}</strong>,</p>
                        <p>Your vehicle registration for
                           <strong style="color:#e74c3c;">{plate}</strong>
                           has been received successfully.</p>
                        <p><strong>Status:</strong> Pending Verification</p>
                        <p>Your documents will be verified within
                           <strong>2-3 working days</strong>.
                           You will receive an email once approved.</p>
                        <p>You can track your registration status at
                           <a href="http://localhost:5000/user/my_documents">
                           My Documents</a>.</p>
                    </div>
                </div>
                """
            )
        except Exception as e:
            print(f"[REG] Email error: {e}")

        flash(
            f"✅ Vehicle {plate} registered successfully! "
            f"Verification will be completed in 2-3 working days.",
            "success"
        )
        return redirect(url_for("user_bp.my_documents"))

    # GET → show registration form
    return render_template("user/register_vehicle.html") 