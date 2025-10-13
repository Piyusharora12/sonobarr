from __future__ import annotations

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db


bp = Blueprint("main", __name__)


@bp.route("/")
@login_required
def home():
    return render_template("base.html")


def _update_user_profile(form_data, user):
    display_name = (form_data.get("display_name") or "").strip()
    avatar_url = (form_data.get("avatar_url") or "").strip()
    lastfm_username = (form_data.get("lastfm_username") or "").strip()

    user.display_name = display_name or None
    user.avatar_url = avatar_url or None
    user.lastfm_username = lastfm_username or None

    new_password = form_data.get("new_password", "")
    confirm_password = form_data.get("confirm_password", "")
    current_password = form_data.get("current_password", "")
    errors: list[str] = []
    password_changed = False

    if not new_password:
        return errors, password_changed

    if new_password != confirm_password:
        errors.append("New password and confirmation do not match.")
    elif len(new_password) < 8:
        errors.append("New password must be at least 8 characters long.")
    elif not user.check_password(current_password):
        errors.append("Current password is incorrect.")
    else:
        user.set_password(new_password)
        password_changed = True

    return errors, password_changed


def _refresh_personal_sources(user):
    data_handler = current_app.extensions.get("data_handler")
    if not data_handler or user.id is None:
        return

    try:
        data_handler.refresh_personal_sources_for_user(int(user.id))
    except Exception as exc:  # pragma: no cover - defensive logging
        current_app.logger.error("Failed to refresh personal discovery state: %s", exc)


@bp.get("/profile")
@login_required
def profile():
    return render_template("profile.html")


@bp.post("/profile")
@login_required
def update_profile():
    errors, password_changed = _update_user_profile(request.form, current_user)

    if errors:
        for message in errors:
            flash(message, "danger")
        db.session.rollback()
    else:
        db.session.commit()
        flash("Profile updated.", "success")
        if password_changed:
            flash("Password updated.", "success")
        _refresh_personal_sources(current_user)
    return redirect(url_for("main.profile"))
