# We import random to generate demo data variety.
import random

# We import timedelta/date/datetime for date and time values.
from datetime import date, datetime, timedelta

# We import Flask to create a small app for SQLAlchemy context.
from flask import Flask

# We import the shared SQLAlchemy instance from the Flask app.
# This prevents having two different `db` objects, which would break ORM usage.
from app.extensions import db

# We import password hashing utility for safe password storage.
from werkzeug.security import generate_password_hash

# We do not create a new SQLAlchemy instance here.
# We reuse the shared `db` imported from `app.extensions`.


# This function creates and configures a Flask app for database usage.
def create_db_app():
    # We create a Flask app instance only for DB setup tasks.
    app = Flask(__name__)
    # We configure SQLite database file name as requested (iste.db).
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///iste.db"
    # We disable modification tracking to save memory.
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    # We connect SQLAlchemy with this Flask app.
    db.init_app(app)
    # We return configured app object.
    return app


# This function imports all models so SQLAlchemy knows every table.
def import_all_models():
    # Import User table model.
    from models.user_model import User  # noqa: F401
    # Import Vehicle table model.
    from models.vehicle_model import Vehicle  # noqa: F401
    # Import Violation table model.
    from models.violation_model import Violation  # noqa: F401
    # Import EmergencyLog table model.
    from models.emergency_log_model import EmergencyLog  # noqa: F401
    # Import SystemLog table model.
    from models.system_log_model import SystemLog  # noqa: F401


# This helper decides document_status from RC/Insurance/PUC dates.
def calculate_document_status(rc_expiry, insurance_expiry, puc_expiry):
    # We get today's date to compare expiry dates.
    today = date.today()
    # We keep all expiry dates in one list for easy checks.
    all_dates = [rc_expiry, insurance_expiry, puc_expiry]
    # If any document already expired, overall status is "Expired".
    if any(exp < today for exp in all_dates):
        return "Expired"
    # If any document expires in next 30 days, mark "Expiring Soon".
    if any(today <= exp <= (today + timedelta(days=30)) for exp in all_dates):
        return "Expiring Soon"
    # Otherwise all documents are valid.
    return "All Valid"


# This function seeds demo data only when database is empty.
def seed_demo_data():
    # We import models inside function to avoid circular import issues.
    from models.user_model import User
    # We import vehicle model for inserting vehicles.
    from models.vehicle_model import Vehicle
    # We import violation model for inserting violations.
    from models.violation_model import Violation
    # We import emergency log model for sample logs.
    from models.emergency_log_model import EmergencyLog
    # We import system log model for sample system events.
    from models.system_log_model import SystemLog

    # If users already exist, we skip seeding to avoid duplicates.
    if User.query.count() > 0:
        return

    # We keep all created users in this list for later linking.
    created_users = []

    # We create exactly 2 admin accounts.
    for i in range(1, 3):
        # Build admin object with required fields.
        admin = User(
            full_name=f"Admin {i}",
            email=f"admin{i}@iste.local",
            phone_number=f"+91000000000{i}",
            password_hash=generate_password_hash("Admin@123"),
            role="admin",
            google_id=None,
            is_verified=True,
            created_at=datetime.utcnow() - timedelta(days=random.randint(30, 365)),
            last_login=datetime.utcnow() - timedelta(days=random.randint(0, 5)),
            profile_picture_url="https://example.com/default-admin.png",
        )
        # Add admin to database session.
        db.session.add(admin)
        # Add admin to local tracking list.
        created_users.append(admin)

    # We create exactly 10 normal user accounts.
    for i in range(1, 11):
        # Create one standard user with simple demo values.
        user = User(
            full_name=f"User {i}",
            email=f"user{i}@iste.local",
            phone_number=f"+9199000000{i:02d}",
            password_hash=generate_password_hash("User@123"),
            role="user",
            google_id=None,
            is_verified=(i % 2 == 0),
            created_at=datetime.utcnow() - timedelta(days=random.randint(10, 300)),
            last_login=datetime.utcnow() - timedelta(days=random.randint(0, 15)),
            profile_picture_url="https://example.com/default-user.png",
        )
        # Add user to DB session.
        db.session.add(user)
        # Save user in list for vehicle ownership links.
        created_users.append(user)

    # Commit now so all users get generated IDs.
    db.session.commit()

    # We define allowed demo vehicle types.
    vehicle_types = ["car", "bike", "truck"]
    # We keep created vehicles for linking violations later.
    created_vehicles = []

    # We create exactly 20 vehicles.
    for i in range(1, 21):
        # Choose random owner from created users.
        owner = random.choice(created_users)
        # Build realistic expiry dates with mixed valid/near-expired/expired.
        rc_expiry = date.today() + timedelta(days=random.randint(-30, 365))
        insurance_expiry = date.today() + timedelta(days=random.randint(-30, 365))
        puc_expiry = date.today() + timedelta(days=random.randint(-30, 180))
        # Compute document status from expiry values.
        doc_status = calculate_document_status(rc_expiry, insurance_expiry, puc_expiry)

        # Create vehicle object with required fields.
        vehicle = Vehicle(
            owner_id=owner.id,
            plate_number=f"MH12AB{i:04d}",
            vehicle_type=random.choice(vehicle_types),
            rc_expiry_date=rc_expiry,
            insurance_expiry_date=insurance_expiry,
            puc_expiry_date=puc_expiry,
            registration_date=date.today() - timedelta(days=random.randint(100, 3000)),
            is_flagged=(doc_status == "Expired"),
            document_status=doc_status,
        )
        # Add vehicle row to session.
        db.session.add(vehicle)
        # Track vehicle for future violation entries.
        created_vehicles.append(vehicle)

    # Commit now so vehicles get IDs.
    db.session.commit()

    # We define possible violation types.
    violation_types = ["speeding", "signal", "document"]
    # We define lane names used in sample data.
    lane_names = ["Lane-A", "Lane-B", "Lane-C", "Lane-D"]

    # We create exactly 15 violation records.
    for i in range(1, 16):
        # Pick one random vehicle for this violation.
        vehicle = random.choice(created_vehicles)
        # Pick one violation type randomly.
        v_type = random.choice(violation_types)
        # We alternate paid/unpaid so mix is guaranteed.
        paid_status = (i % 2 == 0)
        # If paid, choose a payment date; otherwise keep None.
        paid_date = datetime.utcnow() - timedelta(days=random.randint(1, 20)) if paid_status else None

        # Default values for speed-related columns.
        detected_speed = None
        speed_limit = None
        # For speeding violations, set speed values.
        if v_type == "speeding":
            # Standard speed limit for demo.
            speed_limit = random.choice([40, 50, 60, 80])
            # Detected speed must exceed speed limit for realism.
            detected_speed = speed_limit + random.randint(5, 35)

        # Create one violation object.
        violation = Violation(
            vehicle_id=vehicle.id,
            lane_name=random.choice(lane_names),
            violation_type=v_type,
            detected_speed=detected_speed,
            speed_limit=speed_limit,
            plate_number=vehicle.plate_number,
            snapshot_path=f"static/evidence/violation_{i}.jpg",
            fine_amount=random.choice([500.0, 1000.0, 1500.0, 2000.0]),
            is_paid=paid_status,
            payment_date=paid_date,
            timestamp=datetime.utcnow() - timedelta(days=random.randint(0, 30)),
            notified_via_sms=(i % 3 == 0),
        )
        # Add violation row to session.
        db.session.add(violation)

    # Add one sample emergency log entry.
    db.session.add(
        EmergencyLog(
            lane_name="Lane-B",
            detected_at=datetime.utcnow() - timedelta(hours=3),
            duration_seconds=75,
            triggered_by="auto",
        )
    )

    # Add one sample system log entry.
    db.session.add(
        SystemLog(
            event_type="startup",
            description="System initialized successfully.",
            severity="info",
            timestamp=datetime.utcnow(),
        )
    )

    # Final commit writes all seeded rows to SQLite.
    db.session.commit()


# This function creates all tables and then seeds sample records.
def init_database():
    # Create Flask app for database context.
    app = create_db_app()
    # Activate app context so DB operations can run.
    with app.app_context():
        # Import every model so metadata has all table definitions.
        import_all_models()
        # Create tables if they do not already exist.
        db.create_all()
        # Add demo records when DB is empty.
        seed_demo_data()
        # Print success message in terminal.
        print("Database initialized and demo data seeded successfully.")


# This block runs only when this file is executed directly.
if __name__ == "__main__":
    # Call database initialization helper.
    init_database()
