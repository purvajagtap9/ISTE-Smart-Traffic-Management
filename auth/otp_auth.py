# This file is here to match your requested path: `/auth/otp_auth.py`.
# In this project, Flask actually registers routes from `app/auth/...` modules.

# We import the real OTP implementation from the Flask package.
from app.auth.otp_auth import *  # noqa: F403

