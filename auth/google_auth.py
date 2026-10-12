# Step 1: Open https://console.cloud.google.com/ and sign in with your Google account.
# Step 2: Create a new project (or choose an existing project) for I-STE.
# Step 3: Go to "APIs & Services" -> "OAuth consent screen" and configure app details.
# Step 4: Add your test users in consent screen while developing.
# Step 5: Go to "Credentials" -> "Create Credentials" -> "OAuth client ID".
# Step 6: Choose application type as "Web application".
# Step 7: Add authorized redirect URI: http://127.0.0.1:5000/login/google/callback
# Step 8: Copy generated Client ID and Client Secret into your .env file.
# Step 9: Set ADMIN_EMAILS in .env as comma-separated emails for admin auto-role.

# We import os to read environment variables from the system.
import os

# We import Blueprint to organize auth routes cleanly.
from flask import Blueprint
# We import current_app to access app configuration values.
from flask import current_app
# We import redirect to send user to Google/login destinations.
from flask import redirect
# We import request for accessing callback request context if needed.
from flask import request
# We import url_for to build internal route URLs safely.
from flask import url_for

# We import OAuth from Authlib to handle OAuth 2.0 flow.
from authlib.integrations.flask_client import OAuth

# We import login_user to create Flask-Login session.
from flask_login import login_user

# We import database object to save/read users from SQLite.
from models.database import db
# We import User model for querying/creating user accounts.
from models.user_model import User


# We create a Blueprint named "auth" for login-related routes.
auth_bp = Blueprint("auth", __name__)

# We create one OAuth object that can be initialized with Flask app.
oauth = OAuth()


# This helper reads admin emails from environment and returns a set.
def get_admin_emails():
    # Read raw comma-separated admin emails from .env variable ADMIN_EMAILS.
    raw_admin_emails = os.getenv("ADMIN_EMAILS", "")
    # Split the string by comma and clean spaces from each item.
    parsed_admin_emails = [email.strip().lower() for email in raw_admin_emails.split(",")]
    # Keep only non-empty values and convert to set for fast membership checks.
    return {email for email in parsed_admin_emails if email}


# This function must be called once from app setup to configure Google OAuth.
def init_google_oauth(app):
    # Initialize Authlib OAuth extension with current Flask app.
    oauth.init_app(app)

    # Register Google provider details used during OAuth flow.
    oauth.register(
        # Provider name used in oauth.google calls.
        name="google",
        # Read Client ID from app config (loaded from .env).
        client_id=app.config.get("GOOGLE_CLIENT_ID"),
        # Read Client Secret from app config (loaded from .env).
        client_secret=app.config.get("GOOGLE_CLIENT_SECRET"),
        # Use OpenID discovery endpoint to fetch auth/token/userinfo URLs.
        server_metadata_url=app.config.get(
            "GOOGLE_DISCOVERY_URL",
            "https://accounts.google.com/.well-known/openid-configuration",
        ),
        # Request profile + email data from Google account.
        client_kwargs={"scope": "openid email profile"},
    )


# Route: start Google login flow by redirecting to Google sign-in page.
@auth_bp.route("/login/google")
def login_google():
    # Build callback URL where Google will return user after successful login.
    redirect_uri = url_for("auth.google_callback", _external=True)
    # Send user to Google OAuth authorization page.
    return oauth.google.authorize_redirect(redirect_uri)


# Route: callback URL called by Google after user approves login.
@auth_bp.route("/login/google/callback")
def google_callback():
    # Exchange authorization code for access token.
    token = oauth.google.authorize_access_token()
    # Fetch user information from Google userinfo endpoint.
    user_info = oauth.google.userinfo(token=token)

    # Extract full name from Google response (fallback to empty string).
    full_name = user_info.get("name", "")
    # Extract email from Google response and normalize to lowercase.
    email = user_info.get("email", "").lower()
    # Extract profile picture URL from Google response.
    profile_picture_url = user_info.get("picture", "")
    # Extract unique Google account identifier.
    google_id = user_info.get("sub", "")

    # If email is missing, redirect back to Google login route.
    if not email:
        # Redirect user to retry login.
        return redirect(url_for("auth.login_google"))

    # Try to find an existing user account by email.
    existing_user = User.query.filter_by(email=email).first()

    # If user already exists, update Google-linked fields and login.
    if existing_user:
        # Save Google ID if missing or changed.
        existing_user.google_id = google_id
        # Update profile picture from latest Google account picture.
        existing_user.profile_picture_url = profile_picture_url
        # Mark as verified because Google account has verified identity context.
        existing_user.is_verified = True
        # Persist updates to database.
        db.session.commit()
        # Create Flask-Login session for this user.
        login_user(existing_user)
        # Keep selected user in one variable for role-based redirect.
        logged_in_user = existing_user
    else:
        # Build set of admin emails from ADMIN_EMAILS variable.
        admin_emails = get_admin_emails()
        # Decide role based on email matching in admin list.
        assigned_role = "admin" if email in admin_emails else "user"

        # Create new user account automatically for first-time Google login.
        new_user = User(
            # Save full name from Google account.
            full_name=full_name if full_name else "Google User",
            # Save email from Google account.
            email=email,
            # Phone number is unknown now, so keep placeholder for OTP flow.
            phone_number=f"pending_{google_id[:10]}",
            # Password hash is not used for Google login; keep placeholder value.
            password_hash="google_oauth_no_password",
            # Role defaults to user unless email is in admin list.
            role=assigned_role,
            # Save Google unique identifier.
            google_id=google_id,
            # Google login completed successfully, so mark verified as True.
            is_verified=True,
            # Save Google profile picture URL.
            profile_picture_url=profile_picture_url,
        )
        # Add new user to session for insertion.
        db.session.add(new_user)
        # Commit to save new row and generate user ID.
        db.session.commit()
        # Log in the newly created account.
        login_user(new_user)
        # Keep selected user in one variable for final redirect decision.
        logged_in_user = new_user

    # If user role is admin, send to admin dashboard.
    if logged_in_user.role == "admin":
        # Redirect to admin dashboard route path.
        return redirect("/admin/dashboard")

    # Otherwise redirect normal users to user dashboard.
    return redirect("/user/dashboard")
