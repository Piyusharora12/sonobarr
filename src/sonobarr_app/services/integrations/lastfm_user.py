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

    def _client(self, *, session_key: Optional[str] = None) -> pylast.LastFMNetwork:
        if session_key:
            return pylast.LastFMNetwork(api_key=self.api_key, api_secret=self.api_secret, session_key=session_key)
        return pylast.LastFMNetwork(api_key=self.api_key, api_secret=self.api_secret)

    def get_top_artists(self, username: str, limit: int = 50, *, session_key: Optional[str] = None) -> List[LastFmUserArtist]:
        if not username:
            return []
        network = self._client(session_key=session_key)
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

    def get_recommended_artists(self, username: str, limit: int = 50, *, session_key: Optional[str] = None) -> List[LastFmUserArtist]:
        """Return artists Last.fm suggests based on the user's taste.

        Strategy, in order of preference:
        1) Use pylast's user.get_recommended_artists if available (requires proper auth support in pylast).
        2) Build recommendations by aggregating similar artists for the user's top artists,
           excluding the user's top artists themselves. This approximates recommendations
           without requiring a user auth session key.
        """
        if not username:
            return []
        try:
            network = self._client(session_key=session_key)
            user = network.get_user(username)
            # 1) Direct recommendations if supported by the installed pylast version
            rec_fn = getattr(user, "get_recommended_artists", None)
            if callable(rec_fn):
                recs = rec_fn(limit=limit)
                results: List[LastFmUserArtist] = []
                for artist in recs or []:
                    name = getattr(artist, "name", "") or str(artist)
                    if name:
                        results.append(LastFmUserArtist(name=name, playcount=0, match_score=None))
                if results:
                    return results

            # 2) Approximate by similar-to-top aggregation
            top_entries = user.get_top_artists(limit=min(50, max(limit, 20)))
            top_names = [getattr(entry.item, "name", "") for entry in top_entries]
            top_set = {n for n in top_names if n}

            results: List[LastFmUserArtist] = []
            seen: set[str] = set()
            for entry in top_entries:
                artist_obj = entry.item
                base_name = getattr(artist_obj, "name", "")
                if not base_name:
                    continue
                try:
                    similar = network.get_artist(base_name).get_similar()
                except Exception:
                    continue
                for rel in similar:
                    try:
                        cand = getattr(rel.item, "name", "")
                        match_val = getattr(rel, "match", None)
                        match_score = float(match_val) if match_val is not None else None
                    except Exception:
                        cand, match_score = "", None
                    if not cand or cand in top_set or cand in seen:
                        continue
                    seen.add(cand)
                    results.append(LastFmUserArtist(name=cand, playcount=0, match_score=match_score))
                    if len(results) >= limit:
                        return results
            return results
        except Exception:
            return []
