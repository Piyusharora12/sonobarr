from __future__ import annotations

import datetime

from functools import wraps

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import User, ArtistRequest


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


@bp.route("/artist-requests", methods=["GET", "POST"])
@login_required
@admin_required
def artist_requests():
    if request.method == "POST":
        action = request.form.get("action")
        request_id = request.form.get("request_id")

        if not request_id:
            flash("Invalid request ID.", "danger")
            return redirect(url_for("admin.artist_requests"))

        try:
            request_id = int(request_id)
        except ValueError:
            flash("Invalid request ID.", "danger")
            return redirect(url_for("admin.artist_requests"))

        artist_request = ArtistRequest.query.get(request_id)
        if not artist_request:
            flash("Artist request not found.", "danger")
            return redirect(url_for("admin.artist_requests"))

        if artist_request.status != "pending":
            flash("Request has already been processed.", "warning")
            return redirect(url_for("admin.artist_requests"))

        if action == "approve":
            # Add to Lidarr first
            data_handler = current_app.extensions.get("data_handler")
            success = False
            if data_handler:
                # Create a dummy session for the admin
                admin_session = data_handler.ensure_session(f"admin_{current_user.id}", current_user.id, True)
                # Add the artist to Lidarr
                result_status = data_handler.add_artists(f"admin_{current_user.id}", artist_request.artist_name)
                success = result_status == "Added"
            
            if success:
                artist_request.status = "approved"
                artist_request.approved_by_id = current_user.id
                artist_request.approved_at = datetime.datetime.utcnow()
                db.session.commit()
                
                # Notify all connected clients about the approval
                approved_artist = {"Name": artist_request.artist_name, "Status": "Added"}
                data_handler.socketio.emit("refresh_artist", approved_artist)
                
                flash(f"Request for '{artist_request.artist_name}' approved and added to Lidarr.", "success")
            else:
                flash(f"Failed to add '{artist_request.artist_name}' to Lidarr. Request not approved.", "danger")

        elif action == "reject":
            artist_request.status = "rejected"
            artist_request.approved_by_id = current_user.id
            artist_request.approved_at = datetime.datetime.utcnow()
            db.session.commit()
            
            # Notify all connected clients about the rejection
            data_handler = current_app.extensions.get("data_handler")
            if data_handler:
                # Emit refresh_artist event to all connected clients
                rejected_artist = {"Name": artist_request.artist_name, "Status": "Rejected"}
                data_handler.socketio.emit("refresh_artist", rejected_artist)
            
            flash(f"Request for '{artist_request.artist_name}' rejected.", "success")
        else:
            flash("Invalid action.", "danger")

        return redirect(url_for("admin.artist_requests"))

    # GET request - show pending requests
    pending_requests = ArtistRequest.query.filter_by(status="pending").order_by(
        ArtistRequest.created_at.desc()
    ).all()
    return render_template("admin_artist_requests.html", requests=pending_requests)
