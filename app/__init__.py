# app/__init__.py
# This is the main Flask application factory
# It initializes all extensions, registers all blueprints
# and sets up the complete I-STE web application

import os
from flask import Flask, redirect, url_for, jsonify
from flask_login import LoginManager
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ─── Import Extensions ───────────────────────────────────────
# Extensions are initialized in extensions.py to avoid
# circular imports (a common Flask beginner problem)
from app.extensions import db, login_manager

# ─── Import All Models ───────────────────────────────────────
# Models must be imported here so Flask-SQLAlchemy
# knows about all tables before creating the database
from models.user_model      import User
from models.vehicle_model   import Vehicle
from models.violation_model import Violation
from models.emergency_log_model import EmergencyLog
from models.system_log_model    import SystemLog

# ─── Application Factory Function ───────────────────────────
def create_app():
    """
    Creates and configures the Flask application.
    Using a factory function is best practice in Flask.
    It allows creating multiple app instances (useful for testing).
    """

    # Create Flask app instance
    # __name__ tells Flask where to look for templates and static files
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static"
    )

    # ── Load Configuration ────────────────────────────────────
    app.config["SECRET_KEY"] = os.getenv(
        "SECRET_KEY", "iste-secret-key-change-in-production"
    )

    # SQLite database file location
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL", "sqlite:///iste.db"
    )

    # Disable modification tracking (saves memory)
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Google OAuth credentials from .env file
    app.config["GOOGLE_CLIENT_ID"]     = os.getenv("GOOGLE_CLIENT_ID", "")
    app.config["GOOGLE_CLIENT_SECRET"] = os.getenv("GOOGLE_CLIENT_SECRET", "")

    # ── Initialize Extensions with App ────────────────────────
    # This connects SQLAlchemy and LoginManager to our app
    db.init_app(app)
    login_manager.init_app(app)

    # ── Configure Login Manager ───────────────────────────────
    # Where to redirect if user tries to access protected page
    login_manager.login_view = "auth.login_page"
    login_manager.login_message = "Please login to access this page."
    login_manager.login_message_category = "warning"

    # ── User Loader Function ──────────────────────────────────
    # Flask-Login uses this to load user from session
    @login_manager.user_loader
    def load_user(user_id):
        # Load user from database by ID
        return User.query.get(int(user_id))

    # ── Register Blueprints ───────────────────────────────────
    # Blueprints are like mini-apps that handle different sections
    # Each blueprint handles a group of related routes

    # Auth blueprint: login, register, OTP, Google OAuth
    from app.auth.routes import auth_bp
    app.register_blueprint(auth_bp, url_prefix="/auth")

    # Admin blueprint: all admin dashboard pages
    from app.admin.routes import admin_bp
    app.register_blueprint(admin_bp, url_prefix="/admin")

    # User blueprint: all public user dashboard pages
    from app.user.routes import user_bp
    app.register_blueprint(user_bp, url_prefix="/user")

    # API blueprint: JSON endpoints for dashboard live updates
    from app.api.routes import api_bp
    app.register_blueprint(api_bp, url_prefix="/api")

    # ── Create Database Tables ────────────────────────────────
    with app.app_context():
        # Creates all tables if they don't exist yet
        db.create_all()
        # Seed demo data on first run
        seed_demo_data()

    # ── Root Route ────────────────────────────────────────────
    @app.route("/")
    def index():
        """
        Root route - redirects based on login status and role.
        Not logged in → login page
        Admin → admin dashboard
        User → user dashboard
        """
        from flask_login import current_user
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login_page"))
        if current_user.role == "admin":
            return redirect(url_for("admin_bp.dashboard"))
        return redirect(url_for("user_bp.dashboard"))

    # ── Health Check Route ────────────────────────────────────
    @app.route("/health")
    def health():
        """
        Returns system status as JSON.
        Useful for checking if server is running.
        """
        return jsonify({
            "status":  "running",
            "project": "I-STE Smart Traffic System",
            "version": "1.0.0"
        })

    # ── Error Handlers ────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Page not found", "code": 404}), 404

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "Server error", "code": 500}), 500

    return app

# ─── Seed Demo Data ───────────────────────────────────────────
def seed_demo_data():
    """
    Creates demo accounts and sample data on first run.
    This lets your panel log in and explore immediately.
    Only runs if no users exist yet (prevents duplicate data).
    """
    from models.user_model      import User
    from models.vehicle_model   import Vehicle
    from models.violation_model import Violation
    from app.extensions         import db
    from datetime               import datetime, timedelta
    import random

    # Only seed if database is empty
    if User.query.count() > 0:
        return

    print("[SEED] Creating demo data...")

    # ── Create Admin Account ──────────────────────────────────
    admin = User(
        full_name       = "Admin User",
        email           = "admin@iste.com",
        phone_number    = "9999999999",
        role            = "admin",
        is_verified     = True,
        created_at      = datetime.utcnow(),
    )
    admin.set_password("admin123")
    db.session.add(admin)

    # ── Create Demo User Accounts ─────────────────────────────
    demo_users = [
        {"name": "Rahul Sharma",  "email": "rahul@example.com",  "phone": "9876543210"},
        {"name": "Priya Patel",   "email": "priya@example.com",  "phone": "9876543211"},
        {"name": "Amit Singh",    "email": "amit@example.com",   "phone": "9876543212"},
        {"name": "Sneha Kulkarni","email": "sneha@example.com",  "phone": "9876543213"},
        {"name": "Raj Desai",     "email": "raj@example.com",    "phone": "9876543214"},
    ]

    user_objects = []
    for u in demo_users:
        user = User(
            full_name    = u["name"],
            email        = u["email"],
            phone_number = u["phone"],
            role         = "user",
            is_verified  = True,
            created_at   = datetime.utcnow(),
        )
        user.set_password("user123")
        db.session.add(user)
        user_objects.append(user)

    db.session.flush()  # Get IDs without full commit

    # ── Create Demo Vehicles ──────────────────────────────────
    plates = [
        "MH12AB1234", "MH14CD5678", "MH01EF9012",
        "MH04GH3456", "MH06IJ7890", "MH08KL1234",
        "MH10MN5678", "MH43OP9012", "MH46QR3456",
        "MH48ST7890",
    ]

    vehicle_types = ["car", "bike", "truck"]

    for i, plate in enumerate(plates):
        # Assign vehicle to a demo user
        owner = user_objects[i % len(user_objects)]

        # Random expiry dates (some expired, some valid)
        days_offset = random.randint(-30, 365)
        expiry_date = datetime.utcnow() + timedelta(days=days_offset)

        vehicle = Vehicle(
            owner_id           = owner.id,
            plate_number       = plate,
            vehicle_type       = random.choice(vehicle_types),
            rc_expiry_date        = expiry_date,
            insurance_expiry_date = expiry_date + timedelta(days=random.randint(-60, 300)),
            puc_expiry_date       = expiry_date + timedelta(days=random.randint(-30, 180)),
            is_flagged         = False,
        )
        db.session.add(vehicle)

    db.session.flush()

    # ── Create Demo Violations ────────────────────────────────
    violation_types = ["speeding", "signal", "document"]
    lanes           = ["North", "South", "East", "West"]

    for i in range(15):
        v = Violation(
            plate_number   = random.choice(plates),
            lane_name      = random.choice(lanes),
            violation_type = random.choice(violation_types),
            fine_amount    = random.choice([500, 1000, 1500]),
            is_paid        = random.choice([True, False]),
            timestamp      = datetime.utcnow() - timedelta(
                                hours=random.randint(0, 72)
                             ),
        )
        db.session.add(v)

    # ── Commit Everything to Database ─────────────────────────
    db.session.commit()
    print("[SEED] ✅ Demo data created successfully!")
    print("[SEED] Admin login  → admin@iste.com  / admin123")
    print("[SEED] User login   → rahul@example.com / user123")
