# models/violation_model.py
# This file defines the Violation database table
# Every traffic violation detected is stored here
# Includes fine amount and payment status

from app.extensions import db
from datetime       import datetime

class Violation(db.Model):
    """
    Violation table in the database.
    Each row is one traffic violation detected by the system.
    """

    __tablename__ = "violations"

    # ── Columns ───────────────────────────────────────────────
    id             = db.Column(db.Integer, primary_key=True)

    # Vehicle that committed violation
    plate_number   = db.Column(db.String(20), nullable=False)

    # Which lane the violation occurred in
    lane_name      = db.Column(db.String(10), nullable=False)

    # Type: "speeding", "signal", "document"
    violation_type = db.Column(db.String(20), nullable=False)

    # Speed details (for speeding violations)
    detected_speed = db.Column(db.Float,   nullable=True)
    speed_limit    = db.Column(db.Integer, default=40)

    # Fine details
    fine_amount    = db.Column(db.Float,   default=500.0)
    is_paid        = db.Column(db.Boolean, default=False)
    payment_date   = db.Column(db.DateTime, nullable=True)

    # Snapshot photo path
    snapshot_path  = db.Column(db.String(500), nullable=True)

    # Was SMS notification sent?
    notified       = db.Column(db.Boolean, default=False)

    # When violation was detected
    timestamp      = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Violation {self.plate_number} - {self.violation_type}>"