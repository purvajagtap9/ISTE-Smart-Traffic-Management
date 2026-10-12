# Step-by-step: how to get Google Client ID & Client Secret (beginner)
# 1) Go to https://console.cloud.google.com/ and sign in to Google Cloud.
# 2) Click the project dropdown and create a new project (or choose an existing one).
# 3) In the left menu, open "APIs & Services" -> "OAuth consent screen".
# 4) Choose "External" or "Internal" (for demos, either is fine).
# 5) Fill the app name, support email, and save the consent screen.
# 6) Next, go to "APIs & Services" -> "Credentials".
# 7) Click "Create Credentials" -> "OAuth client ID".
# 8) Choose "Web application".
# 9) Set "Authorized redirect URIs" to your callback URL:
#    http://127.0.0.1:5000/login/google/callback
#    (When you deploy, use your real domain instead of 127.0.0.1)
# 10) After creating, copy the "Client ID" and "Client Secret".
# 11) Paste them into your `.env` / `.env.example`:
#    GOOGLE_CLIENT_ID=...
#    GOOGLE_CLIENT_SECRET=...

# We import os so we can read ADMIN_EMAILS from environment variables.
import os

# We import Blueprint so we can group auth routes together.
from flask import Blueprint

# We import redirect to send the user to another URL.
from flask import redirect

# We import url_for to generate correct route URLs.
from flask import url_for

# We import Flask request context helpers if needed later (kept for extensibility).
from flask import request  # noqa: F401

# We import OAuth from Authlib to handle OAuth2/OIDC login flow.
from authlib.integrations.flask_client import OAuth

# We import login_user to set Flask-Login session.
from flask_login import login_user

# We import current Flask SQLAlchemy db session so we can commit changes.
from app.extensions import db

# We import session so we can store temporary profile data for `/register`.
from flask import session

# We import the User model to create and query users in SQLite.
from models.user_model import User


# We create a Blueprint named "auth" (this is important for url_for endpoint names).
auth_bp = Blueprint("auth", __name__)

# We create one OAuth registry object that will hold Google provider config.
oauth = OAuth()


# This helper reads ADMIN_EMAILS (comma-separated) and returns a set for fast checks.
def get_admin_emails():
    # Read the raw string from environment (example: "a@gmail.com,b@gmail.com").
    raw_admin_emails = os.getenv("ADMIN_EMAILS", "")
    # Split by comma so each email becomes an item.
    items = raw_admin_emails.split(",")
    # Normalize by stripping spaces and lowercasing for consistent matching.
    normalized = [item.strip().lower() for item in items]
    # Use set to avoid duplicates and to speed up membership checks.
    return {email for email in normalized if email}


# This function must be called once from the app setup to register Google OAuth.
def init_google_oauth(app):
    # Attach Authlib OAuth to the Flask app.
    oauth.init_app(app)

    # Register the "google" provider with Authlib.
    oauth.register(
        # Provider name used later as oauth.google...
        name="google",
        # Client ID from environment.
        client_id=app.config.get("GOOGLE_CLIENT_ID"),
        # Client secret from environment.
        client_secret=app.config.get("GOOGLE_CLIENT_SECRET"),
        # OpenID discovery URL (tells Authlib where to find endpoints).
        server_metadata_url=app.config.get(
            "GOOGLE_DISCOVERY_URL",
            "https://accounts.google.com/.well-known/openid-configuration",
        ),
        # Tell Google what data we want.
        # "openid email profile" includes id token + email + basic profile info.
        client_kwargs={"scope": "openid email profile"},
    )


# Route 1: start Google login by redirecting the user to Google.
@auth_bp.route("/login/google")
def login_google():
    # Build the full callback URL for Google to redirect back to.
    redirect_uri = url_for("auth.google_callback", _external=True)
    # Redirect the browser to Google OAuth consent/login page.
    return oauth.google.authorize_redirect(redirect_uri)


# Route 2: Google redirects here after user logs in successfully.
@auth_bp.route("/login/google/callback")
def google_callback():
    # Exchange the authorization code for tokens (access token / id token).
    token = oauth.google.authorize_access_token()
    # Fetch user profile information from Google using the token.
    user_info = oauth.google.userinfo(token=token)

    # Extract user details from Google response.
    full_name = user_info.get("name", "")  # name from Google profile
    email = user_info.get("email", "").lower()  # email is the key for matching users
    profile_picture_url = user_info.get("picture", "")  # profile picture URL
    google_id = user_info.get("sub", "")  # unique Google account id (OpenID "sub")

    # If Google didn't return an email, we cannot safely create/login a user.
    if not email:
        # Send the user back to start login again.
        return redirect(url_for("auth.login_google"))

    # Try to find an existing user by email.
    existing_user = User.query.filter_by(email=email).first()

    # If the user exists, just log them in.
    if existing_user:
        # Update Google-linked fields in case they changed.
        existing_user.google_id = google_id
        existing_user.profile_picture_url = profile_picture_url
        # Mark as verified since Google authentication succeeded.
        existing_user.is_verified = True
        # Save the updates to the database.
        db.session.commit()
        # Create Flask-Login session.
        login_user(existing_user)
        # Keep reference for role redirect.
        logged_in_user = existing_user

    # If the user does not exist, create a new account automatically.
    else:
        # Load admin emails from .env.
        admin_emails = get_admin_emails()
        # Default role is "user" as requested.
        assigned_role = "user"
        # If email matches the admin list, assign "admin" role.
        if email in admin_emails:
            assigned_role = "admin"

        # Create a new user row using required User table fields.
        # Note: password is not used for Google login right now, but column is required.
        new_user = User(
            full_name=full_name if full_name else "Google User",
            email=email,
            # phone_number is required; we set a placeholder to allow OTP flow later.
            phone_number=f"pending_{google_id[:10]}",
            # password_hash is required; placeholder means you can implement password later.
            password_hash="google_oauth_placeholder",
            role=assigned_role,
            google_id=google_id,
            # Mark verified as True because Google login succeeded.
            is_verified=True,
            # Store profile picture.
            profile_picture_url=profile_picture_url,
        )

        # Save new user to DB.
        db.session.add(new_user)
        db.session.commit()

        # Create Flask-Login session.
        login_user(new_user)
        # Keep reference for role redirect.
        logged_in_user = new_user

    # Role-based redirect after successful login.
    if logged_in_user.role == "admin":
        # Send admins to the admin dashboard.
        return redirect("/admin/dashboard")

    # Send normal users to the user dashboard.
    return redirect("/user/dashboard")


# ---------------------------------------------
# Google "Register" flow (autofill name/email)
# ---------------------------------------------


# Route: start Google login for the registration autofill flow.
@auth_bp.route("/register/google")
def register_with_google():
    # Build the callback URL for the registration flow.
    redirect_uri = url_for("auth.register_google_callback", _external=True)
    # Start the OAuth redirect to Google.
    return oauth.google.authorize_redirect(redirect_uri)


# Route: Google redirects here after successful login for registration autofill.
@auth_bp.route("/register/google/callback")
def register_google_callback():
    # Exchange authorization code for tokens.
    token = oauth.google.authorize_access_token()
    # Fetch user profile information from Google.
    user_info = oauth.google.userinfo(token=token)

    # Extract fields needed for autofill.
    full_name = user_info.get("name", "")
    email = user_info.get("email", "").lower()
    profile_picture_url = user_info.get("picture", "")
    google_id = user_info.get("sub", "")

    # If email is missing, we send the user back to register page.
    if not email:
        return redirect("/register")

    # Store values in session so `/register` can prefill inputs.
    session["google_register_name"] = full_name
    session["google_register_email"] = email
    session["google_register_picture_url"] = profile_picture_url
    session["google_register_google_id"] = google_id

    # Redirect back to register page.
    return redirect("/register?from_google=1")

