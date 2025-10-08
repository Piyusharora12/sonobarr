from __future__ import annotations

import threading
import time
from typing import Any, Dict

import requests


class ReleaseClient:
    """Simple cached client for retrieving the latest GitHub release."""

    def __init__(self, repo: str, user_agent: str, ttl_seconds: int, logger) -> None:
        self.repo = repo
        self.user_agent = user_agent or "sonobarr-app"
        self.ttl_seconds = max(ttl_seconds, 60)
        self.logger = logger
        self._lock = threading.Lock()
        self._cache: Dict[str, Any] = {
            "fetched_at": 0.0,
            "tag_name": None,
            "html_url": None,
            "error": None,
        }

    def fetch_latest(self, force: bool = False) -> Dict[str, Any]:
        now = time.time()
        with self._lock:
            age = now - self._cache["fetched_at"]
            if not force and age < self.ttl_seconds and (
                self._cache["tag_name"] or self._cache["error"]
            ):
                return dict(self._cache)

        info: Dict[str, Any] = {
            "tag_name": None,
            "html_url": None,
            "error": None,
            "fetched_at": now,
        }

        releases_url = f"https://github.com/{self.repo}/releases"
        request_url = f"https://api.github.com/repos/{self.repo}/releases/latest"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": self.user_agent,
        }

        try:
            response = requests.get(request_url, headers=headers, timeout=5)
            if response.status_code == 200:
                payload = response.json()
                tag_name = (payload.get("tag_name") or payload.get("name") or "").strip() or None
                info["tag_name"] = tag_name
                info["html_url"] = payload.get("html_url") or releases_url
            else:
                info["error"] = f"GitHub API returned status {response.status_code}"
        except Exception as exc:  # pragma: no cover - network errors
            info["error"] = str(exc)

        if not info.get("html_url"):
            info["html_url"] = releases_url

        with self._lock:
            self._cache.update(info)

        return dict(info)
