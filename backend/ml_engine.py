"""Recommendation engine: TF-IDF similarity + explainable reasons."""

from __future__ import annotations

import ast
import pickle
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from data_store import TMDB_5000_CREDITS, TMDB_5000_MOVIES, get_catalog

BASE_DIR = Path(__file__).resolve().parent
MOVIES_PKL = BASE_DIR / "movies.pkl"
SIMILARITY_PKL = BASE_DIR / "similarity.pkl"
META_PKL = BASE_DIR / "movie_meta.pkl"


def parse_names(value, limit=None):
    if pd.isna(value):
        return ""
    try:
        parsed = ast.literal_eval(value) if isinstance(value, str) else value
    except (ValueError, SyntaxError):
        return str(value)
    if not isinstance(parsed, list):
        return str(parsed)
    names = []
    for item in parsed[: limit or len(parsed)]:
        if isinstance(item, dict):
            names.append(str(item.get("name", "")))
        else:
            names.append(str(item))
    return " ".join(names)


def parse_director(value):
    if pd.isna(value):
        return ""
    try:
        crew = ast.literal_eval(value) if isinstance(value, str) else value
    except (ValueError, SyntaxError):
        return ""
    if not isinstance(crew, list):
        return ""
    directors = [
        member.get("name", "")
        for member in crew
        if isinstance(member, dict) and member.get("job") == "Director"
    ]
    return " ".join(directors)


def build_tags(row):
    fields = [
        row.get("overview", ""),
        row.get("genres_text", ""),
        row.get("keywords_text", ""),
        row.get("cast_text", ""),
        row.get("director_text", ""),
    ]
    return " ".join(str(field) for field in fields).lower()


class RecommendationEngine:
    def __init__(self):
        self.movies: pd.DataFrame | None = None
        self.similarity = None
        self.meta: dict[int, dict] = {}
        self.error: str | None = None

    @property
    def ready(self) -> bool:
        return self.movies is not None and self.similarity is not None

    def load(self):
        try:
            if not MOVIES_PKL.exists() or not SIMILARITY_PKL.exists():
                self.train()

            self.movies = pickle.load(open(MOVIES_PKL, "rb"))
            self.similarity = pickle.load(open(SIMILARITY_PKL, "rb"))
            if META_PKL.exists():
                self.meta = pickle.load(open(META_PKL, "rb"))
            else:
                self._build_meta_from_catalog()
            self.error = None
        except Exception as exc:
            self.movies = None
            self.similarity = None
            self.error = str(exc)
        return self

    def _build_meta_from_catalog(self):
        catalog = get_catalog()
        self.meta = {
            movie["id"]: {
                "genres": {g["name"] for g in movie["genres"]},
                "directors": set(movie["directors"]),
                "cast": set(movie["cast"][:5]),
                "keywords": set(movie["keywords"][:10]),
            }
            for movie in catalog.movies
        }
        pickle.dump(self.meta, open(META_PKL, "wb"))

    def train(self):
        movies = pd.read_csv(TMDB_5000_MOVIES)
        credits = pd.read_csv(TMDB_5000_CREDITS)
        if "movie_id" in credits.columns:
            credits = credits.rename(columns={"movie_id": "id"})
        merged = movies.merge(credits, on="id", how="left", suffixes=("", "_credits"))

        merged["genres_text"] = merged["genres"].apply(parse_names) if "genres" in merged else ""
        merged["keywords_text"] = merged["keywords"].apply(parse_names) if "keywords" in merged else ""
        merged["cast_text"] = (
            merged["cast"].apply(lambda value: parse_names(value, limit=5)) if "cast" in merged else ""
        )
        merged["director_text"] = merged["crew"].apply(parse_director) if "crew" in merged else ""
        merged["tags"] = merged.apply(build_tags, axis=1)

        model_movies = merged[["id", "title", "tags"]].dropna(subset=["title"]).drop_duplicates("title")

        vectorizer = TfidfVectorizer(stop_words="english", max_features=8000, ngram_range=(1, 2))
        vectors = vectorizer.fit_transform(model_movies["tags"])
        sim_matrix = cosine_similarity(vectors)

        similarity = {}
        for idx in range(len(sim_matrix)):
            distances = sim_matrix[idx]
            ranked = sorted(list(enumerate(distances)), reverse=True, key=lambda x: x[1])[1:51]
            similarity[idx] = [(int(i), float(s)) for i, s in ranked]

        pickle.dump(model_movies.reset_index(drop=True), open(MOVIES_PKL, "wb"))
        pickle.dump(similarity, open(SIMILARITY_PKL, "wb"))

        catalog = get_catalog()
        meta = {}
        for _, row in model_movies.iterrows():
            movie = catalog.get(int(row["id"])) if pd.notna(row["id"]) else catalog.get_by_title(row["title"])
            if movie:
                meta[movie["id"]] = {
                    "genres": {g["name"] for g in movie["genres"]},
                    "directors": set(movie["directors"]),
                    "cast": set(movie["cast"][:5]),
                    "keywords": set(movie["keywords"][:10]),
                }
        pickle.dump(meta, open(META_PKL, "wb"))

        self.movies = model_movies.reset_index(drop=True)
        self.similarity = similarity
        self.meta = meta
        return self

    def _find_index(self, movie: str):
        idx = self.movies[self.movies["title"].str.lower() == movie.lower()].index
        return None if len(idx) == 0 else int(idx[0])

    def _movie_id_for_index(self, index: int):
        row = self.movies.iloc[index]
        if "id" in row and pd.notna(row["id"]):
            return int(row["id"])
        catalog = get_catalog()
        found = catalog.get_by_title(row["title"])
        return found["id"] if found else None

    def _reasons(self, source_id: int | None, target_id: int | None):
        if not source_id or not target_id:
            return ["Similar storyline and themes"]
        source = self.meta.get(source_id, {})
        target = self.meta.get(target_id, {})
        reasons = []

        shared_genres = source.get("genres", set()) & target.get("genres", set())
        if shared_genres:
            reasons.append(f"Shared genres: {', '.join(sorted(shared_genres)[:3])}")

        shared_directors = source.get("directors", set()) & target.get("directors", set())
        if shared_directors:
            reasons.append(f"Same director: {', '.join(sorted(shared_directors)[:2])}")

        shared_cast = source.get("cast", set()) & target.get("cast", set())
        if shared_cast:
            reasons.append(f"Shared cast: {', '.join(sorted(shared_cast)[:2])}")

        shared_keywords = source.get("keywords", set()) & target.get("keywords", set())
        if shared_keywords:
            reasons.append(f"Similar themes: {', '.join(sorted(shared_keywords)[:3])}")

        return reasons or ["Similar storyline, tone, and themes"]

    def similar(self, movie: str, limit=6, include_scores=False):
        if not self.ready:
            return []

        idx = self._find_index(movie)
        if idx is None:
            return []

        source_id = self._movie_id_for_index(idx)
        if isinstance(self.similarity, dict):
            ranked = self.similarity.get(idx, [])[:limit]
        else:
            distances = self.similarity[idx]
            ranked = sorted(list(enumerate(distances)), reverse=True, key=lambda item: item[1])[1 : limit + 1]

        results = []
        for movie_idx, score in ranked:
            row = self.movies.iloc[movie_idx]
            target_id = self._movie_id_for_index(movie_idx)
            payload = {
                "title": row["title"],
                "id": target_id,
                "score": float(score),
                "reasons": self._reasons(source_id, target_id),
            }
            results.append(payload)

        if include_scores:
            return results
        return [item["title"] for item in results]

    def from_history(self, watched: list[str], limit=10):
        if not self.ready:
            return []

        watched_titles = {title.lower() for title in watched if isinstance(title, str)}
        scores: dict[str, float] = {}
        reason_map: dict[str, list[str]] = {}

        for title in watched_titles:
            idx = self._find_index(title)
            if idx is None:
                continue
            source_id = self._movie_id_for_index(idx)

            for movie_idx, score in enumerate(self.similarity[idx]):
                row = self.movies.iloc[movie_idx]
                candidate = row["title"]
                if candidate.lower() in watched_titles:
                    continue
                scores[candidate] = max(scores.get(candidate, 0), float(score))
                if candidate not in reason_map:
                    target_id = self._movie_id_for_index(movie_idx)
                    reason_map[candidate] = self._reasons(source_id, target_id)

        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:limit]
        return [
            {
                "title": title,
                "score": score,
                "reasons": reason_map.get(title, ["Matches your watch history"]),
            }
            for title, score in ranked
        ]

    def semantic_filter(self, query: str, limit=8):
        if not self.ready:
            return []

        query = query.lower()
        tokens = [token for token in query.split() if len(token) > 2]
        if not tokens:
            return []

        catalog = get_catalog()
        scored = []
        for movie in catalog.movies:
            haystack = " ".join(
                [
                    movie["title"],
                    movie["overview"],
                    " ".join(g["name"] for g in movie["genres"]),
                    " ".join(movie["keywords"]),
                    " ".join(movie["directors"]),
                    " ".join(movie["cast"][:5]),
                ]
            ).lower()
            score = sum(1 for token in tokens if token in haystack)
            if score:
                scored.append((score, movie))

        scored.sort(key=lambda item: (item[0], item[1]["popularity"]), reverse=True)
        return [item[1] for item in scored[:limit]]


_engine: RecommendationEngine | None = None


def get_engine() -> RecommendationEngine:
    global _engine
    if _engine is None:
        _engine = RecommendationEngine().load()
    return _engine
