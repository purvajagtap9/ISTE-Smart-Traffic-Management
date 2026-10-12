# We import wraps so our decorators keep function names/docs.
from functools import wraps

# We import request/redirect/url_for to send user to login pages.
from flask import redirect, url_for

# We import current_user to read logged-in user info.
from flask_login import current_user


# This decorator ensures the user is logged in.
def login_required(view_func):
    # wraps keeps Flask routing and metadata intact.
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        # If current_user is not authenticated, redirect to login.
        if not getattr(current_user, "is_authenticated", False):
            # We redirect to the google login route (you can change to /login).
            return redirect("/login?reason=protected")
        # If authenticated, call the original view.
        return view_func(*args, **kwargs)

    # Return the wrapped function to Flask.
    return wrapped_view


# This decorator ensures the user is admin.
def admin_required(view_func):
    # wraps keeps Flask routing and metadata intact.
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        # If user is not logged in, redirect first.
        if not getattr(current_user, "is_authenticated", False):
            return redirect("/login?reason=protected")
        # If role is not admin, redirect to login page.
        if getattr(current_user, "role", None) != "admin":
            return redirect("/login?reason=protected")
        # If admin, call the original view.
        return view_func(*args, **kwargs)

    # Return the wrapped function to Flask.
    return wrapped_view


# This decorator ensures phone OTP verification is done.
def verified_required(view_func):
    # wraps keeps Flask routing and metadata intact.
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        # If user is not logged in, redirect to login.
        if not getattr(current_user, "is_authenticated", False):
            return redirect("/login?reason=protected")
        # If phone (or OTP step) is not verified, redirect to OTP page.
        if not getattr(current_user, "is_verified", False):
            # We redirect to a placeholder OTP route. You will implement it later.
            return redirect("/login/otp")
        # If verified, call the original view.
        return view_func(*args, **kwargs)

    # Return the wrapped function to Flask.
    return wrapped_view

