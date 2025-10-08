from __future__ import annotations

import threading
from typing import Any

from flask import request
from flask_login import current_user
from flask_socketio import SocketIO, disconnect


def register_socketio_handlers(socketio: SocketIO, data_handler) -> None:
    @socketio.on("connect")
    def handle_connect():
        if not current_user.is_authenticated:
            return False
        sid = request.sid
        try:
            identifier = current_user.get_id()
            user_id = int(identifier) if identifier is not None else None
        except (TypeError, ValueError):
            user_id = None
        data_handler.connection(sid, user_id)

    @socketio.on("disconnect")
    def handle_disconnect():
        data_handler.remove_session(request.sid)

    @socketio.on("side_bar_opened")
    def handle_side_bar_opened():
        if not current_user.is_authenticated:
            disconnect()
            return
        data_handler.side_bar_opened(request.sid)

    @socketio.on("get_lidarr_artists")
    def handle_get_lidarr_artists():
        if not current_user.is_authenticated:
            disconnect()
            return
        sid = request.sid

        thread = threading.Thread(
            target=data_handler.get_artists_from_lidarr,
            args=(sid,),
            name=f"LidarrFetch-{sid}",
            daemon=True,
        )
        thread.start()

    @socketio.on("start_req")
    def handle_start_req(selected_artists: Any):
        if not current_user.is_authenticated:
            disconnect()
            return
        sid = request.sid
        selected = list(selected_artists or [])

        thread = threading.Thread(
            target=data_handler.start,
            args=(sid, selected),
            name=f"StartSearch-{sid}",
            daemon=True,
        )
        thread.start()

    @socketio.on("stop_req")
    def handle_stop_req():
        if not current_user.is_authenticated:
            disconnect()
            return
        data_handler.stop(request.sid)

    @socketio.on("load_more_artists")
    def handle_load_more():
        if not current_user.is_authenticated:
            disconnect()
            return
        sid = request.sid
        thread = threading.Thread(
            target=data_handler.find_similar_artists,
            args=(sid,),
            name=f"LoadMore-{sid}",
            daemon=True,
        )
        thread.start()

    @socketio.on("adder")
    def handle_add_artist(raw_artist_name: str):
        if not current_user.is_authenticated:
            disconnect()
            return
        sid = request.sid
        thread = threading.Thread(
            target=data_handler.add_artists,
            args=(sid, raw_artist_name),
            name=f"AddArtist-{sid}",
            daemon=True,
        )
        thread.start()

    @socketio.on("load_settings")
    def handle_load_settings():
        if not current_user.is_authenticated:
            disconnect()
            return
        if not current_user.is_admin:
            socketio.emit(
                "new_toast_msg",
                {
                    "title": "Unauthorized",
                    "message": "Only administrators can view settings.",
                },
                room=request.sid,
            )
            return
        data_handler.load_settings(request.sid)

    @socketio.on("update_settings")
    def handle_update_settings(payload: dict):
        if not current_user.is_authenticated:
            disconnect()
            return
        if not current_user.is_admin:
            socketio.emit(
                "new_toast_msg",
                {
                    "title": "Unauthorized",
                    "message": "Only administrators can modify settings.",
                },
                room=request.sid,
            )
            return
        data_handler.update_settings(payload)
        data_handler.save_config_to_file()

    @socketio.on("preview_req")
    def handle_preview(raw_artist_name: str):
        if not current_user.is_authenticated:
            disconnect()
            return
        data_handler.preview(request.sid, raw_artist_name)

    @socketio.on("prehear_req")
    def handle_prehear(raw_artist_name: str):
        if not current_user.is_authenticated:
            disconnect()
            return
        sid = request.sid
        thread = threading.Thread(
            target=data_handler.prehear,
            args=(sid, raw_artist_name),
            name=f"Prehear-{sid}",
            daemon=True,
        )
        thread.start()
