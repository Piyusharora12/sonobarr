import json
import re
from typing import List, Optional, Sequence

from openai import OpenAI
from openai import OpenAIError


DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_MAX_SEED_ARTISTS = 5
DEFAULT_OPENAI_TIMEOUT = 60.0

_SYSTEM_PROMPT = (
    "You are Sonobarr's music discovery assistant. "
    "Given a user request about music tastes, moods, genres, or artists, "
    "respond with a JSON array of up to {max_artists} artist names that best match the request. "
    "Only return the JSON array, with each artist as a string. "
    "The artists should be discoverable on major streaming services and ideally not already present in the provided library list."
)


class OpenAIRecommender:
    def __init__(
        self,
        *,
        api_key: str,
        model: str | None = None,
        max_seed_artists: int = DEFAULT_MAX_SEED_ARTISTS,
        timeout: float | None = DEFAULT_OPENAI_TIMEOUT,
    ) -> None:
        self.timeout = timeout
        self.client = OpenAI(api_key=api_key, timeout=timeout)
        self.model = model or DEFAULT_OPENAI_MODEL
        self.max_seed_artists = max_seed_artists

    def _extract_array_fragment(self, content: str) -> Optional[str]:
        if not content:
            return None

        # Prefer fenced code blocks labelled json (e.g. ```json ... ```)
        for match in re.finditer(r"```(?:json)?\s*(.*?)```", content, flags=re.IGNORECASE | re.DOTALL):
            candidate = match.group(1).strip()
            if candidate.startswith("["):
                return candidate

        content_stripped = content.strip()
        if content_stripped.startswith("["):
            return content_stripped

        decoder = json.JSONDecoder()
        text_length = len(content)
        idx = 0
        while idx < text_length:
            char = content[idx]
            if char == "[":
                try:
                    parsed, end = decoder.raw_decode(content[idx:])
                except json.JSONDecodeError:
                    idx += 1
                    continue
                if isinstance(parsed, list):
                    return content[idx : idx + end]
            idx += 1
        return None

    def generate_seed_artists(
        self,
        prompt: str,
        existing_artists: Sequence[str] | None = None,
    ) -> List[str]:
        existing_artists = existing_artists or []
        system_prompt = _SYSTEM_PROMPT.format(max_artists=self.max_seed_artists)
        user_prompt = (
            "User request:\n"
            f"{prompt.strip()}\n\n"
            "Artists already in the library:\n"
            f"{', '.join(existing_artists[:50]) if existing_artists else 'None provided.'}"
        )

        request_kwargs = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        temperature_value = 0.7
        if temperature_value is not None:
            request_kwargs["temperature"] = temperature_value

        attempts = 2
        last_exc: Optional[Exception] = None
        for attempt in range(attempts):
            try:
                response = self.client.chat.completions.create(**request_kwargs)
                break
            except OpenAIError as exc:  # pragma: no cover - network failure path
                message = str(exc)
                last_exc = exc
                if (
                    "temperature" in message.lower()
                    and "unsupported" in message.lower()
                    and request_kwargs.pop("temperature", None) is not None
                ):
                    continue
                if "timed out" in message.lower() and attempt + 1 < attempts:
                    continue
                raise RuntimeError(message) from exc
        else:  # pragma: no cover - defensive
            if last_exc is not None:
                raise RuntimeError(str(last_exc)) from last_exc
            raise RuntimeError("OpenAI request failed without response")

        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError, KeyError) as exc:
            raise RuntimeError("Unexpected response format from OpenAI.") from exc

        if not content:
            return []

        content = content.strip()
        array_fragment = self._extract_array_fragment(content)
        if not array_fragment:
            raise RuntimeError(
                "OpenAI response did not include a JSON array of artist names. "
                "Please try rephrasing your request."
            )

        try:
            raw_data = json.loads(array_fragment)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "OpenAI response was not valid JSON. "
                "Please try rephrasing your request."
            ) from exc

        if not isinstance(raw_data, list):
            if isinstance(raw_data, dict):
                candidate_list = raw_data.get("artists") or raw_data.get("seeds")
                if isinstance(candidate_list, list):
                    raw_data = candidate_list
                else:
                    raise RuntimeError("OpenAI response JSON was not a list of artists.")
            else:
                raise RuntimeError("OpenAI response JSON was not a list of artists.")

        seeds: List[str] = []
        for item in raw_data:
            if isinstance(item, str):
                artist = item.strip()
                if artist and artist.lower() not in {
                    artist_name.lower() for artist_name in seeds
                }:
                    seeds.append(artist)
            elif isinstance(item, dict):
                name = item.get("name") if isinstance(item.get("name"), str) else None
                if name:
                    artist = name.strip()
                    if artist and artist.lower() not in {
                        artist_name.lower() for artist_name in seeds
                    }:
                        seeds.append(artist)

        if len(seeds) > self.max_seed_artists:
            seeds = seeds[: self.max_seed_artists]

        return seeds
