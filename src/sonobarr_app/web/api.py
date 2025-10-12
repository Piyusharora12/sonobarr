from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user

from ..extensions import db
from ..models import ArtistRequest, User


bp = Blueprint("api", __name__, url_prefix="/api")


def api_key_required(view):
    """Decorator to require API key for API endpoints."""
    def wrapped(*args, **kwargs):
        # Extract API key from headers or query params
        api_key = request.headers.get("X-API-Key")
        if api_key is None:
            api_key = request.headers.get("X-Api-Key")
        if api_key is None:
            api_key = request.args.get("api_key") or request.args.get("key")
        if api_key is not None:
            api_key = str(api_key).strip()

        configured_key = current_app.config.get("API_KEY")
        if not configured_key:
            data_handler = current_app.extensions.get("data_handler")
            if data_handler is not None:
                configured_key = getattr(data_handler, "api_key", None)

        if configured_key:
            configured_key = str(configured_key).strip()
            if configured_key and api_key != configured_key:
                return jsonify({"error": "Invalid API key"}), 401

        return view(*args, **kwargs)
    wrapped.__name__ = view.__name__
    return wrapped


@bp.route("/status")
@api_key_required
def status():
    """Get basic system status information."""
    try:
        user_count = User.query.count()
        admin_count = User.query.filter_by(is_admin=True).count()
        pending_requests = ArtistRequest.query.filter_by(status="pending").count()
        total_requests = ArtistRequest.query.count()
        
        # Get data handler for Lidarr status
        data_handler = current_app.extensions.get("data_handler")
        lidarr_connected = False
        if data_handler:
            # Simple check - if we have cached Lidarr data, assume connected
            lidarr_connected = bool(data_handler.cached_lidarr_names)
        
        return jsonify({
            "status": "healthy",
            "version": current_app.config.get("APP_VERSION", "unknown"),
            "users": {
                "total": user_count,
                "admins": admin_count
            },
            "artist_requests": {
                "total": total_requests,
                "pending": pending_requests
            },
            "services": {
                "lidarr_connected": lidarr_connected
            }
        })
    except Exception as e:
        current_app.logger.error(f"API status error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/artist-requests")
@api_key_required
def artist_requests():
    """Get artist requests with optional filtering."""
    try:
        status_filter = request.args.get('status')  # pending, approved, rejected
        limit = min(int(request.args.get('limit', 50)), 100)  # Max 100
        
        query = ArtistRequest.query
        
        if status_filter:
            query = query.filter_by(status=status_filter)
        
        requests = query.order_by(ArtistRequest.created_at.desc()).limit(limit).all()
        
        result = []
        for req in requests:
            result.append({
                "id": req.id,
                "artist_name": req.artist_name,
                "status": req.status,
                "requested_by": req.requested_by.name if req.requested_by else "Unknown",
                "created_at": req.created_at.isoformat() if req.created_at else None,
                "approved_by": req.approved_by.name if req.approved_by else None,
                "approved_at": req.approved_at.isoformat() if req.approved_at else None
            })
        
        return jsonify({
            "count": len(result),
            "requests": result
        })
    except Exception as e:
        current_app.logger.error(f"API artist-requests error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@bp.route("/stats")
@api_key_required
def stats():
    """Get detailed statistics."""
    try:
        # User stats
        total_users = User.query.count()
        admin_users = User.query.filter_by(is_admin=True).count()
        active_users = User.query.filter_by(is_active=True).count()
        
        # Request stats
        total_requests = ArtistRequest.query.count()
        pending_requests = ArtistRequest.query.filter_by(status="pending").count()
        approved_requests = ArtistRequest.query.filter_by(status="approved").count()
        rejected_requests = ArtistRequest.query.filter_by(status="rejected").count()
        
        # Recent activity (last 7 days)
        from datetime import datetime, timedelta
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_requests = ArtistRequest.query.filter(ArtistRequest.created_at >= week_ago).count()
        
        # Top requesters
        from sqlalchemy import func
        top_requesters = db.session.query(
            User.username,
            func.count(ArtistRequest.id).label('request_count')
        ).join(ArtistRequest, User.id == ArtistRequest.requested_by_id)\
         .group_by(User.id, User.username)\
         .order_by(func.count(ArtistRequest.id).desc())\
         .limit(5).all()
        
        return jsonify({
            "users": {
                "total": total_users,
                "admins": admin_users,
                "active": active_users
            },
            "artist_requests": {
                "total": total_requests,
                "pending": pending_requests,
                "approved": approved_requests,
                "rejected": rejected_requests,
                "recent_week": recent_requests
            },
            "top_requesters": [
                {"username": username, "requests": count}
                for username, count in top_requesters
            ]
        })
    except Exception as e:
        current_app.logger.error(f"API stats error: {e}")
        return jsonify({"error": "Internal server error"}), 500
