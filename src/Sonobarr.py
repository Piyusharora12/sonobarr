from __future__ import annotations

import json
import logging
import os
import random
import secrets
import string
import threading
import time
import urllib.parse
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Dict, List, Optional

import musicbrainzngs
import pylast
import requests
from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_socketio import SocketIO, disconnect
from thefuzz import fuzz
from unidecode import unidecode

from .models import User, db


logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("sonobarr")

GITHUB_REPO = "Dodelidoo-Labs/sonobarr"
GITHUB_REPO_URL = f"https://github.com/{GITHUB_REPO}"
GITHUB_RELEASES_LATEST_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
RELEASE_CACHE_TTL_SECONDS = 60 * 60  # 1 hour
_release_cache: Dict[str, Any] = {
    "fetched_at": 0.0,
    "tag_name": None,
    "html_url": None,
    "error": None,
}
_release_cache_lock = threading.Lock()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, os.pardir))
CONFIG_DIR = os.path.join(ROOT_DIR, "config")
os.makedirs(CONFIG_DIR, exist_ok=True)
DB_PATH = os.path.join(CONFIG_DIR, "app.db")

def get_env_value(key: str, default: Optional[str] = None) -> Optional[str]:
    """Retrieve an environment variable preferring lowercase naming."""
    candidates: List[str] = []
    for candidate in (key, key.lower(), key.upper()):
        if candidate not in candidates:
            candidates.append(candidate)
    for candidate in candidates:
        value = os.environ.get(candidate)
        if value not in (None, ""):
            return value
    return default


app = Flask(__name__)
secret_key = get_env_value("secret_key")
if not secret_key:
    raise RuntimeError(
        "SECRET_KEY environment variable is required. Set 'secret_key' (preferred) or 'SECRET_KEY'."
    )
app.config["SECRET_KEY"] = secret_key
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
app.config["APP_VERSION"] = get_env_value("release_version", "unknown") or "unknown"
app.config["REPO_URL"] = GITHUB_REPO_URL


def get_latest_release_info(force: bool = False) -> Dict[str, Any]:
    now = time.time()
    with _release_cache_lock:
        age = now - _release_cache["fetched_at"]
        if not force and age < RELEASE_CACHE_TTL_SECONDS and (
            _release_cache["tag_name"] or _release_cache["error"]
        ):
            return dict(_release_cache)

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "sonobarr-app",
    }

    info: Dict[str, Any] = {
        "tag_name": None,
        "html_url": None,
        "error": None,
        "fetched_at": now,
    }

    try:
        response = requests.get(GITHUB_RELEASES_LATEST_URL, headers=headers, timeout=5)
        if response.status_code == 200:
            payload = response.json()
            info["tag_name"] = (payload.get("tag_name") or payload.get("name") or "").strip() or None
            info["html_url"] = payload.get("html_url") or f"{GITHUB_REPO_URL}/releases"
        else:
            info["error"] = f"GitHub API returned status {response.status_code}"
    except Exception as exc:  # pragma: no cover - network errors
        info["error"] = str(exc)

    if not info.get("html_url"):
        info["html_url"] = f"{GITHUB_REPO_URL}/releases"

    with _release_cache_lock:
        _release_cache.update(info)

    return dict(info)


@app.context_processor
def inject_footer_metadata() -> Dict[str, Any]:
    current_version = (app.config.get("APP_VERSION") or "unknown").strip() or "unknown"
    release_info = get_latest_release_info()
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
        "repo_url": app.config.get("REPO_URL", GITHUB_REPO_URL),
        "app_version": current_version,
        "latest_release_version": latest_version,
        "latest_release_url": release_info.get("html_url") or f"{GITHUB_REPO_URL}/releases",
        "update_available": update_available,
        "update_status_color": status_color,
        "update_status_label": status_label,
    }

db.init_app(app)
socketio = SocketIO(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access Sonobarr."


@login_manager.user_loader
def load_user(user_id: str) -> Optional[User]:
    if not user_id:
        return None
    try:
        return User.query.get(int(user_id))
    except (TypeError, ValueError):
        return None


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


@dataclass
class SessionState:
    sid: str
    user_id: Optional[int]
    recommended_artists: List[dict] = field(default_factory=list)
    lidarr_items: List[dict] = field(default_factory=list)
    cleaned_lidarr_items: List[str] = field(default_factory=list)
    artists_to_use_in_search: List[str] = field(default_factory=list)
    similar_artist_candidates: List[dict] = field(default_factory=list)
    similar_artist_batch_pointer: int = 0
    initial_batch_sent: bool = False
    stop_event: threading.Event = field(default_factory=threading.Event)
    search_lock: threading.Lock = field(default_factory=threading.Lock)
    running: bool = False

    def __post_init__(self) -> None:
        self.stop_event.set()

    def prepare_for_search(self) -> None:
        self.recommended_artists.clear()
        self.artists_to_use_in_search.clear()
        self.similar_artist_candidates.clear()
        self.similar_artist_batch_pointer = 0
        self.initial_batch_sent = False
        self.stop_event.clear()
        self.running = True

    def mark_stopped(self) -> None:
        self.stop_event.set()
        self.running = False


class DataHandler:
    def __init__(self) -> None:
        self.sonobarr_logger = logger
        self.musicbrainzngs_logger = logging.getLogger("musicbrainzngs")
        self.musicbrainzngs_logger.setLevel("WARNING")
        self.pylast_logger = logging.getLogger("pylast")
        self.pylast_logger.setLevel("WARNING")

        app_name_text = os.path.basename(__file__).replace(".py", "")
        release_version = get_env_value("release_version", "unknown") or "unknown"
        self.sonobarr_logger.warning(f"{'*' * 50}\n")
        self.sonobarr_logger.warning(f"{app_name_text} Version: {release_version}\n")
        self.sonobarr_logger.warning(f"{'*' * 50}")

        self.sessions: Dict[str, SessionState] = {}
        self.sessions_lock = threading.Lock()
        self.cache_lock = threading.Lock()
        self.cached_lidarr_names: List[str] = []
        self.cached_cleaned_lidarr_names: List[str] = []

        self.config_folder = CONFIG_DIR
        self.settings_config_file = os.path.join(self.config_folder, "settings_config.json")
        self.similar_artist_batch_size = 10

        self.load_environ_or_config_settings()

    def _env(self, key: str) -> str:
        # Prefer existing lowercase usage, but accept UPPERCASE too
        value = get_env_value(key)
        return value if value is not None else ""

    # Session helpers -----------------------------------------------------
    def ensure_session(self, sid: str, user_id: Optional[int] = None) -> SessionState:
        with self.sessions_lock:
            session = self.sessions.get(sid)
            if session is None:
                session = SessionState(sid=sid, user_id=user_id)
                self.sessions[sid] = session
            elif user_id is not None:
                session.user_id = user_id
            return session

    def get_session_if_exists(self, sid: str) -> Optional[SessionState]:
        with self.sessions_lock:
            return self.sessions.get(sid)

    def remove_session(self, sid: str) -> None:
        with self.sessions_lock:
            session = self.sessions.pop(sid, None)
        if session:
            session.mark_stopped()

    # Cache helpers -------------------------------------------------------
    def _copy_cached_lidarr_items(self, checked: bool = False) -> List[dict]:
        with self.cache_lock:
            return [{"name": name, "checked": checked} for name in self.cached_lidarr_names]

    def _copy_cached_cleaned_names(self) -> List[str]:
        with self.cache_lock:
            return list(self.cached_cleaned_lidarr_names)

    # Socket helpers ------------------------------------------------------
    def connection(self, sid: str, user_id: Optional[int]) -> None:
        session = self.ensure_session(sid, user_id)
        if session.recommended_artists:
            socketio.emit("more_artists_loaded", session.recommended_artists, room=sid)
        if session.lidarr_items:
            payload = {
                "Status": "Success",
                "Data": session.lidarr_items,
                "Running": session.running,
            }
            socketio.emit("lidarr_sidebar_update", payload, room=sid)

    def side_bar_opened(self, sid: str) -> None:
        session = self.ensure_session(sid)
        if not session.lidarr_items:
            items = self._copy_cached_lidarr_items()
            if items:
                session.lidarr_items = items
                session.cleaned_lidarr_items = self._copy_cached_cleaned_names()
        if session.lidarr_items:
            payload = {
                "Status": "Success",
                "Data": session.lidarr_items,
                "Running": session.running,
            }
            socketio.emit("lidarr_sidebar_update", payload, room=sid)

    # Lidarr interactions -------------------------------------------------
    def get_artists_from_lidarr(self, sid: str, checked: bool = False) -> None:
        session = self.ensure_session(sid)
        try:
            endpoint = f"{self.lidarr_address}/api/v1/artist"
            headers = {"X-Api-Key": self.lidarr_api_key}
            response = requests.get(endpoint, headers=headers, timeout=self.lidarr_api_timeout)
            if response.status_code == 200:
                full_list = response.json()
                names = [unidecode(artist["artistName"], replace_str=" ") for artist in full_list]
                names.sort(key=lambda value: value.lower())

                with self.cache_lock:
                    self.cached_lidarr_names = names
                    self.cached_cleaned_lidarr_names = [name.lower() for name in names]

                session.lidarr_items = [{"name": name, "checked": checked} for name in names]
                session.cleaned_lidarr_items = self._copy_cached_cleaned_names()
                status = "Success"
                data = session.lidarr_items
            else:
                status = "Error"
                data = response.text
            payload = {
                "Status": status,
                "Code": response.status_code if status == "Error" else None,
                "Data": data,
                "Running": session.running,
            }
        except Exception as exc:
            self.sonobarr_logger.error(f"Getting Artist Error: {exc}")
            payload = {
                "Status": "Error",
                "Code": 500,
                "Data": str(exc),
                "Running": session.running,
            }
        socketio.emit("lidarr_sidebar_update", payload, room=sid)

    # Discovery -----------------------------------------------------------
    def start(self, sid: str, selected_artists: List[str]) -> None:
        session = self.ensure_session(sid)
        if not session.lidarr_items:
            cached = self._copy_cached_lidarr_items()
            if cached:
                session.lidarr_items = cached
                session.cleaned_lidarr_items = self._copy_cached_cleaned_names()
            else:
                self.get_artists_from_lidarr(sid)
                session = self.ensure_session(sid)
                if not session.lidarr_items:
                    return

        selection = set(selected_artists or [])
        session.prepare_for_search()
        session.artists_to_use_in_search = []

        for item in session.lidarr_items:
            is_selected = item["name"] in selection
            item["checked"] = is_selected
            if is_selected:
                session.artists_to_use_in_search.append(item["name"])

        if not session.artists_to_use_in_search:
            session.mark_stopped()
            payload = {
                "Status": "Error",
                "Code": "No Lidarr Artists Selected",
                "Data": session.lidarr_items,
                "Running": session.running,
            }
            socketio.emit("lidarr_sidebar_update", payload, room=sid)
            socketio.emit(
                "new_toast_msg",
                {
                    "title": "Selection required",
                    "message": "Choose at least one Lidarr artist to start.",
                },
                room=sid,
            )
            return

        socketio.emit("clear", room=sid)
        payload = {
            "Status": "Success",
            "Data": session.lidarr_items,
            "Running": session.running,
        }
        socketio.emit("lidarr_sidebar_update", payload, room=sid)

        self.prepare_similar_artist_candidates(session)
        with session.search_lock:
            self.load_similar_artist_batch(session, sid)

    def stop(self, sid: str) -> None:
        session = self.ensure_session(sid)
        session.mark_stopped()
        payload = {
            "Status": "Success",
            "Data": session.lidarr_items,
            "Running": session.running,
        }
        socketio.emit("lidarr_sidebar_update", payload, room=sid)

    def prepare_similar_artist_candidates(self, session: SessionState) -> None:
        session.similar_artist_candidates = []
        session.similar_artist_batch_pointer = 0
        session.initial_batch_sent = False

        lfm = pylast.LastFMNetwork(
            api_key=self.last_fm_api_key,
            api_secret=self.last_fm_api_secret,
        )

        seen_candidates = set()
        for artist_name in session.artists_to_use_in_search:
            try:
                chosen_artist = lfm.get_artist(artist_name)
                related_artists = chosen_artist.get_similar()
                for related_artist in related_artists:
                    cleaned_artist = unidecode(related_artist.item.name).lower()
                    if cleaned_artist in session.cleaned_lidarr_items or cleaned_artist in seen_candidates:
                        continue
                    seen_candidates.add(cleaned_artist)
                    raw_match = getattr(related_artist, "match", None)
                    try:
                        match_score = float(raw_match) if raw_match is not None else None
                    except (TypeError, ValueError):
                        match_score = None
                    session.similar_artist_candidates.append(
                        {
                            "artist": related_artist,
                            "match": match_score,
                        }
                    )
            except Exception:
                continue
            if len(session.similar_artist_candidates) >= 500:
                break

        def sort_key(item):
            match_value = item["match"] if item["match"] is not None else -1.0
            return (-match_value, unidecode(item["artist"].item.name).lower())

        session.similar_artist_candidates.sort(key=sort_key)

    def load_similar_artist_batch(self, session: SessionState, sid: str) -> None:
        if session.stop_event.is_set():
            session.mark_stopped()
            return

        batch_size = max(1, int(self.similar_artist_batch_size))
        batch_start = session.similar_artist_batch_pointer
        batch_end = batch_start + batch_size
        batch = session.similar_artist_candidates[batch_start:batch_end]

        if not batch:
            session.mark_stopped()
            socketio.emit("load_more_complete", {"hasMore": False}, room=sid)
            return

        lfm_network = pylast.LastFMNetwork(
            api_key=self.last_fm_api_key,
            api_secret=self.last_fm_api_secret,
        )

        # Stream results: emit each artist as soon as it’s ready
        for candidate in batch:
            if session.stop_event.is_set():
                break
            related_artist = candidate["artist"]
            similarity_score = candidate.get("match")
            try:
                artist_obj = lfm_network.get_artist(related_artist.item.name)
                genres = ", ".join(
                    [tag.item.get_name().title() for tag in artist_obj.get_top_tags()[:5]]
                ) or "Unknown Genre"
                try:
                    listeners = artist_obj.get_listener_count() or 0
                except Exception:
                    listeners = 0
                try:
                    play_count = artist_obj.get_playcount() or 0
                except Exception:
                    play_count = 0

                img_link = None
                try:
                    endpoint = "https://api.deezer.com/search/artist"
                    params = {"q": related_artist.item.name}
                    response = requests.get(endpoint, params=params, timeout=10)
                    data = response.json()
                    if data.get("data"):
                        artist_info = data["data"][0]
                        img_link = (
                            artist_info.get("picture_xl")
                            or artist_info.get("picture_large")
                            or artist_info.get("picture_medium")
                            or artist_info.get("picture")
                        )
                except Exception:
                    img_link = None

                if similarity_score is not None:
                    clamped_similarity = max(0.0, min(1.0, similarity_score))
                    similarity_label = f"Similarity: {clamped_similarity * 100:.1f}%"
                else:
                    clamped_similarity = None
                    similarity_label = None

                artist_payload = {
                    "Name": related_artist.item.name,
                    "Genre": genres,
                    "Status": "",
                    "Img_Link": img_link or "https://placehold.co/512x512?text=No+Image",
                    "Popularity": f"Play Count: {self.format_numbers(play_count)}",
                    "Followers": f"Listeners: {self.format_numbers(listeners)}",
                    "SimilarityScore": clamped_similarity,
                    "Similarity": similarity_label,
                }

                # Keep server-side state and emit immediately (single-element array)
                session.recommended_artists.append(artist_payload)
                socketio.emit("more_artists_loaded", [artist_payload], room=sid)
            except Exception as exc:
                self.sonobarr_logger.error(f"Error loading artist {related_artist.item.name}: {exc}")

        session.similar_artist_batch_pointer += len(batch)
        has_more = session.similar_artist_batch_pointer < len(session.similar_artist_candidates)
        event_name = "initial_load_complete" if not session.initial_batch_sent else "load_more_complete"
        socketio.emit(event_name, {"hasMore": has_more}, room=sid)
        session.initial_batch_sent = True
        if not has_more:
            session.mark_stopped()

    def find_similar_artists(self, sid: str) -> None:
        session = self.ensure_session(sid)
        if session.stop_event.is_set():
            return
        with session.search_lock:
            if session.stop_event.is_set():
                return
            if session.similar_artist_batch_pointer < len(session.similar_artist_candidates):
                self.load_similar_artist_batch(session, sid)
            else:
                socketio.emit(
                    "new_toast_msg",
                    {
                        "title": "No More Artists",
                        "message": "No more similar artists to load.",
                    },
                    room=sid,
                )
                session.mark_stopped()

    # Lidarr artist creation ----------------------------------------------
    def add_artists(self, sid: str, raw_artist_name: str) -> None:
        session = self.ensure_session(sid)
        artist_name = urllib.parse.unquote(raw_artist_name)
        artist_folder = artist_name.replace("/", " ")
        status = "Failed to Add"

        try:
            musicbrainzngs.set_useragent(self.app_name, self.app_rev, self.app_url)
            mbid = self.get_mbid_from_musicbrainz(artist_name)

            if mbid:
                lidarr_url = f"{self.lidarr_address}/api/v1/artist"
                headers = {"X-Api-Key": self.lidarr_api_key}
                payload = {
                    "ArtistName": artist_name,
                    "qualityProfileId": self.quality_profile_id,
                    "metadataProfileId": self.metadata_profile_id,
                    "path": os.path.join(self.root_folder_path, artist_folder, ""),
                    "rootFolderPath": self.root_folder_path,
                    "foreignArtistId": mbid,
                    "monitored": True,
                    "addOptions": {
                        "searchForMissingAlbums": self.search_for_missing_albums,
                    },
                }

                if self.dry_run_adding_to_lidarr:
                    response = None
                    response_status = 201
                else:
                    response = requests.post(
                        lidarr_url,
                        headers=headers,
                        json=payload,
                        timeout=self.lidarr_api_timeout,
                    )
                    response_status = response.status_code

                if response_status == 201:
                    self.sonobarr_logger.info(
                        "Artist '%s' added successfully to Lidarr.", artist_name
                    )
                    status = "Added"
                    session.lidarr_items.append({"name": artist_name, "checked": False})
                    session.cleaned_lidarr_items.append(unidecode(artist_name).lower())
                    with self.cache_lock:
                        if artist_name not in self.cached_lidarr_names:
                            self.cached_lidarr_names.append(artist_name)
                            self.cached_cleaned_lidarr_names.append(unidecode(artist_name).lower())
                else:
                    if self.dry_run_adding_to_lidarr:
                        response_body = "Dry-run mode: no request sent."
                        error_payload = None
                    elif response is not None:
                        response_body = response.text.strip()
                        try:
                            error_payload = response.json()
                        except ValueError:
                            error_payload = None
                    else:
                        response_body = "No response object returned."
                        error_payload = None

                    self.sonobarr_logger.error(
                        "Failed to add artist '%s' to Lidarr (status=%s). Body: %s",
                        artist_name,
                        response_status,
                        response_body,
                    )
                    if error_payload is not None:
                        self.sonobarr_logger.error("Lidarr error payload: %s", error_payload)

                    error_message: str
                    if isinstance(error_payload, list) and error_payload:
                        error_message = error_payload[0].get(
                            "errorMessage", "No Error Message Returned"
                        )
                    elif isinstance(error_payload, dict):
                        error_message = (
                            error_payload.get("errorMessage")
                            or error_payload.get("message")
                            or "No Error Message Returned"
                        )
                    else:
                        error_message = response_body or "Error Unknown"

                    self.sonobarr_logger.error("Lidarr error message: %s", error_message)

                    if "already been added" in error_message or "configured for an existing artist" in error_message:
                        status = "Already in Lidarr"
                    elif "Invalid Path" in error_message:
                        status = "Invalid Path"
                        self.sonobarr_logger.info(
                            "Path '%s' reported invalid by Lidarr.",
                            os.path.join(self.root_folder_path, artist_folder, ""),
                        )
                    else:
                        status = "Failed to Add"
            else:
                self.sonobarr_logger.warning(
                    "No MusicBrainz match found for '%s'; cannot add to Lidarr.", artist_name
                )
                socketio.emit(
                    "new_toast_msg",
                    {
                        "title": "Failed to add Artist",
                        "message": f"No Matching Artist for: '{artist_name}' in MusicBrainz.",
                    },
                    room=sid,
                )

        except Exception as exc:
            self.sonobarr_logger.exception(
                "Unexpected error while adding '%s' to Lidarr", artist_name
            )
            socketio.emit(
                "new_toast_msg",
                {
                    "title": "Failed to add Artist",
                    "message": f"Error adding '{artist_name}': {exc}",
                },
                room=sid,
            )
        finally:
            for item in session.recommended_artists:
                if item["Name"] == artist_name:
                    item["Status"] = status
                    socketio.emit("refresh_artist", item, room=sid)
                    break

    # Settings -------------------------------------------------------------
    def load_settings(self, sid: str) -> None:
        try:
            data = {
                "lidarr_address": self.lidarr_address,
                "lidarr_api_key": self.lidarr_api_key,
                "root_folder_path": self.root_folder_path,
                "youtube_api_key": self.youtube_api_key,
                "similar_artist_batch_size": self.similar_artist_batch_size,
            }
            socketio.emit("settingsLoaded", data, room=sid)
        except Exception as exc:
            self.sonobarr_logger.error(f"Failed to load settings: {exc}")

    def update_settings(self, data: dict) -> None:
        try:
            self.lidarr_address = data["lidarr_address"].strip()
            self.lidarr_api_key = data["lidarr_api_key"].strip()
            self.root_folder_path = data["root_folder_path"].strip()
            self.youtube_api_key = data.get("youtube_api_key", "").strip()
            batch_size = data.get("similar_artist_batch_size")
            if batch_size is not None:
                try:
                    batch_value = int(batch_size)
                except (TypeError, ValueError):
                    batch_value = self.similar_artist_batch_size
                if batch_value > 0:
                    self.similar_artist_batch_size = batch_value
        except Exception as exc:
            self.sonobarr_logger.error(f"Failed to update settings: {exc}")

    # Preview --------------------------------------------------------------
    def preview(self, sid: str, raw_artist_name: str) -> None:
        artist_name = urllib.parse.unquote(raw_artist_name)
        try:
            preview_info: dict | str
            biography = None
            lfm = pylast.LastFMNetwork(
                api_key=self.last_fm_api_key,
                api_secret=self.last_fm_api_secret,
            )
            search_results = lfm.search_for_artist(artist_name)
            artists = search_results.get_next_page()
            cleaned_artist_name = unidecode(artist_name).lower()
            for artist_obj in artists:
                match_ratio = fuzz.ratio(cleaned_artist_name, artist_obj.name.lower())
                decoded_match_ratio = fuzz.ratio(
                    unidecode(cleaned_artist_name), unidecode(artist_obj.name.lower())
                )
                if match_ratio > 90 or decoded_match_ratio > 90:
                    biography = artist_obj.get_bio_content()
                    preview_info = {
                        "artist_name": artist_obj.name,
                        "biography": biography,
                    }
                    break
            else:
                preview_info = f"No Artist match for: {artist_name}"
                self.sonobarr_logger.error(preview_info)

            if biography is None:
                preview_info = f"No Biography available for: {artist_name}"
                self.sonobarr_logger.error(preview_info)

        except Exception as exc:
            preview_info = {"error": f"Error retrieving artist bio: {exc}"}
            self.sonobarr_logger.error(preview_info)

        socketio.emit("lastfm_preview", preview_info, room=sid)

    def prehear(self, sid: str, raw_artist_name: str) -> None:
        artist_name = urllib.parse.unquote(raw_artist_name)
        lfm = pylast.LastFMNetwork(
            api_key=self.last_fm_api_key,
            api_secret=self.last_fm_api_secret,
        )
        yt_key = (self.youtube_api_key or "").strip()
        result: dict[str, str] = {"error": "No sample found"}
        top_tracks = []
        try:
            artist = lfm.get_artist(artist_name)
            top_tracks = artist.get_top_tracks(limit=10)
        except Exception as exc:
            self.sonobarr_logger.error(f"LastFM error: {exc}")

        def attempt_youtube(track_name: str) -> Optional[dict[str, str]]:
            if not yt_key:
                return None
            query = f"{artist_name} {track_name}"
            yt_url = (
                "https://www.googleapis.com/youtube/v3/search?part=snippet"
                f"&q={requests.utils.quote(query)}&key={yt_key}&type=video&maxResults=1"
            )
            try:
                yt_resp = requests.get(yt_url, timeout=10)
                yt_resp.raise_for_status()
            except Exception as exc:
                self.sonobarr_logger.error(f"YouTube search failed: {exc}")
                return None
            yt_items = yt_resp.json().get("items", [])
            if not yt_items:
                return None
            video_id = yt_items[0]["id"]["videoId"]
            return {
                "videoId": video_id,
                "track": track_name,
                "artist": artist_name,
                "source": "youtube",
            }

        def attempt_itunes(track_name: Optional[str]) -> Optional[dict[str, str]]:
            search_term = f"{artist_name} {track_name}" if track_name else artist_name
            params = {
                "term": search_term,
                "entity": "musicTrack",
                "limit": 5,
                "media": "music",
            }
            try:
                resp = requests.get("https://itunes.apple.com/search", params=params, timeout=10)
                resp.raise_for_status()
            except Exception as exc:
                self.sonobarr_logger.error(f"iTunes lookup failed: {exc}")
                return None
            for entry in resp.json().get("results", []):
                preview_url = entry.get("previewUrl")
                if not preview_url:
                    continue
                return {
                    "previewUrl": preview_url,
                    "track": entry.get("trackName") or (track_name or artist_name),
                    "artist": entry.get("artistName") or artist_name,
                    "source": "itunes",
                }
            return None

        try:
            if yt_key:
                for track in top_tracks:
                    track_name = track.item.title
                    candidate = attempt_youtube(track_name)
                    if candidate:
                        result = candidate
                        break
                    time.sleep(0.2)

            if isinstance(result, dict) and not result.get("previewUrl") and not result.get("videoId"):
                for track in top_tracks:
                    track_name = track.item.title
                    candidate = attempt_itunes(track_name)
                    if candidate:
                        result = candidate
                        break

            if isinstance(result, dict) and not result.get("previewUrl") and not result.get("videoId"):
                fallback_candidate = attempt_itunes(None)
                if fallback_candidate:
                    result = fallback_candidate
        except Exception as exc:
            self.sonobarr_logger.error(f"Prehear error: {exc}")
            result = {"error": str(exc)}

        socketio.emit("prehear_result", result, room=sid)

    # Utilities ------------------------------------------------------------
    def format_numbers(self, count: int) -> str:
        if count >= 1_000_000:
            return f"{count / 1_000_000:.1f}M"
        if count >= 1_000:
            return f"{count / 1_000:.1f}K"
        return str(count)

    def save_config_to_file(self) -> None:
        try:
            with open(self.settings_config_file, "w") as json_file:
                json.dump(
                    {
                        "lidarr_address": self.lidarr_address,
                        "lidarr_api_key": self.lidarr_api_key,
                        "root_folder_path": self.root_folder_path,
                        "fallback_to_top_result": self.fallback_to_top_result,
                        "lidarr_api_timeout": float(self.lidarr_api_timeout),
                        "quality_profile_id": self.quality_profile_id,
                        "metadata_profile_id": self.metadata_profile_id,
                        "search_for_missing_albums": self.search_for_missing_albums,
                        "dry_run_adding_to_lidarr": self.dry_run_adding_to_lidarr,
                        "app_name": self.app_name,
                        "app_rev": self.app_rev,
                        "app_url": self.app_url,
                        "last_fm_api_key": self.last_fm_api_key,
                        "last_fm_api_secret": self.last_fm_api_secret,
                        "auto_start": self.auto_start,
                        "auto_start_delay": self.auto_start_delay,
                        "youtube_api_key": self.youtube_api_key,
                        "similar_artist_batch_size": self.similar_artist_batch_size,
                    },
                    json_file,
                    indent=4,
                )
        except Exception as exc:
            self.sonobarr_logger.error(f"Error Saving Config: {exc}")

    def get_mbid_from_musicbrainz(self, artist_name: str) -> Optional[str]:
        result = musicbrainzngs.search_artists(artist=artist_name)
        mbid = None

        if "artist-list" in result:
            artists = result["artist-list"]

            for artist in artists:
                match_ratio = fuzz.ratio(artist_name.lower(), artist["name"].lower())
                decoded_match_ratio = fuzz.ratio(
                    unidecode(artist_name.lower()),
                    unidecode(artist["name"].lower()),
                )
                if match_ratio > 90 or decoded_match_ratio > 90:
                    mbid = artist["id"]
                    self.sonobarr_logger.info(
                        f"Artist '{artist_name}' matched '{artist['name']}' with MBID: {mbid}"
                    )
                    break
            else:
                if self.fallback_to_top_result and artists:
                    mbid = artists[0]["id"]
                    self.sonobarr_logger.info(
                        f"Artist '{artist_name}' matched '{artists[0]['name']}' with MBID: {mbid}"
                    )

        return mbid

    def load_environ_or_config_settings(self) -> None:
        default_settings = {
            "lidarr_address": "http://192.168.1.1:8686",
            "lidarr_api_key": "",
            "root_folder_path": "/data/media/music/",
            "fallback_to_top_result": False,
            "lidarr_api_timeout": 120.0,
            "quality_profile_id": 1,
            "metadata_profile_id": 1,
            "search_for_missing_albums": False,
            "dry_run_adding_to_lidarr": False,
            "app_name": "Sonobarr",
            "app_rev": "0.10",
            "app_url": "http://" + "".join(random.choices(string.ascii_lowercase, k=10)) + ".com",
            "last_fm_api_key": "",
            "last_fm_api_secret": "",
            "auto_start": False,
            "auto_start_delay": 60,
            "youtube_api_key": "",
            "similar_artist_batch_size": 10,
            "sonobarr_superadmin_username": "admin",
            "sonobarr_superadmin_password": "",
            "sonobarr_superadmin_display_name": "Super Admin",
            "sonobarr_superadmin_reset": "false",
        }

        self.lidarr_address = self._env("lidarr_address")
        self.lidarr_api_key = self._env("lidarr_api_key")
        self.youtube_api_key = self._env("youtube_api_key")
        self.root_folder_path = self._env("root_folder_path")

        fallback_to_top_result = self._env("fallback_to_top_result")
        self.fallback_to_top_result = (
            fallback_to_top_result.lower() == "true" if fallback_to_top_result != "" else ""
        )

        lidarr_api_timeout = self._env("lidarr_api_timeout")
        self.lidarr_api_timeout = float(lidarr_api_timeout) if lidarr_api_timeout else ""

        quality_profile_id = self._env("quality_profile_id")
        self.quality_profile_id = int(quality_profile_id) if quality_profile_id else ""

        metadata_profile_id = self._env("metadata_profile_id")
        self.metadata_profile_id = int(metadata_profile_id) if metadata_profile_id else ""

        search_for_missing_albums = self._env("search_for_missing_albums")
        self.search_for_missing_albums = (
            search_for_missing_albums.lower() == "true" if search_for_missing_albums != "" else ""
        )

        dry_run_adding_to_lidarr = self._env("dry_run_adding_to_lidarr")
        self.dry_run_adding_to_lidarr = (
            dry_run_adding_to_lidarr.lower() == "true" if dry_run_adding_to_lidarr != "" else ""
        )

        self.app_name = self._env("app_name")
        self.app_rev = self._env("app_rev")
        self.app_url = self._env("app_url")
        self.last_fm_api_key = self._env("last_fm_api_key")
        self.last_fm_api_secret = self._env("last_fm_api_secret")

        auto_start = self._env("auto_start")
        self.auto_start = auto_start.lower() == "true" if auto_start != "" else ""

        auto_start_delay = self._env("auto_start_delay")
        self.auto_start_delay = float(auto_start_delay) if auto_start_delay else ""

        similar_artist_batch_size = self._env("similar_artist_batch_size")
        if similar_artist_batch_size:
            self.similar_artist_batch_size = similar_artist_batch_size

        superadmin_username = self._env("sonobarr_superadmin_username")
        superadmin_password = self._env("sonobarr_superadmin_password")
        superadmin_display_name = self._env("sonobarr_superadmin_display_name")
        superadmin_reset = self._env("sonobarr_superadmin_reset")

        self.superadmin_username = (superadmin_username or "").strip() or default_settings["sonobarr_superadmin_username"]
        self.superadmin_password = (superadmin_password or "").strip() or default_settings["sonobarr_superadmin_password"]
        self.superadmin_display_name = (superadmin_display_name or "").strip() or default_settings["sonobarr_superadmin_display_name"]
        reset_raw = (superadmin_reset or "").strip().lower()
        self.superadmin_reset_flag = reset_raw in {"1", "true", "yes"}

        try:
            if os.path.exists(self.settings_config_file):
                self.sonobarr_logger.info("Loading Config via file")
                with open(self.settings_config_file, "r") as json_file:
                    ret = json.load(json_file)
                    for key in ret:
                        if getattr(self, key, "") == "":
                            setattr(self, key, ret[key])
        except Exception as exc:
            self.sonobarr_logger.error(f"Error Loading Config: {exc}")

        for key, value in default_settings.items():
            if getattr(self, key, "") == "":
                setattr(self, key, value)

        try:
            self.similar_artist_batch_size = int(self.similar_artist_batch_size)
        except (TypeError, ValueError):
            self.similar_artist_batch_size = default_settings["similar_artist_batch_size"]
        if self.similar_artist_batch_size <= 0:
            self.similar_artist_batch_size = default_settings["similar_artist_batch_size"]

        try:
            self.lidarr_api_timeout = float(self.lidarr_api_timeout)
        except (TypeError, ValueError):
            self.lidarr_api_timeout = float(default_settings["lidarr_api_timeout"])

        self.save_config_to_file()


data_handler = DataHandler()


def bootstrap_super_admin() -> None:
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


with app.app_context():
    db.create_all()
    bootstrap_super_admin()


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if not username or not password:
            flash("Username and password are required.", "danger")
        else:
            user = User.query.filter_by(username=username).first()
            if not user or not user.check_password(password):
                flash("Invalid username or password.", "danger")
            elif not user.is_active:
                flash("Account is disabled.", "danger")
            else:
                login_user(user)
                flash("Welcome to Sonobarr!", "success")
                return redirect(url_for("home"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("login"))


@app.route("/")
@login_required
def home():
    return render_template("base.html")


@app.route("/profile", methods=["GET", "POST"])
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
        errors: List[str] = []

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
        return redirect(url_for("profile"))

    return render_template("profile.html")


@app.route("/admin/users", methods=["GET", "POST"])
@login_required
@admin_required
def admin_users():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "create":
            username = (request.form.get("username") or "").strip()
            password = request.form.get("password") or ""
            confirm_password = request.form.get("confirm_password") or ""
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
        return redirect(url_for("admin_users"))

    users = User.query.order_by(User.username.asc()).all()
    return render_template("admin_users.html", users=users)


# Socket.IO events --------------------------------------------------------
@socketio.on("connect")
def handle_connect():
    if not current_user.is_authenticated:
        return False
    sid = request.sid
    try:
        user_id = int(current_user.get_id()) if current_user.get_id() is not None else None
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
def handle_start_req(selected_artists):
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
def handle_add_artist(raw_artist_name):
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
def handle_update_settings(payload):
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
def handle_preview(raw_artist_name):
    if not current_user.is_authenticated:
        disconnect()
        return
    data_handler.preview(request.sid, raw_artist_name)


@socketio.on("prehear_req")
def handle_prehear(raw_artist_name):
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


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
