"""Local movie catalog built from TMDB 5000 CSV files (no external API)."""

from __future__ import annotations

import ast
import json
import math
import re
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
TMDB_5000_MOVIES = BASE_DIR / "tmdb_5000_movies.csv"
TMDB_5000_CREDITS = BASE_DIR / "tmdb_5000_credits.csv"
CATALOG_PATH = BASE_DIR / "movie_catalog.json"

GENRE_PALETTE = {
    "Action": "#e74c3c",
    "Adventure": "#e67e22",
    "Animation": "#9b59b6",
    "Comedy": "#f1c40f",
    "Crime": "#34495e",
    "Documentary": "#95a5a6",
    "Drama": "#3498db",
    "Family": "#1abc9c",
    "Fantasy": "#8e44ad",
    "History": "#795548",
    "Horror": "#c0392b",
    "Music": "#e91e63",
    "Mystery": "#607d8b",
    "Romance": "#ff4081",
    "Science Fiction": "#00bcd4",
    "TV Movie": "#78909c",
    "Thriller": "#ff5722",
    "War": "#5d4037",
    "Western": "#8d6e63",
}


def _parse_json_list(value):
    if pd.isna(value):
        return []
    if isinstance(value, list):
        return value
    try:
        parsed = ast.literal_eval(value)
        return parsed if isinstance(parsed, list) else []
    except (ValueError, SyntaxError):
        return []


def _parse_names(items, limit=None):
    names = []
    for item in items[: limit or len(items)]:
        if isinstance(item, dict):
            name = item.get("name", "")
            if name:
                names.append(str(name))
        elif item:
            names.append(str(item))
    return names


def _directors(crew):
    return [
        member.get("name", "")
        for member in crew
        if isinstance(member, dict) and member.get("job") == "Director"
    ]


def _cast_names(cast, limit=10):
    return _parse_names(cast, limit)


class MovieCatalog:
    def __init__(self):
        self.movies: list[dict] = []
        self.by_id: dict[int, dict] = {}
        self.by_title: dict[str, dict] = {}
        self.genres: list[dict] = []
        self.genre_name_to_id: dict[str, int] = {}

    def load(self):
        if CATALOG_PATH.exists():
            payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
            self.movies = payload["movies"]
            self.genres = payload["genres"]
        else:
            self._build_from_csv()
            self.save()

        self.by_id = {movie["id"]: movie for movie in self.movies}
        self.by_title = {movie["title"].lower(): movie for movie in self.movies}
        self.genre_name_to_id = {g["name"].lower(): g["id"] for g in self.genres}
        return self

    def save(self):
        CATALOG_PATH.write_text(
            json.dumps({"genres": self.genres, "movies": self.movies}, ensure_ascii=False),
            encoding="utf-8",
        )

    def _build_from_csv(self):
        movies_df = pd.read_csv(TMDB_5000_MOVIES)
        credits_df = pd.read_csv(TMDB_5000_CREDITS)

        if "movie_id" in credits_df.columns:
            credits_df = credits_df.rename(columns={"movie_id": "id"})

        merged = movies_df.merge(credits_df, on="id", how="left", suffixes=("", "_credits"))

        genre_map: dict[int, str] = {}
        records = []

        for _, row in merged.iterrows():
            genre_items = _parse_json_list(row.get("genres"))
            genres = [
                {"id": int(item["id"]), "name": item["name"]}
                for item in genre_items
                if isinstance(item, dict) and "id" in item and "name" in item
            ]
            for genre in genres:
                genre_map[genre["id"]] = genre["name"]

            cast = _parse_json_list(row.get("cast"))
            crew = _parse_json_list(row.get("crew"))
            keywords = _parse_names(_parse_json_list(row.get("keywords")))
            directors = _directors(crew)
            cast_top = _cast_names(cast, 10)

            movie_id = int(row["id"])
            title = str(row.get("title") or row.get("original_title") or "Untitled")
            release_date = str(row.get("release_date") or "")
            overview = str(row.get("overview") or "")
            tagline = str(row.get("tagline") or "")
            runtime = row.get("runtime")
            runtime = int(runtime) if pd.notna(runtime) else None
            vote_average = float(row.get("vote_average") or 0)
            vote_count = int(row.get("vote_count") or 0)
            popularity = float(row.get("popularity") or 0)
            language = str(row.get("original_language") or "en")
            status = str(row.get("status") or "Released")

            primary_genre = genres[0]["name"] if genres else "Drama"
            color = GENRE_PALETTE.get(primary_genre, "#00d7fd")

            records.append(
                {
                    "id": movie_id,
                    "title": title,
                    "original_title": str(row.get("original_title") or title),
                    "overview": overview,
                    "tagline": tagline,
                    "release_date": release_date,
                    "runtime": runtime,
                    "vote_average": vote_average,
                    "vote_count": vote_count,
                    "popularity": popularity,
                    "original_language": language,
                    "status": status,
                    "genres": genres,
                    "genre_ids": [g["id"] for g in genres],
                    "keywords": keywords,
                    "cast": cast_top,
                    "directors": directors,
                    "poster_path": f"/{movie_id}",
                    "backdrop_path": f"/{movie_id}",
                    "poster_color": color,
                    "budget": int(row["budget"]) if pd.notna(row.get("budget")) else 0,
                    "revenue": int(row["revenue"]) if pd.notna(row.get("revenue")) else 0,
                }
            )

        self.genres = [{"id": gid, "name": name} for gid, name in sorted(genre_map.items())]
        self.movies = sorted(records, key=lambda item: item["popularity"], reverse=True)

    def get(self, movie_id: int):
        return self.by_id.get(int(movie_id))

    def get_by_title(self, title: str):
        return self.by_title.get(title.lower())

    def card_payload(self, movie: dict):
        return {
            "id": movie["id"],
            "title": movie["title"],
            "poster_path": movie["poster_path"],
            "backdrop_path": movie["backdrop_path"],
            "vote_average": movie["vote_average"],
            "release_date": movie["release_date"],
            "overview": movie["overview"],
            "genre_ids": movie["genre_ids"],
            "popularity": movie["popularity"],
            "original_language": movie["original_language"],
        }

    def paginate(self, items: list[dict], page: int, per_page: int = 20):
        page = max(1, int(page))
        total = len(items)
        total_pages = max(1, math.ceil(total / per_page))
        start = (page - 1) * per_page
        end = start + per_page
        return {
            "page": page,
            "results": [self.card_payload(movie) for movie in items[start:end]],
            "total_pages": total_pages,
            "total_results": total,
        }

    def list_popular(self, page=1):
        items = sorted(self.movies, key=lambda m: m["popularity"], reverse=True)
        return self.paginate(items, page)

    def list_top_rated(self, page=1):
        items = sorted(
            [m for m in self.movies if m["vote_count"] >= 50],
            key=lambda m: m["vote_average"],
            reverse=True,
        )
        return self.paginate(items or self.movies, page)

    def list_upcoming(self, page=1):
        items = sorted(
            self.movies,
            key=lambda m: m.get("release_date") or "",
            reverse=True,
        )[:200]
        return self.paginate(items, page)

    def list_trending(self, page=1):
        items = sorted(
            self.movies,
            key=lambda m: (m["popularity"] * 0.6 + m["vote_average"] * 0.4),
            reverse=True,
        )[:120]
        return self.paginate(items, page)

    def search(self, query: str, page=1):
        query = query.strip().lower()
        if not query:
            return self.paginate([], page)

        scored = []
        for movie in self.movies:
            title = movie["title"].lower()
            score = 0
            if title == query:
                score = 100
            elif title.startswith(query):
                score = 80
            elif query in title:
                score = 60
            elif query in movie["overview"].lower():
                score = 30
            else:
                for genre in movie["genres"]:
                    if query in genre["name"].lower():
                        score = 25
                        break
            if score:
                scored.append((score, movie))

        scored.sort(key=lambda item: (item[0], item[1]["popularity"]), reverse=True)
        items = [movie for _, movie in scored]
        return self.paginate(items, page)

    def discover(self, args, page=1):
        items = list(self.movies)

        genre_ids = args.get("with_genres")
        if genre_ids:
            wanted = {int(g) for g in str(genre_ids).split(",") if g.isdigit()}
            items = [m for m in items if wanted.intersection(set(m["genre_ids"]))]

        language = args.get("with_original_language")
        if language:
            items = [m for m in items if m["original_language"] == language]

        sort_by = args.get("sort_by", "popularity.desc")
        if sort_by == "vote_average.desc":
            items.sort(key=lambda m: m["vote_average"], reverse=True)
        else:
            items.sort(key=lambda m: m["popularity"], reverse=True)

        return self.paginate(items, page)

    def detail_payload(self, movie_id: int):
        movie = self.get(movie_id)
        if not movie:
            return None

        certification = "PG-13" if movie["vote_average"] < 8 else "R"
        if movie["genres"] and movie["genres"][0]["name"] in {"Family", "Animation"}:
            certification = "PG"

        cast_objects = [
            {"name": name, "character": name, "order": index}
            for index, name in enumerate(movie["cast"])
        ]
        crew_objects = [
            {"name": name, "job": "Director"}
            for name in movie["directors"]
        ]

        return {
            "id": movie["id"],
            "title": movie["title"],
            "overview": movie["overview"],
            "tagline": movie["tagline"],
            "release_date": movie["release_date"],
            "runtime": movie["runtime"],
            "vote_average": movie["vote_average"],
            "vote_count": movie["vote_count"],
            "popularity": movie["popularity"],
            "original_language": movie["original_language"],
            "status": movie["status"],
            "genres": movie["genres"],
            "genre_ids": movie["genre_ids"],
            "poster_path": movie["poster_path"],
            "backdrop_path": movie["backdrop_path"],
            "casts": {"cast": cast_objects, "crew": crew_objects},
            "videos": self._get_videos_payload(movie["id"], movie["title"]),
            "releases": {"countries": [{"certification": certification}]},
            "keywords": movie["keywords"],
            "directors": movie["directors"],
        }

    def _get_videos_payload(self, movie_id: int, title: str) -> dict:
        try:
            from trailer_resolver import get_trailer_resolver
            return get_trailer_resolver().videos_payload(movie_id, title)
        except Exception as e:
            print(f"Error resolving videos for {movie_id} ({title}):", e)
            return {"id": movie_id, "results": []}

    def recommendations_for(self, movie_id: int, limit=20):
        movie = self.get(movie_id)
        if not movie:
            return []

        genre_ids = set(movie["genre_ids"])
        scored = []
        for candidate in self.movies:
            if candidate["id"] == movie_id:
                continue
            overlap = len(genre_ids.intersection(candidate["genre_ids"]))
            score = overlap * 2 + candidate["vote_average"] * 0.2 + candidate["popularity"] * 0.01
            if overlap or candidate["original_language"] == movie["original_language"]:
                scored.append((score, candidate))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [self.card_payload(item[1]) for item in scored[:limit]]

    def rag_document(self, movie: dict) -> str:
        genres = ", ".join(g["name"] for g in movie["genres"])
        keywords = ", ".join(movie["keywords"][:8])
        cast = ", ".join(movie["cast"][:5])
        directors = ", ".join(movie["directors"])
        runtime = f"{movie['runtime']} minutes" if movie.get("runtime") else "unknown runtime"
        return (
            f"Title: {movie['title']}. "
            f"Genres: {genres}. "
            f"Release date: {movie['release_date']}. "
            f"Rating: {movie['vote_average']}/10 from {movie['vote_count']} votes. "
            f"Runtime: {runtime}. "
            f"Language: {movie['original_language']}. "
            f"Directors: {directors or 'unknown'}. "
            f"Cast: {cast or 'unknown'}. "
            f"Keywords: {keywords or 'none'}. "
            f"Overview: {movie['overview']}"
        )


_catalog: MovieCatalog | None = None


def get_catalog() -> MovieCatalog:
    global _catalog
    if _catalog is None:
        _catalog = MovieCatalog().load()
    return _catalog
