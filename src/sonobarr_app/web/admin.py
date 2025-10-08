from __future__ import annotations

from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import User


bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


@bp.route("/users", methods=["GET", "POST"])
@login_required
@admin_required
def users():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "create":
            username = (request.form.get("username") or "").strip()
            password = request.form.get("password") or ""
            confirm_password = (request.form.get("confirm_password") or "").strip()
            display_name = (request.form.get("display_name") or "").strip()
            avatar_url = (request.form.get("avatar_url") or "").strip()
            is_admin = request.form.get("is_admin") == "on"

            if not username or not password:
                flash("Username and password are required.", "danger")
            elif password != confirm_password:
                flash("Password confirmation does not match.", "danger")
            elif User.query.filter_by(username=username).first():
                flash("Username already exists.", "danger")
            else:
                user = User(
                    username=username,
                    display_name=display_name or None,
                    avatar_url=avatar_url or None,
                    is_admin=is_admin,
                )
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
                flash(f"User '{username}' created.", "success")
        elif action == "delete":
            try:
                user_id = int(request.form.get("user_id", "0"))
            except ValueError:
                flash("Invalid user id.", "danger")
            else:
                user = User.query.get(user_id)
                if not user:
                    flash("User not found.", "danger")
                elif user.id == current_user.id:
                    flash("You cannot delete your own account.", "warning")
                elif user.is_admin and User.query.filter_by(is_admin=True).count() <= 1:
                    flash("At least one administrator must remain.", "warning")
                else:
                    db.session.delete(user)
                    db.session.commit()
                    flash(f"User '{user.username}' deleted.", "success")
        return redirect(url_for("admin.users"))

    users = User.query.order_by(User.username.asc()).all()
    return render_template("admin_users.html", users=users)
