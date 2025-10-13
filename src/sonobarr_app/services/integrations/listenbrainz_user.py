from __future__ import annotations

import json
import urllib.parse
from dataclasses import dataclass
from typing import List, Sequence

import requests

LISTENBRAINZ_API_BASE = "https://api.listenbrainz.org/1"


class ListenBrainzIntegrationError(Exception):
    """Raised when a ListenBrainz API call fails."""


@dataclass
class ListenBrainzPlaylistArtists:
    artists: List[str]


class ListenBrainzUserService:
    def __init__(self, *, timeout: float = 10.0, session: requests.Session | None = None) -> None:
        self._timeout = max(1.0, float(timeout))
        self._session = session or requests.Session()

    def get_weekly_exploration_artists(self, username: str) -> ListenBrainzPlaylistArtists:
        username = (username or "").strip()
        if not username:
            return ListenBrainzPlaylistArtists(artists=[])

        playlist_id = self._find_weekly_exploration_playlist(username)
        if not playlist_id:
            return ListenBrainzPlaylistArtists(artists=[])

        artists = self._fetch_playlist_artists(playlist_id)
        return ListenBrainzPlaylistArtists(artists=artists)

    def _find_weekly_exploration_playlist(self, username: str) -> str | None:
        encoded_username = urllib.parse.quote(username)
        url = f"{LISTENBRAINZ_API_BASE}/user/{encoded_username}/playlists/createdfor"
        response = self._session.get(url, timeout=self._timeout)
        self._ensure_success(response)
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise ListenBrainzIntegrationError("Invalid response from ListenBrainz when listing playlists.") from exc

        playlists = payload.get("playlists") or []
        for playlist_entry in playlists:
            playlist = playlist_entry.get("playlist") or {}
            extension = playlist.get("extension") or {}
            playlist_ext = extension.get("https://musicbrainz.org/doc/jspf#playlist") or {}
            metadata = playlist_ext.get("additional_metadata") or {}
            algorithm_metadata = metadata.get("algorithm_metadata") or {}
            source_patch = (algorithm_metadata.get("source_patch") or "").strip().lower()
            if source_patch != "weekly-exploration":
                continue
            identifier = playlist.get("identifier")
            identifier_str = self._normalise_identifier(identifier)
            if identifier_str:
                return identifier_str
        return None

    def _fetch_playlist_artists(self, identifier: str) -> List[str]:
        url = f"{LISTENBRAINZ_API_BASE}/playlist/{identifier}"
        response = self._session.get(url, timeout=self._timeout)
        self._ensure_success(response)
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise ListenBrainzIntegrationError("Invalid response from ListenBrainz when loading playlist.") from exc

        playlist = payload.get("playlist") or {}
        tracks = playlist.get("track") or []
        artists: List[str] = []
        for track in tracks:
            for name in self._extract_track_artists(track):
                if name not in artists:
                    artists.append(name)
        return artists

    @staticmethod
    def _normalise_identifier(identifier: object) -> str:
        if isinstance(identifier, Sequence) and not isinstance(identifier, (str, bytes, bytearray)):
            if identifier:
                identifier = identifier[0]
        identifier_str = (str(identifier).strip() if identifier is not None else "")
        if not identifier_str:
            return ""
        identifier_str = identifier_str.rstrip("/")
        if "/" in identifier_str:
            identifier_str = identifier_str.rsplit("/", 1)[-1]
        return identifier_str

    @staticmethod
    def _extract_track_artists(track: dict) -> List[str]:
        names: List[str] = []
        extension = track.get("extension") or {}
        track_ext = extension.get("https://musicbrainz.org/doc/jspf#track") or {}
        metadata = track_ext.get("additional_metadata") or {}
        artists_meta = metadata.get("artists") or []
        for artist in artists_meta:
            name = (artist.get("artist_credit_name") or artist.get("name") or "").strip()
            if name:
                names.append(name)
        if not names:
            fallback = (track.get("creator") or track_ext.get("artist") or track.get("artist") or "").strip()
            if fallback:
                names.append(fallback)
        return names

    @staticmethod
    def _ensure_success(response: requests.Response) -> None:
        if response.status_code != 200:
            message = f"ListenBrainz API returned status {response.status_code}"
            raise ListenBrainzIntegrationError(message)
