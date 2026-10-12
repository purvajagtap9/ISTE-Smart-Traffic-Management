# We import datetime to save log timestamps.
from datetime import datetime

# We import db from shared database setup.
from models.database import db


# This class creates the "system_logs" table.
class SystemLog(db.Model):
    # Name of SQL table.
    __tablename__ = "system_logs"

    # id is unique primary key.
    id = db.Column(db.Integer, primary_key=True)
    # event_type stores event category name.
    event_type = db.Column(db.String(80), nullable=False)
    # description stores detailed text.
    description = db.Column(db.Text, nullable=False)
    # severity stores info/warning/critical.
    severity = db.Column(db.String(20), nullable=False, default="info")
    # timestamp stores creation time of log.
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Helpful string when printing this model object.
    def __repr__(self):
        # Return readable object details.
        return f"<SystemLog {self.id} - {self.event_type}>"
