# app/config.py
# This file contains all configuration settings
# for the I-STE Flask application.
# Settings are loaded from .env file for security.

import os
from dotenv import load_dotenv

# Load .env file variables into environment
load_dotenv()

class Config:
    """
    Base configuration class.
    All settings that apply to every environment go here.
    """

    # ── Security ──────────────────────────────────────────────
    # Secret key is used to sign session cookies
    # Change this to a random string in production!
    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        "iste-dev-secret-key-please-change"
    )

    # ── Database ──────────────────────────────────────────────
    # SQLite database stored in instance/ folder
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "sqlite:///iste.db"
    )
    # Disable event tracking to save memory
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ── Google OAuth ──────────────────────────────────────────
    GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID",     "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")

    # ── Twilio OTP ────────────────────────────────────────────
    TWILIO_ACCOUNT_SID  = os.getenv("TWILIO_ACCOUNT_SID",  "")
    TWILIO_AUTH_TOKEN   = os.getenv("TWILIO_AUTH_TOKEN",   "")
    TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")

    # ── Admin Emails ──────────────────────────────────────────
    # Comma separated list of emails that get admin role
    # when logging in with Google
    ADMIN_EMAILS = os.getenv(
        "ADMIN_EMAILS", "admin@iste.com"
    ).split(",")

    # ── Camera Settings ───────────────────────────────────────
    # Default IP Webcam URLs for each lane
    # Change these to match your phone IPs
    CAMERA_URLS = {
        "North": os.getenv("CAMERA_NORTH", ""),
        "South": os.getenv("CAMERA_SOUTH", ""),
        "East":  os.getenv("CAMERA_EAST",  ""),
        "West":  os.getenv("CAMERA_WEST",  ""),
    }

    # ── Detection Settings ────────────────────────────────────
    # Speed limit in km/h for violation detection
    SPEED_LIMIT = int(os.getenv("SPEED_LIMIT", "40"))

    # How often to run detection loop (seconds)
    DETECTION_INTERVAL = int(os.getenv("DETECTION_INTERVAL", "2"))


class DevelopmentConfig(Config):
    """
    Development environment settings.
    Debug mode shows detailed error pages.
    """
    DEBUG = True


class ProductionConfig(Config):
    """
    Production environment settings.
    Debug mode off for security.
    """
    DEBUG = False


# Dictionary to select config by name
config = {
    "development": DevelopmentConfig,
    "production":  ProductionConfig,
    "default":     DevelopmentConfig,
}