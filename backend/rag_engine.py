"""Vector RAG engine for MovieMate AI chatbot."""

from __future__ import annotations

import os
import pickle
import re
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from data_store import get_catalog
from ml_engine import get_engine

BASE_DIR = Path(__file__).resolve().parent
VECTORIZER_PKL = BASE_DIR / "rag_vectorizer.pkl"
MATRIX_PKL = BASE_DIR / "rag_matrix.pkl"
DOCS_PKL = BASE_DIR / "rag_docs.pkl"


class MovieRAG:
    def __init__(self):
        self.vectorizer: TfidfVectorizer | None = None
        self.matrix = None
        self.documents: list[dict] = []
        self.error: str | None = None

    @property
    def ready(self) -> bool:
        return self.vectorizer is not None and self.matrix is not None and bool(self.documents)

    def build(self):
        catalog = get_catalog()
        self.documents = []
        for movie in catalog.movies:
            self.documents.append(
                {
                    "id": movie["id"],
                    "title": movie["title"],
                    "genres": [g["name"] for g in movie["genres"]],
                    "overview": movie["overview"],
                    "directors": movie["directors"],
                    "cast": movie["cast"][:5],
                    "vote_average": movie["vote_average"],
                    "runtime": movie.get("runtime"),
                    "language": movie["original_language"],
                    "text": catalog.rag_document(movie),
                }
            )

        corpus = [doc["text"] for doc in self.documents]
        self.vectorizer = TfidfVectorizer(stop_words="english", max_features=12000, ngram_range=(1, 2))
        self.matrix = self.vectorizer.fit_transform(corpus)

        pickle.dump(self.vectorizer, open(VECTORIZER_PKL, "wb"))
        pickle.dump(self.matrix, open(MATRIX_PKL, "wb"))
        pickle.dump(self.documents, open(DOCS_PKL, "wb"))
        return self

    def load(self):
        try:
            if not VECTORIZER_PKL.exists() or not MATRIX_PKL.exists() or not DOCS_PKL.exists():
                self.build()

            self.vectorizer = pickle.load(open(VECTORIZER_PKL, "rb"))
            self.matrix = pickle.load(open(MATRIX_PKL, "rb"))
            self.documents = pickle.load(open(DOCS_PKL, "rb"))
            self.error = None
        except Exception as exc:
            self.vectorizer = None
            self.matrix = None
            self.documents = []
            self.error = str(exc)
        return self

    def retrieve(self, query: str, limit=6):
        if not self.ready:
            return []

        query_vec = self.vectorizer.transform([query.lower()])
        scores = cosine_similarity(query_vec, self.matrix).flatten()
        ranked = np.argsort(scores)[::-1][: limit * 3]

        results = []
        seen_titles = set()
        for idx in ranked:
            doc = self.documents[int(idx)]
            if doc["title"] in seen_titles:
                continue
            seen_titles.add(doc["title"])
            results.append({**doc, "score": float(scores[int(idx)])})
            if len(results) >= limit:
                break
        return results

    def _parse_constraints(self, query: str):
        query_lower = query.lower()
        constraints = {
            "max_runtime": None,
            "min_rating": None,
            "genre": None,
            "language": None,
            "avoid_horror": "horror" in query_lower and any(word in query_lower for word in ["no", "without", "avoid", "not"]),
            "feel_good": any(word in query_lower for word in ["feel good", "uplifting", "light", "funny", "comedy"]),
            "intense": any(word in query_lower for word in ["intense", "dark", "thriller", "mind", "suspense"]),
        }

        runtime_match = re.search(r"(\d+)\s*(?:min|minute|minutes|hour|hours|hr)", query_lower)
        if runtime_match:
            value = int(runtime_match.group(1))
            if "hour" in runtime_match.group(0) or "hr" in runtime_match.group(0):
                value *= 60
            constraints["max_runtime"] = value

        rating_match = re.search(r"(?:above|over|at least)\s*(\d(?:\.\d)?)", query_lower)
        if rating_match:
            constraints["min_rating"] = float(rating_match.group(1))

        for genre in [
            "action",
            "comedy",
            "romance",
            "horror",
            "thriller",
            "animation",
            "drama",
            "sci-fi",
            "science fiction",
            "fantasy",
            "family",
        ]:
            if genre in query_lower:
                constraints["genre"] = "Science Fiction" if genre in {"sci-fi", "science fiction"} else genre.title()
                break

        if "hindi" in query_lower:
            constraints["language"] = "hi"
        elif "english" in query_lower:
            constraints["language"] = "en"

        return constraints

    def _apply_constraints(self, docs: list[dict], constraints: dict):
        filtered = []
        for doc in docs:
            if constraints["avoid_horror"] and "Horror" in doc["genres"]:
                continue
            if constraints["genre"] and constraints["genre"] not in doc["genres"]:
                continue
            if constraints["language"] and doc["language"] != constraints["language"]:
                continue
            if constraints["max_runtime"] and doc["runtime"] and doc["runtime"] > constraints["max_runtime"]:
                continue
            if constraints["min_rating"] and doc["vote_average"] < constraints["min_rating"]:
                continue
            if constraints["feel_good"] and not any(g in doc["genres"] for g in ["Comedy", "Family", "Animation", "Romance"]):
                continue
            if constraints["intense"] and not any(g in doc["genres"] for g in ["Thriller", "Crime", "Mystery", "Horror", "Science Fiction"]):
                continue
            filtered.append(doc)
        return filtered or docs[:5]

    def _try_gemini(self, query: str, docs: list[dict]) -> str | None:
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return None

        try:
            import google.generativeai as genai

            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            context = "\n\n".join(
                f"- {doc['title']} ({', '.join(doc['genres'])}, rating {doc['vote_average']}): {doc['overview'][:220]}"
                for doc in docs[:5]
            )
            prompt = (
                "You are MovieMate AI, a concise movie recommendation assistant. "
                "Use ONLY the provided movie facts. Recommend up to 5 movies with one-line reasons each. "
                "If nothing fits, say so honestly.\n\n"
                f"User query: {query}\n\nMovie facts:\n{context}"
            )
            response = model.generate_content(prompt)
            text = getattr(response, "text", None)
            return text.strip() if text else None
        except Exception:
            return None

    def _fallback_answer(self, query: str, docs: list[dict]) -> str:
        if not docs:
            return (
                "I couldn't find a strong match in the MovieMate catalog for that request. "
                "Try mentioning a genre, mood, or a movie you already like."
            )

        lines = ["Here are movies from the MovieMate catalog that fit your request:"]
        for doc in docs[:5]:
            genres = ", ".join(doc["genres"][:3]) or "General"
            runtime = f"{doc['runtime']} min" if doc.get("runtime") else "runtime N/A"
            lines.append(
                f"• **{doc['title']}** ({genres}, {runtime}, rated {doc['vote_average']}/10) — "
                f"{doc['overview'][:140].strip()}..."
            )

        lines.append("Open any title from the cards below to watch details and ML-powered similar picks.")
        return "\n".join(lines)

    def _is_upcoming_query(self, query: str) -> bool:
        q = query.lower()
        return any(
            w in q
            for w in [
                "upcoming",
                "2026",
                "releasing soon",
                "coming soon",
                "next year",
                "future release",
                "latest movie",
                "newest movie",
                "in theaters soon",
                "latest releases",
            ]
        )

    def _is_trending_query(self, query: str) -> bool:
        q = query.lower()
        return any(
            w in q
            for w in [
                "trending",
                "popular now",
                "popular this week",
                "hot right now",
                "top movies right now",
                "what is trending",
            ]
        )

    def _fetch_tmdb_movies_for_rag(self, endpoint: str, limit: int = 5) -> tuple[str, list[dict]]:
        try:
            from app import _fetch_tmdb_json, _format_tmdb_movie_item
            data = _fetch_tmdb_json(endpoint, {"page": 1})
            if not data or not data.get("results"):
                return "", []

            results = data["results"][:limit]
            formatted_cards = [_format_tmdb_movie_item(m) for m in results]

            is_upcoming = "upcoming" in endpoint
            header = (
                "Here are top upcoming 2026 movies releasing soon in theaters:"
                if is_upcoming
                else "Here are top trending movies right now:"
            )

            lines = [header]
            for m in results:
                title = m.get("title") or m.get("name") or "Untitled"
                rdate = m.get("release_date") or "2026"
                rating = float(m.get("vote_average") or 0)
                rating_str = f" (rated {rating:.1f}/10)" if rating > 0 else ""
                overview = (m.get("overview") or "No overview available.").strip()
                if len(overview) > 130:
                    overview = overview[:130] + "..."
                lines.append(f"• **{title}** ({rdate}{rating_str}) — {overview}")

            lines.append("\nClick any movie card below to view details and watch its trailer!")
            return "\n".join(lines), formatted_cards
        except Exception:
            return "", []

    def _try_openrouter(self, query: str) -> tuple[str | None, list[dict]]:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            return None, []

        models_to_try = [
            os.getenv("OPENROUTER_MODEL", "inclusionai/ling-3.0-flash:free"),
            "inclusionai/ling-3.0-flash:free",
            "google/gemma-4-31b-it:free",
            "openrouter/auto",
        ]
        # Remove duplicates while preserving order
        models_to_try = list(dict.fromkeys(models_to_try))

        url = "https://openrouter.ai/api/v1/chat/completions"
        system_prompt = (
            "You are MovieMate AI, an expert movie concierge specializing in global and Indian cinema "
            "(Tollywood, Kollywood, Mollywood, Sandalwood, Bollywood, Hollywood). "
            "Recommend 5 top movies for the user's request with a short 1-line reason for each. "
            "At the end of your response, list the movie titles inside a line formatted like: "
            "TITLES: Movie Title 1, Movie Title 2, Movie Title 3, Movie Title 4, Movie Title 5"
        )

        for model_name in models_to_try:
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query},
                ],
                "temperature": 0.7,
            }

            try:
                import json
                import urllib.request
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://127.0.0.1:5000",
                    "X-Title": "MovieMate",
                }
                req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
                with urllib.request.urlopen(req, timeout=6) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    text = data["choices"][0]["message"]["content"]

                    titles = []
                    match = re.search(r"TITLES:\s*(.+)", text, re.IGNORECASE)
                    if match:
                        titles = [t.strip() for t in match.group(1).split(",") if t.strip()]

                    clean_answer = re.sub(r"TITLES:\s*.+", "", text, flags=re.IGNORECASE).strip()

                    cards = []
                    if titles:
                        from app import _fetch_tmdb_json, _format_tmdb_movie_item
                        for t in titles[:5]:
                            tmdb_data = _fetch_tmdb_json("search/movie", {"query": t, "page": 1})
                            if tmdb_data and tmdb_data.get("results"):
                                cards.append(_format_tmdb_movie_item(tmdb_data["results"][0]))

                    return clean_answer, cards
            except Exception:
                continue

        return None, []

    def _is_regional_query(self, query: str) -> bool:
        q = query.lower()
        return any(
            w in q
            for w in [
                "south indian",
                "south india",
                "telugu",
                "tamil",
                "malayalam",
                "kannada",
                "bollywood",
                "tollywood",
                "kollywood",
                "mollywood",
                "hindi",
                "indian movie",
                "indian movies",
            ]
        )

    def _fetch_regional_movies_from_tmdb(self, query: str) -> tuple[str, list[dict]]:
        try:
            from app import _fetch_tmdb_json, _format_tmdb_movie_item
            q = query.lower()
            lang = "te|ta|ml|kn"
            region_name = "South Indian"
            if "hindi" in q or "bollywood" in q:
                lang = "hi"
                region_name = "Bollywood (Hindi)"
            elif "telugu" in q or "tollywood" in q:
                lang = "te"
                region_name = "Telugu (Tollywood)"
            elif "tamil" in q or "kollywood" in q:
                lang = "ta"
                region_name = "Tamil (Kollywood)"
            elif "malayalam" in q or "mollywood" in q:
                lang = "ml"
                region_name = "Malayalam (Mollywood)"
            elif "kannada" in q:
                lang = "kn"
                region_name = "Kannada (Sandalwood)"

            data = _fetch_tmdb_json("discover/movie", {"with_original_language": lang, "sort_by": "popularity.desc", "page": 1})
            if not data or not data.get("results"):
                return "", []

            results = data["results"][:5]
            formatted_cards = [_format_tmdb_movie_item(m) for m in results]

            lines = [f"Here are top popular {region_name} movies matching your request:"]
            for m in results:
                title = m.get("title") or m.get("name") or "Untitled"
                rdate = m.get("release_date") or "2026"
                rating = float(m.get("vote_average") or 0)
                rating_str = f" (rated {rating:.1f}/10)" if rating > 0 else ""
                overview = (m.get("overview") or "No overview available.").strip()
                if len(overview) > 130:
                    overview = overview[:130] + "..."
                lines.append(f"• **{title}** ({rdate}{rating_str}) — {overview}")

            lines.append("\nClick any movie card below to view details and watch its trailer!")
            return "\n".join(lines), formatted_cards
        except Exception:
            return "", []

    def chat(self, query: str, history: list | None = None):
        query = (query or "").strip()
        if not query:
            return {
                "answer": "Ask me for a movie by mood, genre, runtime, or ask about 2026 upcoming & South Indian movies!",
                "movies": [],
                "sources": [],
            }

        if not self.ready:
            return {
                "answer": "AI search index is still loading. Please try again in a moment.",
                "movies": [],
                "sources": [],
            }

        openrouter_answer, openrouter_cards = self._try_openrouter(query)
        if openrouter_answer:
            return {
                "answer": openrouter_answer,
                "movies": openrouter_cards,
                "sources": [{"title": c["title"], "score": 0.99} for c in openrouter_cards],
            }

        if self._is_upcoming_query(query):
            answer, cards = self._fetch_tmdb_movies_for_rag("movie/upcoming", limit=5)
            if answer:
                return {
                    "answer": answer,
                    "movies": cards,
                    "sources": [{"title": c["title"], "score": 0.99} for c in cards],
                }

        if self._is_trending_query(query):
            answer, cards = self._fetch_tmdb_movies_for_rag("trending/movie/week", limit=5)
            if answer:
                return {
                    "answer": answer,
                    "movies": cards,
                    "sources": [{"title": c["title"], "score": 0.99} for c in cards],
                }

        if self._is_regional_query(query):
            answer, cards = self._fetch_regional_movies_from_tmdb(query)
            if answer:
                return {
                    "answer": answer,
                    "movies": cards,
                    "sources": [{"title": c["title"], "score": 0.99} for c in cards],
                }

        constraints = self._parse_constraints(query)
        retrieved = self.retrieve(query, limit=8)
        retrieved = self._apply_constraints(retrieved, constraints)

        engine = get_engine()
        if len(retrieved) < 3:
            for movie in engine.semantic_filter(query, limit=5):
                retrieved.append(
                    {
                        "id": movie["id"],
                        "title": movie["title"],
                        "genres": [g["name"] for g in movie["genres"]],
                        "overview": movie["overview"],
                        "directors": movie["directors"],
                        "cast": movie["cast"][:5],
                        "vote_average": movie["vote_average"],
                        "runtime": movie.get("runtime"),
                        "language": movie["original_language"],
                        "text": get_catalog().rag_document(movie),
                        "score": 0.5,
                    }
                )

        seen = set()
        unique_docs = []
        for doc in retrieved:
            if doc["title"] in seen:
                continue
            seen.add(doc["title"])
            unique_docs.append(doc)
        unique_docs = unique_docs[:6]

        answer = self._try_gemini(query, unique_docs) or self._fallback_answer(query, unique_docs)
        catalog = get_catalog()

        return {
            "answer": answer,
            "movies": [catalog.card_payload(catalog.get(doc["id"])) for doc in unique_docs[:5] if catalog.get(doc["id"])],
            "sources": [
                {"title": doc["title"], "score": round(doc.get("score", 0), 3)}
                for doc in unique_docs[:5]
            ],
        }


_rag: MovieRAG | None = None


def get_rag() -> MovieRAG:
    global _rag
    if _rag is None:
        _rag = MovieRAG().load()
    return _rag
