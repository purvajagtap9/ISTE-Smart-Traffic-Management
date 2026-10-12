# models/user_model.py
# This file defines the User database table
# Every person who registers on I-STE is stored here
# Flask-Login uses this model to manage sessions

from app.extensions import db
from flask_login    import UserMixin
from datetime       import datetime
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin, db.Model):
    """
    User table in the database.
    UserMixin adds is_authenticated, is_active etc.
    that Flask-Login needs automatically.
    """

    # Table name in database
    __tablename__ = "users"

    # ── Columns ───────────────────────────────────────────────
    # Primary key - unique ID for each user
    id              = db.Column(db.Integer, primary_key=True)

    # Basic user information
    full_name       = db.Column(db.String(100), nullable=False)
    email           = db.Column(db.String(120), unique=True, nullable=False)
    phone_number    = db.Column(db.String(15),  unique=True, nullable=True)

    # Password stored as hash (never store plain passwords!)
    password_hash   = db.Column(db.String(256), nullable=True)

    # Role: "admin" or "user"
    role            = db.Column(db.String(10), default="user", nullable=False)

    # Google OAuth ID (filled when user logs in with Google)
    google_id       = db.Column(db.String(100), unique=True, nullable=True)

    # Profile picture URL from Google
    profile_picture = db.Column(db.String(500), nullable=True)

    # Is phone number verified via OTP?
    is_verified     = db.Column(db.Boolean, default=False)

    # Account timestamps
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    last_login      = db.Column(db.DateTime, nullable=True)

    # ── Relationships ─────────────────────────────────────────
    # One user can have many vehicles
    # backref="owner" lets us do vehicle.owner to get User
    vehicles = db.relationship(
        "Vehicle",
        backref ="owner",
        lazy    =True,
        cascade ="all, delete-orphan"
    )

    # ── Password Methods ──────────────────────────────────────
    def set_password(self, password):
        """
        Hashes password and stores it.
        Never stores the actual password text.
        """
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """
        Checks if provided password matches stored hash.
        Returns True if correct, False if wrong.
        """
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    # ── String Representation ─────────────────────────────────
    def __repr__(self):
        return f"<User {self.email} ({self.role})>"