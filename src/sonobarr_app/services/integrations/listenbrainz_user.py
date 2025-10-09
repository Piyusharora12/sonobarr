from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

import requests


@dataclass
class ListenBrainzUserArtist:
    name: str
    score: Optional[float] = None


class ListenBrainzUserService:
    """Fetch user listening data from ListenBrainz."""

    BASE_URL = "https://api.listenbrainz.org/1"  # public API endpoint

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self.logger = logger or logging.getLogger(__name__)

    def _headers(self, user_token: Optional[str]) -> dict[str, str]:
        headers = {"User-Agent": "sonobarr/0.6"}
        if user_token:
            headers["Authorization"] = f"Token {user_token}"
        return headers

    def get_user_top_artists(
        self,
        username: str,
        *,
        user_token: Optional[str] = None,
        limit: int = 50,
    ) -> List[ListenBrainzUserArtist]:
        if not username:
            return []
        endpoint = f"{self.BASE_URL}/stats/user/{username}/artists"  # returns top artists
        params = {"count": limit}
        try:
            response = requests.get(endpoint, params=params, headers=self._headers(user_token), timeout=10)
            response.raise_for_status()
        except Exception as exc:  # pragma: no cover - network errors
            self.logger.error("ListenBrainz top artists failed for %s: %s", username, exc)
            return []
        payload = response.json()
        items = payload.get("payload", {}).get("artists", [])
        results: List[ListenBrainzUserArtist] = []
        for item in items:
            name = item.get("artist_name") or ""
            score = item.get("raw_count")
            if score is not None:
                try:
                    score = float(score)
                except (TypeError, ValueError):
                    score = None
            results.append(ListenBrainzUserArtist(name=name, score=score))
        return results

    def get_user_discoveries(
        self,
        username: str,
        *,
        user_token: Optional[str] = None,
        limit: int = 50,
    ) -> List[ListenBrainzUserArtist]:
        """Fetch ListenBrainz personalized recommendations."""
        if not username:
            return []
        endpoint = f"{self.BASE_URL}/recommendation/user/{username}/artists"  # discovery endpoint
        params = {"count": limit}
        try:
            response = requests.get(endpoint, params=params, headers=self._headers(user_token), timeout=10)
            response.raise_for_status()
        except Exception as exc:  # pragma: no cover - network errors
            self.logger.error("ListenBrainz recommendations failed for %s: %s", username, exc)
            return []
        payload = response.json()
        items = payload.get("payload", {}).get("recommended_artists", [])
        results: List[ListenBrainzUserArtist] = []
        for item in items:
            name = item.get("artist_name") or ""
            score = item.get("score")
            if score is not None:
                try:
                    score = float(score)
                except (TypeError, ValueError):
                    score = None
            results.append(ListenBrainzUserArtist(name=name, score=score))
        return results
