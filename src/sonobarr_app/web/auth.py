from __future__ import annotations

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy.exc import OperationalError, ProgrammingError

from ..models import User
from ..extensions import db


bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if not username or not password:
            flash("Username and password are required.", "danger")
        else:
            try:
                user = User.query.filter_by(username=username).first()
            except (OperationalError, ProgrammingError) as exc:
                current_app.logger.warning(
                    "Database schema not ready during login attempt for username %s: %s",
                    username,
                    exc,
                )
                db.session.rollback()
                flash("Database upgrade in progress. Please try again in a moment.", "warning")
            else:
                if not user or not user.check_password(password):
                    flash("Invalid username or password.", "danger")
                elif not user.is_active:
                    flash("Account is disabled.", "danger")
                else:
                    login_user(user)
                    flash("Welcome to Sonobarr!", "success")
                    return redirect(url_for("main.home"))

    return render_template("login.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))
