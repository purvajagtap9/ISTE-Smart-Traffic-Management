# This file exists so your `app/__init__.py` can import `auth_bp`.

# We import the Blueprint from our Google OAuth module.
from app.auth.google_auth import auth_bp

# We also re-export init_google_oauth in case you want to call it elsewhere.
from app.auth.google_auth import init_google_oauth

# Import OTP auth module so its routes are registered on `auth_bp`.
# This import is needed because Flask registers routes when the module is imported.
from app.auth import otp_auth  # noqa: F401

# Import UI routes so `/login` and `/register` pages are registered.
from app.auth import ui_routes  # noqa: F401


