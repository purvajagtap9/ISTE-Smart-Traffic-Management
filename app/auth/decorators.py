# We import wraps so our decorators do not break Flask endpoint names.
from functools import wraps

# We import redirect and url_for so we can send the user to login pages.
from flask import redirect, url_for

# We import current_user so decorators can check who is logged in.
from flask_login import current_user


# Admin-only decorator.
def admin_required(view_func):
    # wraps keeps the original function metadata.
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        # If user is not logged in, redirect to Google login start.
        if not getattr(current_user, "is_authenticated", False):
            return redirect("/login?reason=protected")
        # If logged-in user is not an admin, redirect to login page.
        if getattr(current_user, "role", None) != "admin":
            return redirect("/login?reason=protected")
        # Otherwise, user is admin and allowed to continue.
        return view_func(*args, **kwargs)

    # Return the wrapped function to Flask.
    return wrapped_view


# Login-required decorator.
def login_required(view_func):
    # wraps keeps the original function metadata.
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        # If user is not logged in, redirect to Google login start.
        if not getattr(current_user, "is_authenticated", False):
            return redirect("/login?reason=protected")
        # Otherwise, user is logged in and allowed to continue.
        return view_func(*args, **kwargs)

    # Return the wrapped function to Flask.
    return wrapped_view


# Verification-required decorator (OTP verification).
def verified_required(view_func):
    # wraps keeps the original function metadata.
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        # If user is not logged in, redirect to Google login start.
        if not getattr(current_user, "is_authenticated", False):
            return redirect("/login?reason=protected")
        # If phone is not verified, redirect them to the OTP page.
        if not getattr(current_user, "is_verified", False):
            return redirect("/login/otp")
        # Otherwise, phone is verified and allowed to continue.
        return view_func(*args, **kwargs)

    # Return the wrapped function to Flask.
    return wrapped_view

