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
        """Return a user's artist recommendations.

        pylast doesn't expose a stable tasteometer client across versions; to keep this
        robust we fall back to the user's top artists as "recommendations" if a
        dedicated recommendations API isn't available.
        """
        if not username:
            return []
        try:
            network = self._client()
            user = network.get_user(username)
            # Some pylast versions provide get_recommended_artists on User; use if present
            rec_fn = getattr(user, "get_recommended_artists", None)
            if callable(rec_fn):
                recs = rec_fn(limit=limit)
                results: List[LastFmUserArtist] = []
                for artist in recs or []:
                    name = getattr(artist, "name", "") or str(artist)
                    results.append(LastFmUserArtist(name=name, playcount=0, match_score=None))
                if results:
                    return results
            # Fallback to top artists
            top = user.get_top_artists(limit=limit)
            results: List[LastFmUserArtist] = []
            for entry in top:
                artist = entry.item
                playcount = int(entry.weight) if hasattr(entry, "weight") else 0
                results.append(LastFmUserArtist(name=getattr(artist, "name", "") or "", playcount=playcount))
            return results
        except Exception:
            return []
