from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db


bp = Blueprint("main", __name__)


@bp.route("/")
@login_required
def home():
    return render_template("base.html")


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        display_name = (request.form.get("display_name") or "").strip()
        avatar_url = (request.form.get("avatar_url") or "").strip()
        current_user.display_name = display_name or None
        current_user.avatar_url = avatar_url or None

        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")
        current_password = request.form.get("current_password", "")
        password_changed = False
        errors: list[str] = []

        if new_password:
            if new_password != confirm_password:
                errors.append("New password and confirmation do not match.")
            elif len(new_password) < 8:
                errors.append("New password must be at least 8 characters long.")
            elif not current_user.check_password(current_password):
                errors.append("Current password is incorrect.")
            else:
                current_user.set_password(new_password)
                password_changed = True

        if errors:
            for message in errors:
                flash(message, "danger")
            db.session.rollback()
        else:
            db.session.commit()
            flash("Profile updated.", "success")
            if password_changed:
                flash("Password updated.", "success")
        return redirect(url_for("main.profile"))

    return render_template("profile.html")
