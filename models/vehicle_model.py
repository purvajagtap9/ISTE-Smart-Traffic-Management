# models/vehicle_model.py
# Vehicle and driver registration database table
# Stores all RTO-required details including document uploads

from app.extensions import db
from datetime       import datetime

class Vehicle(db.Model):
    __tablename__ = "vehicles"

    # ── Primary Key ───────────────────────────────────────────
    id = db.Column(db.Integer, primary_key=True)

    # ── Owner Link ────────────────────────────────────────────
    owner_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )

    # ── Vehicle Details ───────────────────────────────────────
    plate_number  = db.Column(db.String(20), unique=True, nullable=False)
    vehicle_type  = db.Column(db.String(20), default="car")
    vehicle_make  = db.Column(db.String(50), nullable=True)  # Honda, Maruti
    vehicle_model = db.Column(db.String(50), nullable=True)  # City, Swift
    vehicle_color = db.Column(db.String(30), nullable=True)
    engine_number = db.Column(db.String(50), nullable=True)
    chassis_number= db.Column(db.String(50), nullable=True)
    year_of_mfg   = db.Column(db.Integer,    nullable=True)
    fuel_type     = db.Column(db.String(20), default="Petrol")

    # ── Driver License Details ────────────────────────────────
    license_number   = db.Column(db.String(30), nullable=True)
    license_expiry   = db.Column(db.DateTime,   nullable=True)

    # ── Document Expiry Dates ─────────────────────────────────
    rc_expiry_date        = db.Column(db.DateTime, nullable=False)
    insurance_expiry_date = db.Column(db.DateTime, nullable=False)
    puc_expiry_date       = db.Column(db.DateTime, nullable=False)

    # ── Document Upload Paths ─────────────────────────────────
    rc_document_path        = db.Column(db.String(500), nullable=True)
    insurance_document_path = db.Column(db.String(500), nullable=True)
    puc_document_path       = db.Column(db.String(500), nullable=True)
    license_document_path   = db.Column(db.String(500), nullable=True)

    # ── Address Details ───────────────────────────────────────
    address      = db.Column(db.String(200), nullable=True)
    city         = db.Column(db.String(50),  nullable=True)
    state        = db.Column(db.String(50),  nullable=True)
    pincode      = db.Column(db.String(10),  nullable=True)

    # ── Status ────────────────────────────────────────────────
    is_flagged         = db.Column(db.Boolean, default=False)
    registration_status= db.Column(db.String(20), default="Pending")
    # Pending → Approved → Rejected

    registered_at = db.Column(db.DateTime, default=datetime.utcnow)

    # ── Document Status Property ──────────────────────────────
    @property
    def document_status(self):
        from datetime import timedelta
        now  = datetime.utcnow()
        soon = now + timedelta(days=30)
        if (self.puc_expiry_date       < now or
            self.insurance_expiry_date < now or
            self.rc_expiry_date        < now):
            return "Expired"
        elif (self.puc_expiry_date       < soon or
              self.insurance_expiry_date < soon or
              self.rc_expiry_date        < soon):
            return "Expiring Soon"
        return "Valid"

    def __repr__(self):
        return f"<Vehicle {self.plate_number}>"