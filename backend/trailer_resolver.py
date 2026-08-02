"""Resolve YouTube trailer video IDs by movie ID and title (cached, TMDB + YouTube search fallback)."""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CACHE_PATH = BASE_DIR / "trailer_cache.json"

TMDB_API_KEYS = [
    "8265bd1679663a7ea12ac168da84d2e8",
    "c13c72b2203714b6bd27b876a40a5a3a",
]

INVIDIOUS_INSTANCES = [
    "https://yewtu.be",
    "https://inv.nadeko.net",
    "https://invidious.jing.rocks",
]

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class TrailerResolver:
    def __init__(self):
        self.cache: dict[str, str | None] = {}
        if CACHE_PATH.exists():
            try:
                self.cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self.cache = {}

    def save(self):
        CACHE_PATH.write_text(
            json.dumps(self.cache, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _fetch_text(self, url: str, timeout=4) -> str | None:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="ignore")

    def _fetch_json(self, url: str, timeout=4):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def _fetch_tmdb_videos(self, movie_id: int) -> list[dict]:
        for key in TMDB_API_KEYS:
            try:
                url = f"https://api.themoviedb.org/3/movie/{movie_id}/videos?api_key={key}"
                data = self._fetch_json(url, timeout=5)
                results = data.get("results", [])
                if results:
                    return results
            except Exception as e:
                print(f"TMDB video fetch error for key {key}:", e)
                continue
        return []

    def _extract_video_id(self, html: str) -> str | None:
        patterns = [
            r'"videoId":"([a-zA-Z0-9_-]{11})"',
            r"watch\?v=([a-zA-Z0-9_-]{11})",
            r"embed/([a-zA-Z0-9_-]{11})",
        ]
        seen = set()
        for pattern in patterns:
            for match in re.finditer(pattern, html):
                video_id = match.group(1)
                if video_id not in seen:
                    seen.add(video_id)
                    return video_id
        return None

    def _search_youtube(self, title: str) -> str | None:
        query = urllib.parse.quote(f"{title} official trailer")
        url = f"https://www.youtube.com/results?search_query={query}&sp=EgIQAQ%253D%253D"
        try:
            html = self._fetch_text(url, timeout=5)
            return self._extract_video_id(html) if html else None
        except Exception:
            return None

    def _search_invidious(self, title: str) -> str | None:
        query = urllib.parse.quote(f"{title} official trailer")
        for base in INVIDIOUS_INSTANCES:
            try:
                url = f"{base}/api/v1/search?q={query}&type=video&sort_by=relevance"
                results = self._fetch_json(url, timeout=3)
                if not isinstance(results, list):
                    continue
                for item in results[:5]:
                    video_id = item.get("videoId")
                    video_title = (item.get("title") or "").lower()
                    if not video_id:
                        continue
                    if "trailer" in video_title or title.lower().split(":")[0] in video_title:
                        return video_id
                if results and results[0].get("videoId"):
                    return results[0]["videoId"]
            except Exception:
                continue
        return None

    def get_video_id(self, title: str, movie_id: int | None = None) -> str | None:
        cache_key = f"{movie_id}_{title.strip().lower()}" if movie_id else title.strip().lower()

        if cache_key in self.cache and self.cache[cache_key]:
            return self.cache[cache_key]

        if title.strip().lower() in self.cache and self.cache[title.strip().lower()]:
            return self.cache[title.strip().lower()]

        # 1. Try TMDB videos API if movie_id provided
        if movie_id:
            tmdb_videos = self._fetch_tmdb_videos(movie_id)
            trailers = [
                v for v in tmdb_videos
                if v.get("site") == "YouTube" and v.get("type") in ("Trailer", "Teaser") and v.get("key")
            ]
            if trailers:
                key = trailers[0]["key"]
                self.cache[cache_key] = key
                self.save()
                return key

        # 2. Fallback to YouTube web search & Invidious
        video_id = self._search_youtube(title) or self._search_invidious(title)
        self.cache[cache_key] = video_id
        self.save()
        return video_id

    def videos_payload(self, movie_id: int, title: str) -> dict:
        # First try TMDB videos list to get multiple videos if available
        tmdb_videos = self._fetch_tmdb_videos(movie_id)
        if tmdb_videos:
            formatted = []
            for v in tmdb_videos:
                if v.get("site") == "YouTube" and v.get("key"):
                    formatted.append({
                        "id": v.get("id", v["key"]),
                        "key": v["key"],
                        "name": v.get("name") or f"{title} Video",
                        "site": "YouTube",
                        "type": v.get("type") or "Trailer",
                        "official": v.get("official", True),
                    })
            if formatted:
                formatted.sort(key=lambda item: 0 if item["type"] == "Trailer" else (1 if item["type"] == "Teaser" else 2))
                return {"id": movie_id, "results": formatted}

        # Fallback to single resolved trailer video_id
        video_id = self.get_video_id(title, movie_id)
        if not video_id:
            return {"id": movie_id, "results": []}

        return {
            "id": movie_id,
            "results": [
                {
                    "id": video_id,
                    "key": video_id,
                    "name": f"{title} Official Trailer",
                    "site": "YouTube",
                    "type": "Trailer",
                    "official": True,
                }
            ],
        }


_resolver: TrailerResolver | None = None


def get_trailer_resolver() -> TrailerResolver:
    global _resolver
    if _resolver is None:
        _resolver = TrailerResolver()
    return _resolver
