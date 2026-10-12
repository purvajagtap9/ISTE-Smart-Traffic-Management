# We import datetime to save emergency event time.
from datetime import datetime

# We import db from shared database setup.
from models.database import db


# This class creates the "emergency_logs" table.
class EmergencyLog(db.Model):
    # Table name in SQLite database.
    __tablename__ = "emergency_logs"

    # id is unique primary key.
    id = db.Column(db.Integer, primary_key=True)
    # lane_name stores where emergency was detected.
    lane_name = db.Column(db.String(80), nullable=False)
    # detected_at stores event start time.
    detected_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    # duration_seconds stores total preemption duration.
    duration_seconds = db.Column(db.Integer, nullable=False, default=0)
    # triggered_by stores "auto" or "manual".
    triggered_by = db.Column(db.String(20), nullable=False)

    # Helpful text output for debugging.
    def __repr__(self):
        # Return readable object information.
        return f"<EmergencyLog {self.id} - {self.lane_name}>"
