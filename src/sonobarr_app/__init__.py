from __future__ import annotations

from typing import Any, Dict, Optional

from flask import Flask, current_app

from .bootstrap import bootstrap_super_admin
from .config import Config, STATIC_DIR, TEMPLATE_DIR
from .extensions import csrf, db, login_manager, migrate, socketio
from .services.data_handler import DataHandler
from .services.releases import ReleaseClient
from .sockets import register_socketio_handlers
from .web import admin_bp, auth_bp, main_bp


def create_app(config_class: type[Config] = Config) -> Flask:
    app = Flask(
        __name__,
        static_folder=str(STATIC_DIR),
        template_folder=str(TEMPLATE_DIR),
    )
    app.config.from_object(config_class)

    # Core extensions -------------------------------------------------
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access Sonobarr."
    login_manager.login_message_category = "warning"
    csrf.init_app(app)
    socketio.init_app(app, async_mode="gevent")

    from .models import User  # Imported lazily to avoid circular imports

    @login_manager.user_loader
    def load_user(user_id: str) -> Optional[User]:
        if not user_id:
            return None
        try:
            return User.query.get(int(user_id))
        except (TypeError, ValueError):
            return None

    # Services --------------------------------------------------------
    data_handler = DataHandler(socketio=socketio, logger=app.logger, app_config=app.config)
    release_client = ReleaseClient(
        repo=app.config.get("GITHUB_REPO", "Dodelidoo-Labs/sonobarr"),
        user_agent=app.config.get("GITHUB_USER_AGENT", "sonobarr-app"),
        ttl_seconds=int(app.config.get("RELEASE_CACHE_TTL_SECONDS", 3600)),
        logger=app.logger,
    )

    app.extensions["data_handler"] = data_handler
    app.extensions["release_client"] = release_client

    @app.context_processor
    def inject_footer_metadata() -> Dict[str, Any]:
        current_version = (app.config.get("APP_VERSION") or "unknown").strip() or "unknown"
        release_info = release_client.fetch_latest()
        latest_version = release_info.get("tag_name")
        update_available: Optional[bool]
        status_color = "muted"

        if latest_version and current_version.lower() not in {"", "unknown", "dev", "development"}:
            update_available = latest_version != current_version
            status_color = "danger" if update_available else "success"
        elif latest_version:
            update_available = None
        else:
            update_available = None

        if release_info.get("error") and not latest_version:
            status_color = "muted"

        status_label = "Update status unavailable"
        if update_available is True and latest_version:
            status_label = f"Update available · {latest_version}"
        elif update_available is False:
            status_label = "Up to date"
        elif update_available is None and latest_version:
            status_label = f"Latest release: {latest_version}"

        return {
            "repo_url": app.config.get("REPO_URL", "https://github.com/Dodelidoo-Labs/sonobarr"),
            "app_version": current_version,
            "latest_release_version": latest_version,
            "latest_release_url": release_info.get("html_url")
            or "https://github.com/Dodelidoo-Labs/sonobarr/releases",
            "update_available": update_available,
            "update_status_color": status_color,
            "update_status_label": status_label,
        }

    # Blueprints ------------------------------------------------------
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)

    # Socket.IO -------------------------------------------------------
    register_socketio_handlers(socketio, data_handler)

    # Database initialisation ----------------------------------------
    with app.app_context():
        db.create_all()
        bootstrap_super_admin(app.logger, data_handler)

    return app


__all__ = ["create_app", "socketio"]
