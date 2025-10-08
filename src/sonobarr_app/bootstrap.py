from __future__ import annotations

import secrets

from .extensions import db
from .models import User


def bootstrap_super_admin(logger, data_handler) -> None:
    admin_count = User.query.filter_by(is_admin=True).count()
    reset_flag = data_handler.superadmin_reset_flag
    if admin_count > 0 and not reset_flag:
        return

    username = data_handler.superadmin_username
    password = data_handler.superadmin_password
    display_name = data_handler.superadmin_display_name
    generated_password = False
    if not password:
        password = secrets.token_urlsafe(16)
        generated_password = True

    existing = User.query.filter_by(username=username).first()
    if existing:
        existing.is_admin = True
        if password:
            existing.set_password(password)
        if display_name:
            existing.display_name = display_name
        action = "updated"
    else:
        admin = User(
            username=username,
            display_name=display_name,
            is_admin=True,
        )
        admin.set_password(password)
        db.session.add(admin)
        action = "created"

    db.session.commit()

    if generated_password:
        logger.warning(
            "Generated super-admin credentials. Username: %s Password: %s",
            username,
            password,
        )
    else:
        logger.info("Super-admin %s %s.", username, action)
