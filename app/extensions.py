# app/extensions.py
# This file initializes Flask extensions
# We initialize them here (without app) to avoid
# circular imports - a very common Flask problem
#
# Circular import problem explained simply:
# If app/__init__.py imports from models, and models
# imports from app/__init__.py, Python gets confused.
# Solution: put extensions here, import from here everywhere.

from flask_sqlalchemy import SQLAlchemy
from flask_login      import LoginManager

# ─── Database Extension ───────────────────────────────────────
# SQLAlchemy handles all database operations
# We create it here without linking to app yet
# It gets linked to app in app/__init__.py via db.init_app(app)
db = SQLAlchemy()

# ─── Login Manager Extension ──────────────────────────────────
# Flask-Login handles user sessions and authentication
# It tracks who is logged in across page requests
login_manager = LoginManager()