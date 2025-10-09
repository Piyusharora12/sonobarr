import json
from typing import List, Sequence

from openai import OpenAI
from openai import OpenAIError


DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_MAX_SEED_ARTISTS = 5

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
        timeout: float | None = 30.0,
    ) -> None:
        self.client = OpenAI(api_key=api_key, timeout=timeout)
        self.model = model or DEFAULT_OPENAI_MODEL
        self.max_seed_artists = max_seed_artists

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

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=300,
            )
        except OpenAIError as exc:  # pragma: no cover - network failure path
            raise RuntimeError(str(exc)) from exc

        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError, KeyError) as exc:
            raise RuntimeError("Unexpected response format from OpenAI.") from exc

        if not content:
            return []

        content = content.strip()
        try:
            raw_data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "OpenAI response was not valid JSON. "
                "Please try rephrasing your request."
            ) from exc

        if not isinstance(raw_data, list):
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
