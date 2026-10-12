# app/auth/ui_routes.py
# UI routes for /login and /register pages
# Also handles email/password login for demo purposes

from app.auth.google_auth import auth_bp
from flask import render_template, request, session, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user
from app.extensions import db

# ─── Login Page ───────────────────────────────────────────────
@auth_bp.route("/login", methods=["GET", "POST"])
def login_page():
    """
    GET  → shows login page
    POST → handles email/password login form submission
    """
    # If already logged in redirect to correct dashboard
    if current_user.is_authenticated:
        if current_user.role == "admin":
            return redirect(url_for("admin_bp.dashboard"))
        return redirect(url_for("user_bp.dashboard"))

    # Handle email/password login form submission
    if request.method == "POST":
        email    = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        if not email or not password:
            flash("Please enter both email and password.", "danger")
            return render_template("auth/login.html", reason="")

        # Find user by email
        from models.user_model import User
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            # Check if user is trying correct portal
            portal = request.form.get("portal", "user")
            if portal == "admin" and user.role != "admin":
                flash("This account does not have Admin access. Please use User Portal.", "danger")
                return render_template("auth/login.html", reason="")
            if portal == "user" and user.role == "admin":
                flash("Admin accounts must use the Admin Portal.", "warning")
                return render_template("auth/login.html", reason="")
            login_user(user)
            user.last_login = db.func.now()
            db.session.commit()

            flash(f"Welcome back, {user.full_name}!", "success")

            # Redirect based on role
            if user.role == "admin":
                return redirect(url_for("admin_bp.dashboard"))
            return redirect(url_for("user_bp.dashboard"))
        else:
            flash("Invalid email or password. Try again.", "danger")
            return render_template("auth/login.html", reason="")

    # GET request - just show login page
    reason = request.args.get("reason", "")
    return render_template("auth/login.html", reason=reason)

# ─── Register Page ────────────────────────────────────────────
@auth_bp.route("/register", methods=["GET", "POST"])
def register_page():
    """
    GET  → shows register page
    POST → creates new user account
    """
    if current_user.is_authenticated:
        return redirect(url_for("user_bp.dashboard"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email     = request.form.get("email", "").strip()
        phone     = request.form.get("phone_number", "").strip()
        password  = request.form.get("password", "").strip()

        if not full_name or not email or not password:
            flash("Please fill all required fields.", "danger")
            return render_template("auth/register.html",
                                   google_name="", google_email="")

        # Check if email already exists
        from models.user_model import User
        existing = User.query.filter_by(email=email).first()
        if existing:
            flash("Email already registered. Please login.", "warning")
            return redirect(url_for("auth.login_page"))

        # Create new user
        user = User(
            full_name    = full_name,
            email        = email,
            phone_number = phone if phone else None,
            role         = "user",
            is_verified  = True,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        # Log them in immediately
        login_user(user)

        # Send registration confirmation email
        try:
            from modules.notification_service import (
                send_registration_confirmation
            )
            send_registration_confirmation(
                driver_name = full_name,
                email       = email,
                phone       = phone if phone else None,
                plate       = "",
            )
        except Exception as e:
            print(f"[AUTH] Email error: {e}")

        flash(f"Welcome to I-STE, {full_name}! "
              f"Check your email for confirmation.", "success")
        return redirect(url_for("user_bp.dashboard"))

    # GET - show register page
    google_name  = session.pop("google_register_name",  "")
    google_email = session.pop("google_register_email", "")
    return render_template("auth/register.html",
                           google_name=google_name,
                           google_email=google_email)

# ─── Logout ───────────────────────────────────────────────────
@auth_bp.route("/logout")
def logout():
    """
    Logs out current user and redirects to login page.
    """
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login_page"))