# Beginner note: this file implements phone OTP using Twilio SMS.
# Beginner note: if Twilio is not configured, we print the OTP in the terminal for demo.

# We import os so we can read environment variables using the current app config.
import os

# We import time so we can generate expiry timestamps and rate-limit resend actions.
import time

# We import random so we can generate a 6-digit OTP code.
import random

# We import datetime for readable timestamps (mostly helpful for debugging).
from datetime import datetime

# We also import date/timedelta so we can create vehicle expiry dates.
from datetime import date, timedelta

# We import the Flask Blueprint that already exists in our auth system.
from app.auth.google_auth import auth_bp, get_admin_emails

# We import request to read POST data from the client (JSON or form data).
from flask import request

# We import jsonify so we can return JSON success/failure responses.
from flask import jsonify

# We import session so we can store OTP + expiry + attempts server-side for demo.
from flask import session

# We import current_app so we can access app config (Twilio keys, secret key, etc.).
from flask import current_app

# We import render_template to return our OTP verify HTML page.
from flask import render_template

# We import login_user so we can create a Flask-Login session after OTP is valid.
from flask_login import login_user

# We import User model to update `is_verified` and log the user in.
from models.user_model import User

# We import generate_password_hash so we can store password securely.
from werkzeug.security import generate_password_hash

# We import Vehicle model so we can create vehicle record during registration.
from models.vehicle_model import Vehicle

# We import document status helper so vehicle document_status matches expiry dates.
from models.database import calculate_document_status


# Helper: read Twilio config and decide whether Twilio is configured.
def twilio_is_configured():
    # We read account SID from Flask config (or environment).
    account_sid = current_app.config.get("TWILIO_ACCOUNT_SID")
    # We read auth token from Flask config (or environment).
    auth_token = current_app.config.get("TWILIO_AUTH_TOKEN")
    # We read the "from" phone number used by Twilio to send SMS.
    from_phone = current_app.config.get("TWILIO_PHONE_NUMBER")

    # If any required Twilio setting is missing, we treat Twilio as not configured.
    return bool(account_sid and auth_token and from_phone)


# Helper: send the SMS using Twilio (or print OTP to terminal if Twilio is missing).
def send_otp_sms(to_phone: str, otp_code: str, expiry_ts: int):
    # We build a message string that includes OTP and expiry time.
    message_body = f"Your I-STE OTP is {otp_code}. It expires in 5 minutes."

    # If Twilio is configured, we try to send the SMS through Twilio.
    if twilio_is_configured():
        # We import Twilio Client only when needed (this avoids import-time crashes).
        from twilio.rest import Client  # type: ignore

        # Read Twilio credentials from config.
        account_sid = current_app.config.get("TWILIO_ACCOUNT_SID")
        auth_token = current_app.config.get("TWILIO_AUTH_TOKEN")
        from_phone = current_app.config.get("TWILIO_PHONE_NUMBER")

        # Create Twilio client instance.
        client = Client(account_sid, auth_token)

        # Send SMS using Twilio messages API.
        client.messages.create(
            # The phone number to send FROM.
            from_=from_phone,
            # The phone number to send TO.
            to=to_phone,
            # The actual SMS message body.
            body=message_body,
        )

        # Return True to indicate SMS was sent successfully.
        return True

    # Twilio is not configured: print OTP to terminal for demo.
    readable_expiry = datetime.fromtimestamp(expiry_ts).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[DEMO OTP] Sending OTP to {to_phone}. OTP={otp_code}. Expires at {readable_expiry}")

    # Return False to indicate we did not send SMS (but we still printed OTP).
    return False


# Helper: normalize phone numbers slightly for consistent matching in session.
def normalize_phone(phone_number: str) -> str:
    # We remove spaces because users often type phone numbers with spaces.
    cleaned = phone_number.replace(" ", "")

    # We keep the rest as-is (including leading +) because Twilio expects E.164 format.
    return cleaned


# POST route: send OTP to user phone number.
@auth_bp.route("/auth/send-otp", methods=["POST"])
def send_otp():
    # We try to read JSON body first.
    data = request.get_json(silent=True) or {}

    # If JSON is empty, we allow reading from form fields as a fallback.
    phone_number = data.get("phone_number") or request.form.get("phone_number")

    # Validate input: phone number must exist.
    if not phone_number:
        return jsonify({"success": False, "error": "phone_number is required"}), 400

    # Normalize phone for consistent session storage.
    phone_number = normalize_phone(phone_number)

    # Rate-limit check variables.
    now_ts = int(time.time())  # Current time in seconds since epoch.
    otp_last_sent_ts = session.get("otp_last_sent_ts")  # Last time OTP was sent (if any).

    # If an OTP was sent recently, we stop resend for 60 seconds.
    if otp_last_sent_ts is not None and (now_ts - int(otp_last_sent_ts)) < 60:
        retry_after = 60 - (now_ts - int(otp_last_sent_ts))
        return (
            jsonify(
                {
                    "success": False,
                    "error": "OTP recently sent. Please wait before resending.",
                    "retry_after_seconds": retry_after,
                }
            ),
            429,
        )

    # Generate a 6-digit OTP as a string (leading zeros allowed).
    otp_code = str(random.randint(0, 999999)).zfill(6)

    # OTP expiry is 5 minutes (300 seconds) from now.
    expiry_ts = now_ts + 300

    # Store OTP data in session for later verification.
    session["otp_phone"] = phone_number
    session["otp_code"] = otp_code
    session["otp_expiry_ts"] = expiry_ts
    session["otp_attempts_used"] = 0
    session["otp_max_attempts"] = 3
    session["otp_last_sent_ts"] = now_ts

    # Attempt to send OTP (Twilio or demo print).
    send_ok = send_otp_sms(to_phone=phone_number, otp_code=otp_code, expiry_ts=expiry_ts)

    # Build success response for frontend.
    return (
        jsonify(
            {
                "success": True,
                "message": "OTP sent successfully." if send_ok else "OTP prepared for demo (printed in terminal).",
                "expiry_ts": expiry_ts,
                "expiry_seconds": 300,
                "attempts_max": 3,
            }
        ),
        200,
    )


# POST route: verify OTP entered by user.
@auth_bp.route("/auth/verify-otp", methods=["POST"])
def verify_otp():
    # We try to read JSON body first.
    data = request.get_json(silent=True) or {}

    # Read phone number and OTP from request.
    phone_number = data.get("phone_number") or request.form.get("phone_number")
    otp_entered = data.get("otp") or request.form.get("otp")

    # Read optional registration fields (sent by the register page).
    full_name = (data.get("full_name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    plate_number = (data.get("plate_number") or "").strip()

    # Validate phone number exists.
    if not phone_number:
        return jsonify({"success": False, "error": "phone_number is required"}), 400

    # Validate OTP exists.
    if not otp_entered:
        return jsonify({"success": False, "error": "otp is required"}), 400

    # Normalize phone number so session matching works correctly.
    phone_number = normalize_phone(phone_number)

    # Convert OTP input to string and strip spaces.
    otp_entered = str(otp_entered).strip()

    # Load OTP info from session.
    otp_phone = session.get("otp_phone")
    otp_code = session.get("otp_code")
    otp_expiry_ts = session.get("otp_expiry_ts")

    # If session has no OTP for this phone, ask user to resend.
    if not otp_phone or not otp_code or otp_expiry_ts is None or otp_phone != phone_number:
        return jsonify({"success": False, "error": "No OTP found. Please resend OTP."}), 400

    # Calculate current time.
    now_ts = int(time.time())

    # If OTP is expired, tell user to resend.
    if now_ts > int(otp_expiry_ts):
        return jsonify({"success": False, "error": "OTP expired. Please resend.", "expired": True}), 400

    # Read attempt counters.
    attempts_used = int(session.get("otp_attempts_used", 0))
    max_attempts = int(session.get("otp_max_attempts", 3))

    # Compute attempts remaining before checking code.
    attempts_remaining = max_attempts - attempts_used

    # If user already used all attempts, stop verification and ask resend.
    if attempts_remaining <= 0:
        return jsonify({"success": False, "error": "Max attempts reached. Please resend OTP.", "attempts_remaining": 0}), 400

    # Check whether entered OTP matches stored OTP.
    if otp_entered != otp_code:
        # Increase attempts used.
        attempts_used += 1
        session["otp_attempts_used"] = attempts_used

        # Recompute attempts remaining after wrong OTP.
        attempts_remaining = max_attempts - attempts_used

        # Return error with attempts remaining (max 3 behavior).
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Invalid OTP.",
                    "attempts_remaining": attempts_remaining,
                }
            ),
            400,
        )

    # OTP is correct: we fetch or create user and mark as verified.
    user = User.query.filter_by(phone_number=phone_number).first()

    # If user does not exist, we create it automatically using fields from the register page (if provided).
    if not user:
        # Admin auto-role: if email matches ADMIN_EMAILS, create user with role="admin".
        admin_emails = get_admin_emails()

        # If email was not provided, create a placeholder email so our `users.email` column stays valid.
        if not email:
            email = f"otp_{phone_number}@iste.local".replace("+", "").replace("@", "_at_")

        # Decide role based on email match in ADMIN_EMAILS.
        assigned_role = "admin" if email in admin_emails else "user"

        # Determine which full_name to save.
        if not full_name:
            full_name = "OTP User"

        # Determine google_id if we are coming from "Register with Google".
        google_id = session.get("google_register_google_id")

        # Profile picture URL can be saved for Google-based autofill.
        profile_picture_url = session.get("google_register_picture_url")

        # Hash the password if the user provided it.
        # (If user does not provide a password, we still create a placeholder hash.)
        password_hash = (
            generate_password_hash(password) if password else generate_password_hash("otp_placeholder_password")
        )

        # Create the new user row.
        user = User(
            full_name=full_name,
            email=email,
            phone_number=phone_number,
            password_hash=password_hash,
            role=assigned_role,
            google_id=google_id,
            is_verified=True,
            profile_picture_url=profile_picture_url,
            created_at=datetime.utcnow(),
            last_login=datetime.utcnow(),
        )

        # Save the new user to DB.
        from app.extensions import db as app_db  # We import db here to avoid circular imports.

        app_db.session.add(user)
        app_db.session.commit()

        # If user provided a vehicle plate, we create one Vehicle record too.
        if plate_number:
            # We avoid duplicate plate inserts because Vehicle.plate_number is unique.
            existing_vehicle = Vehicle.query.filter_by(plate_number=plate_number).first()

            if not existing_vehicle:
                # We set expiry dates in the future so demo users start with "All Valid".
                rc_expiry = date.today() + timedelta(days=365)
                insurance_expiry = date.today() + timedelta(days=365)
                puc_expiry = date.today() + timedelta(days=180)

                doc_status = calculate_document_status(rc_expiry, insurance_expiry, puc_expiry)

                vehicle = Vehicle(
                    owner_id=user.id,
                    plate_number=plate_number,
                    vehicle_type="car",
                    rc_expiry_date=rc_expiry,
                    insurance_expiry_date=insurance_expiry,
                    puc_expiry_date=puc_expiry,
                    registration_date=date.today() - timedelta(days=500),
                    is_flagged=(doc_status == "Expired"),
                    document_status=doc_status,
                )

                # Save vehicle record.
                app_db.session.add(vehicle)
                app_db.session.commit()

        # Clear Google autofill temporary data so it is not reused accidentally.
        session.pop("google_register_google_id", None)
        session.pop("google_register_picture_url", None)

    # Mark the user verified.
    user.is_verified = True

    # Update last login time.
    user.last_login = datetime.utcnow()

    # Commit verification update.
    from app.extensions import db as app_db  # We import db here for safe session commit.

    app_db.session.commit()

    # Create Flask-Login session for this user.
    login_user(user)

    # Decide redirect URL based on role (admin vs user).
    redirect_to = "/admin/dashboard" if user.role == "admin" else "/user/dashboard"

    # Return success response for frontend redirect.
    return jsonify({"success": True, "message": "OTP verified successfully.", "redirect": redirect_to}), 200


# POST route: resend a new OTP with 60-second rate limit.
@auth_bp.route("/auth/resend-otp", methods=["POST"])
def resend_otp():
    # We try to read JSON body first.
    data = request.get_json(silent=True) or {}

    # Read phone number from request.
    phone_number = data.get("phone_number") or request.form.get("phone_number")

    # Validate input.
    if not phone_number:
        return jsonify({"success": False, "error": "phone_number is required"}), 400

    # Normalize phone number.
    phone_number = normalize_phone(phone_number)

    # Current time in seconds.
    now_ts = int(time.time())

    # Get last time OTP was sent to apply rate limit.
    otp_last_sent_ts = session.get("otp_last_sent_ts")

    # If last sent happened less than 60 seconds ago, deny resend.
    if otp_last_sent_ts is not None and (now_ts - int(otp_last_sent_ts)) < 60:
        retry_after = 60 - (now_ts - int(otp_last_sent_ts))
        return jsonify({"success": False, "error": "Please wait before resending.", "retry_after_seconds": retry_after}), 429

    # Generate a new OTP.
    otp_code = str(random.randint(0, 999999)).zfill(6)

    # Compute expiry timestamp (5 minutes).
    expiry_ts = now_ts + 300

    # Update session OTP fields.
    session["otp_phone"] = phone_number
    session["otp_code"] = otp_code
    session["otp_expiry_ts"] = expiry_ts
    session["otp_attempts_used"] = 0
    session["otp_max_attempts"] = 3
    session["otp_last_sent_ts"] = now_ts

    # Send OTP (Twilio or demo print).
    send_ok = send_otp_sms(to_phone=phone_number, otp_code=otp_code, expiry_ts=expiry_ts)

    # Compute next resend timestamp for frontend.
    next_resend_ts = now_ts + 60

    # Return success response with timing info.
    return (
        jsonify(
            {
                "success": True,
                "message": "OTP resent successfully." if send_ok else "OTP resent (demo printed in terminal).",
                "expiry_ts": expiry_ts,
                "expiry_seconds": 300,
                "next_resend_ts": next_resend_ts,
                "attempts_max": 3,
            }
        ),
        200,
    )


# GET route: render the OTP verify page.
@auth_bp.route("/login/otp", methods=["GET"])
def otp_page():
    # Read stored phone from session so the UI knows which phone the OTP is for.
    phone_number = session.get("otp_phone", "")

    # Read expiry timestamp and compute seconds left.
    otp_expiry_ts = session.get("otp_expiry_ts")
    otp_expiry_ts_int = int(otp_expiry_ts) if otp_expiry_ts else 0

    # Current time so we can show countdown immediately.
    now_ts = int(time.time())

    # Seconds left for OTP countdown (never negative).
    seconds_left = max(0, otp_expiry_ts_int - now_ts)

    # Read last sent time for resend button cooldown.
    otp_last_sent_ts = session.get("otp_last_sent_ts")
    otp_last_sent_ts_int = int(otp_last_sent_ts) if otp_last_sent_ts else 0

    # Resend is allowed once 60 seconds have passed since last send.
    next_resend_ts = otp_last_sent_ts_int + 60

    # Compute seconds left until resend becomes allowed.
    resend_seconds_left = max(0, next_resend_ts - now_ts)

    # Render HTML template with initial timing values.
    return render_template(
        "otp_verify.html",
        phone_number=phone_number,
        otp_expiry_ts=otp_expiry_ts_int,
        seconds_left=seconds_left,
        resend_seconds_left=resend_seconds_left,
    )

