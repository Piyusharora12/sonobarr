from __future__ import annotations

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for, session
from flask_login import current_user, login_required

from ..extensions import db
from ..services.integrations.lastfm_user import LastFmUserService
import pylast


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
        lastfm_username = (request.form.get("lastfm_username") or "").strip()
        lastfm_unlink = request.form.get("lastfm_unlink") == "on"
        listenbrainz_username = (request.form.get("listenbrainz_username") or "").strip()
        listenbrainz_token_raw = (request.form.get("listenbrainz_token") or "").strip()
        listenbrainz_token_clear = request.form.get("listenbrainz_token_clear") == "on"

        current_user.display_name = display_name or None
        current_user.avatar_url = avatar_url or None
        current_user.lastfm_username = lastfm_username or None
        if lastfm_unlink:
            current_user.lastfm_session_key = None
        current_user.listenbrainz_username = listenbrainz_username or None

        if listenbrainz_token_clear:
            current_user.listenbrainz_token = None
        elif listenbrainz_token_raw:
            current_user.listenbrainz_token = listenbrainz_token_raw

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
            data_handler = current_app.extensions.get("data_handler")
            if data_handler and current_user.id is not None:
                try:
                    data_handler.refresh_personal_sources_for_user(int(current_user.id))
                except Exception as exc:  # pragma: no cover - defensive logging
                    current_app.logger.error("Failed to refresh personal discovery state: %s", exc)
        return redirect(url_for("main.profile"))

    has_lastfm_link_token = bool(session.get("lastfm_link_token"))
    return render_template("profile.html", has_lastfm_link_token=has_lastfm_link_token)


@bp.route("/profile/lastfm/link", methods=["GET", "POST"])
@login_required
def lastfm_begin_link():
    data_handler = current_app.extensions.get("data_handler")
    if not data_handler or not getattr(data_handler, "last_fm_user_service", None):
        flash("Last.fm is not configured by the administrator.", "warning")
        return redirect(url_for("main.profile"))
    lastfm: LastFmUserService = data_handler.last_fm_user_service
    try:
        network = lastfm._client()
        skg = pylast.SessionKeyGenerator(network)  # type: ignore[name-defined]
        auth_url = skg.get_web_auth_url()
        # Extract token from the URL and store it in session for completion
        try:
            from urllib.parse import urlparse, parse_qs

            parsed = urlparse(auth_url)
            q = parse_qs(parsed.query)
            token = (q.get("token") or [""])[0]
            if token:
                session["lastfm_link_token"] = token
        except Exception:
            pass
    except Exception as exc:  # pragma: no cover - network/auth errors
        current_app.logger.error("Failed to start Last.fm link: %s", exc)
        flash("Couldn't start Last.fm linking. Please try again later.", "danger")
        return redirect(url_for("main.profile"))
    return redirect(auth_url)


@bp.route("/profile/lastfm/complete", methods=["POST"]) 
@login_required
def lastfm_complete_link():
    token = (session.get("lastfm_link_token") or "").strip()
    if not token:
        flash("Missing Last.fm token. Click 'Link Last.fm' first.", "danger")
        return redirect(url_for("main.profile"))
    data_handler = current_app.extensions.get("data_handler")
    if not data_handler or not getattr(data_handler, "last_fm_user_service", None):
        flash("Last.fm is not configured by the administrator.", "warning")
        return redirect(url_for("main.profile"))
    lastfm: LastFmUserService = data_handler.last_fm_user_service
    try:
        network = lastfm._client()
        skg = pylast.SessionKeyGenerator(network)  # type: ignore[name-defined]
        session_key, username = skg.get_web_auth_session_key_username(url=None, token=token)
        if session_key:
            current_user.lastfm_session_key = session_key
            if not current_user.lastfm_username:
                current_user.lastfm_username = username
            db.session.commit()
            session.pop("lastfm_link_token", None)
            flash("Last.fm account linked.", "success")
            try:
                data_handler.refresh_personal_sources_for_user(int(current_user.id))
            except Exception as exc:  # pragma: no cover - defensive logging
                current_app.logger.error("Failed to refresh personal discovery state: %s", exc)
        else:
            flash("Failed to obtain Last.fm session key.", "danger")
    except Exception as exc:  # pragma: no cover - network/auth errors
        current_app.logger.error("Failed to complete Last.fm link: %s", exc)
        flash("Couldn't complete Last.fm linking. Please try again.", "danger")
    return redirect(url_for("main.profile"))
