from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import pylast


@dataclass
class LastFmUserArtist:
    name: str
    playcount: int
    match_score: Optional[float] = None


class LastFmUserService:
    """Wrapper for fetching user-specific listening data from Last.fm."""

    def __init__(self, api_key: str, api_secret: str) -> None:
        self.api_key = api_key
        self.api_secret = api_secret

    def _client(self) -> pylast.LastFMNetwork:
        return pylast.LastFMNetwork(api_key=self.api_key, api_secret=self.api_secret)

    def get_top_artists(self, username: str, limit: int = 50) -> List[LastFmUserArtist]:
        if not username:
            return []
        network = self._client()
        user = network.get_user(username)
        top_artists = user.get_top_artists(limit=limit)
        results: List[LastFmUserArtist] = []
        for entry in top_artists:
            artist = entry.item
            playcount = int(entry.weight) if hasattr(entry, "weight") else 0
            results.append(
                LastFmUserArtist(
                    name=getattr(artist, "name", "") or "",
                    playcount=playcount,
                )
            )
        return results

    def get_recommended_artists(self, username: str, limit: int = 50) -> List[LastFmUserArtist]:
        """Use Last.fm tasteometer to fetch similar artists to the user's taste."""
        if not username:
            return []
        network = self._client()
        taste = network.get_tasteometer()
        try:
            response = taste.user_get_top_artists(username, limit=limit)
        except Exception:
            return []
        results: List[LastFmUserArtist] = []
        for item in response:
            artist = item.get("artist")
            if not artist:
                continue
            name = artist.get("name", "")
            match_score = float(item.get("match", 0)) if item.get("match") is not None else None
            results.append(
                LastFmUserArtist(
                    name=name,
                    playcount=0,
                    match_score=match_score,
                )
            )
        return results
