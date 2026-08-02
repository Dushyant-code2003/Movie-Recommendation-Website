"""Production Flask server: local movie API, live TMDb hybrid, ML recommendations, RAG chatbot."""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request, send_from_directory
from flask_cors import CORS

from data_store import get_catalog
from ml_engine import get_engine
from poster_generator import (
    get_movie_image_bytes,
    get_tmdb_direct_image_bytes,
    poster_color_for_movie,
    render_poster_png,
)
from rag_engine import get_rag
from trailer_resolver import get_trailer_resolver

load_dotenv()

PROJECT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent
POSTER_CACHE_DIR = BACKEND_DIR / "poster_cache"
POSTER_CACHE_DIR.mkdir(exist_ok=True)

TMDB_API_KEYS = [
    "8265bd1679663a7ea12ac168da84d2e8",
    "c13c72b2203714b6bd27b876a40a5a3a",
]

app = Flask(
    __name__,
    static_folder=str(PROJECT_DIR / "assets"),
    static_url_path="/assets",
)
CORS(app)

_initialized = False


def ensure_ready():
    global _initialized
    if _initialized:
        return
    get_catalog()
    engine = get_engine()
    if not engine.ready:
        engine.train()
    get_rag()
    _initialized = True


def _fetch_tmdb_json(endpoint: str, params: dict | None = None) -> dict | None:
    params = dict(params or {})
    params["language"] = params.get("language", "en-US")
    for key in TMDB_API_KEYS:
        params["api_key"] = key
        query_str = urllib.parse.urlencode(params)
        url = f"https://api.themoviedb.org/3/{endpoint.lstrip('/')}?{query_str}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "MovieMate/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            continue
    return None


def _format_tmdb_movie_item(m: dict) -> dict:
    p = m.get("poster_path")
    b = m.get("backdrop_path")
    return {
        "id": m["id"],
        "title": m.get("title") or m.get("name") or "Untitled",
        "poster_path": f"/tmdb{p}" if p else f"/{m['id']}",
        "backdrop_path": f"/tmdb{b}" if b else (f"/tmdb{p}" if p else f"/{m['id']}"),
        "vote_average": float(m.get("vote_average") or 0),
        "release_date": str(m.get("release_date") or ""),
        "overview": str(m.get("overview") or ""),
        "genre_ids": m.get("genre_ids") or [],
        "popularity": float(m.get("popularity") or 0),
        "original_language": str(m.get("original_language") or "en"),
    }


# ---------------------------------------------------------------------------
# Static pages
# ---------------------------------------------------------------------------

@app.route("/")
@app.route("/index.html")
def home():
    return send_from_directory(PROJECT_DIR, "index.html")


@app.route("/detail.html")
def detail_page():
    return send_from_directory(PROJECT_DIR, "detail.html")


@app.route("/movie-list.html")
def movie_list_page():
    return send_from_directory(PROJECT_DIR, "movie-list.html")


@app.route("/signin")
@app.route("/SignIn&SignUp/")
@app.route("/SignIn&SignUp/index.html")
def signin_page():
    return send_from_directory(PROJECT_DIR / "SignIn&SignUp", "index.html")


@app.route("/SignIn&SignUp/<path:filename>")
def signin_assets(filename):
    return send_from_directory(PROJECT_DIR / "SignIn&SignUp", filename)


@app.route("/favicon.svg")
@app.route("/favicon.ico")
def favicon():
    return send_from_directory(PROJECT_DIR, "favicon.svg")


# ---------------------------------------------------------------------------
# Image routes (Local catalog + TMDb direct proxy)
# ---------------------------------------------------------------------------

@app.route("/api/images/<size>/tmdb/<path:tmdb_path>")
def tmdb_direct_image(size, tmdb_path):
    img_bytes, mimetype = get_tmdb_direct_image_bytes(size, tmdb_path)
    return Response(
        img_bytes,
        mimetype=mimetype,
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.route("/api/images/<size>/<int:movie_id>")
def movie_image(size, movie_id):
    ensure_ready()
    catalog = get_catalog()
    movie = catalog.get(movie_id)
    if not movie:
        # Try TMDb path fallback
        img_bytes, mimetype = get_tmdb_direct_image_bytes(size, f"{movie_id}.jpg")
        return Response(img_bytes, mimetype=mimetype, headers={"Cache-Control": "public, max-age=86400"})

    img_bytes, mimetype = get_movie_image_bytes(movie_id, size, movie)
    return Response(
        img_bytes,
        mimetype=mimetype,
        headers={"Cache-Control": "public, max-age=86400"},
    )


# ---------------------------------------------------------------------------
# TMDb-compatible API (Live TMDb with Local Fallback)
# ---------------------------------------------------------------------------

@app.route("/api/v3/genre/movie/list")
def genre_list():
    ensure_ready()
    data = _fetch_tmdb_json("genre/movie/list")
    if data and data.get("genres"):
        return jsonify(data)
    return jsonify({"genres": get_catalog().genres})


@app.route("/api/v3/movie/popular")
def popular_movies():
    ensure_ready()
    page = request.args.get("page", 1)
    data = _fetch_tmdb_json("movie/popular", {"page": page})
    if data and data.get("results"):
        return jsonify({
            "page": data.get("page", int(page)),
            "results": [_format_tmdb_movie_item(m) for m in data["results"]],
            "total_pages": data.get("total_pages", 1),
            "total_results": data.get("total_results", len(data["results"])),
        })
    return jsonify(get_catalog().list_popular(page))


@app.route("/api/v3/movie/top_rated")
def top_rated_movies():
    ensure_ready()
    page = request.args.get("page", 1)
    data = _fetch_tmdb_json("movie/top_rated", {"page": page})
    if data and data.get("results"):
        return jsonify({
            "page": data.get("page", int(page)),
            "results": [_format_tmdb_movie_item(m) for m in data["results"]],
            "total_pages": data.get("total_pages", 1),
            "total_results": data.get("total_results", len(data["results"])),
        })
    return jsonify(get_catalog().list_top_rated(page))


@app.route("/api/v3/movie/upcoming")
def upcoming_movies():
    ensure_ready()
    page = request.args.get("page", 1)
    data = _fetch_tmdb_json("movie/upcoming", {"page": page})
    if data and data.get("results"):
        return jsonify({
            "page": data.get("page", int(page)),
            "results": [_format_tmdb_movie_item(m) for m in data["results"]],
            "total_pages": data.get("total_pages", 1),
            "total_results": data.get("total_results", len(data["results"])),
        })
    return jsonify(get_catalog().list_upcoming(page))


@app.route("/api/v3/trending/movie/week")
def trending_movies():
    ensure_ready()
    page = request.args.get("page", 1)
    data = _fetch_tmdb_json("trending/movie/week", {"page": page})
    if data and data.get("results"):
        return jsonify({
            "page": data.get("page", int(page)),
            "results": [_format_tmdb_movie_item(m) for m in data["results"]],
            "total_pages": data.get("total_pages", 1),
            "total_results": data.get("total_results", len(data["results"])),
        })
    return jsonify(get_catalog().list_trending(page))


@app.route("/api/v3/search/movie")
def search_movies():
    ensure_ready()
    query = request.args.get("query", "")
    page = request.args.get("page", 1)
    if query:
        data = _fetch_tmdb_json("search/movie", {"query": query, "page": page, "include_adult": "false"})
        if data and data.get("results"):
            return jsonify({
                "page": data.get("page", int(page)),
                "results": [_format_tmdb_movie_item(m) for m in data["results"]],
                "total_pages": data.get("total_pages", 1),
                "total_results": data.get("total_results", len(data["results"])),
            })
    return jsonify(get_catalog().search(query, page))


@app.route("/api/v3/discover/movie")
def discover_movies():
    ensure_ready()
    page = request.args.get("page", 1)
    params = dict(request.args)
    params["page"] = page
    data = _fetch_tmdb_json("discover/movie", params)
    if data and data.get("results"):
        return jsonify({
            "page": data.get("page", int(page)),
            "results": [_format_tmdb_movie_item(m) for m in data["results"]],
            "total_pages": data.get("total_pages", 1),
            "total_results": data.get("total_results", len(data["results"])),
        })
    return jsonify(get_catalog().discover(request.args, page))


@app.route("/api/v3/movie/<int:movie_id>")
def movie_detail(movie_id):
    ensure_ready()
    # 1. Try local catalog
    payload = get_catalog().detail_payload(movie_id)
    if payload:
        return jsonify(payload)

    # 2. Live TMDb details for new 2026 movies
    data = _fetch_tmdb_json(f"movie/{movie_id}", {"append_to_response": "casts,videos,images,releases"})
    if data and data.get("id"):
        p = data.get("poster_path")
        b = data.get("backdrop_path")
        cast_raw = data.get("casts", {}).get("cast", []) or data.get("credits", {}).get("cast", [])
        crew_raw = data.get("casts", {}).get("crew", []) or data.get("credits", {}).get("crew", [])
        vids_raw = data.get("videos", {}).get("results", [])

        formatted_vids = []
        for v in vids_raw:
            if v.get("site") == "YouTube" and v.get("key"):
                formatted_vids.append({
                    "id": v.get("id", v["key"]),
                    "key": v["key"],
                    "name": v.get("name") or "Trailer",
                    "site": "YouTube",
                    "type": v.get("type") or "Trailer",
                    "official": v.get("official", True),
                })
        formatted_vids.sort(key=lambda item: 0 if item["type"] == "Trailer" else (1 if item["type"] == "Teaser" else 2))

        releases = data.get("releases", {}).get("countries", []) or []
        certification = "NR"
        for r in releases:
            if r.get("certification"):
                certification = r["certification"]
                break

        formatted = {
            "id": data["id"],
            "title": data.get("title") or data.get("name") or "Untitled",
            "overview": data.get("overview") or "",
            "tagline": data.get("tagline") or "",
            "release_date": data.get("release_date") or "",
            "runtime": data.get("runtime"),
            "vote_average": float(data.get("vote_average") or 0),
            "vote_count": int(data.get("vote_count") or 0),
            "popularity": float(data.get("popularity") or 0),
            "original_language": data.get("original_language") or "en",
            "status": data.get("status") or "Released",
            "genres": data.get("genres") or [],
            "genre_ids": [g["id"] for g in (data.get("genres") or []) if isinstance(g, dict) and "id" in g],
            "poster_path": f"/tmdb{p}" if p else f"/{data['id']}",
            "backdrop_path": f"/tmdb{b}" if b else (f"/tmdb{p}" if p else f"/{data['id']}"),
            "casts": {"cast": cast_raw, "crew": crew_raw},
            "videos": {"results": formatted_vids},
            "releases": {"countries": [{"certification": certification}]},
            "keywords": [],
            "directors": [c["name"] for c in crew_raw if c.get("job") == "Director"],
        }
        return jsonify(formatted)

    return jsonify({"success": False, "status_message": "Movie not found"}), 404


@app.route("/api/v3/movie/<int:movie_id>/recommendations")
def movie_recommendations(movie_id):
    ensure_ready()
    page = int(request.args.get("page", 1))
    per_page = 20
    results = get_catalog().recommendations_for(movie_id, limit=100)
    if not results:
        data = _fetch_tmdb_json(f"movie/{movie_id}/recommendations", {"page": page})
        if data and data.get("results"):
            return jsonify({
                "page": data.get("page", page),
                "results": [_format_tmdb_movie_item(m) for m in data["results"]],
                "total_pages": data.get("total_pages", 1),
                "total_results": data.get("total_results", len(data["results"])),
            })
    start = (page - 1) * per_page
    end = start + per_page
    return jsonify(
        {
            "page": page,
            "results": results[start:end],
            "total_pages": max(1, (len(results) + per_page - 1) // per_page),
            "total_results": len(results),
        }
    )


@app.route("/api/v3/movie/<int:movie_id>/videos")
def movie_videos(movie_id):
    ensure_ready()
    movie = get_catalog().get(movie_id)
    if movie:
        return jsonify(get_trailer_resolver().videos_payload(movie_id, movie["title"]))

    data = _fetch_tmdb_json(f"movie/{movie_id}/videos")
    if data and "results" in data:
        formatted_vids = []
        for v in data["results"]:
            if v.get("site") == "YouTube" and v.get("key"):
                formatted_vids.append({
                    "id": v.get("id", v["key"]),
                    "key": v["key"],
                    "name": v.get("name") or "Trailer",
                    "site": "YouTube",
                    "type": v.get("type") or "Trailer",
                    "official": v.get("official", True),
                })
        formatted_vids.sort(key=lambda item: 0 if item["type"] == "Trailer" else (1 if item["type"] == "Teaser" else 2))
        return jsonify({"id": movie_id, "results": formatted_vids})

    return jsonify({"id": movie_id, "results": []})


# ---------------------------------------------------------------------------
# ML recommendation API
# ---------------------------------------------------------------------------

@app.route("/recommend/<path:movie>")
def recommend(movie):
    ensure_ready()
    engine = get_engine()
    if not engine.ready:
        return jsonify({"error": "Recommendation model is not ready", "details": engine.error}), 503

    detailed = request.args.get("detailed", "false").lower() == "true"
    if detailed:
        catalog = get_catalog()
        enriched = []
        for item in engine.similar(movie, limit=8, include_scores=True):
            found = catalog.get(item.get("id")) if item.get("id") else catalog.get_by_title(item["title"])
            if not found:
                continue
            enriched.append(
                {
                    **catalog.card_payload(found),
                    "reasons": item.get("reasons", []),
                    "score": item.get("score"),
                }
            )
        if not enriched:
            # Fallback to catalog top rated
            return jsonify([catalog.card_payload(m) for m in catalog.movies[:8]])
        return jsonify(enriched)
    return jsonify(engine.similar(movie))


@app.route("/recommend/history", methods=["POST"])
def recommend_from_history():
    ensure_ready()
    engine = get_engine()
    if not engine.ready:
        return jsonify({"error": "Recommendation model is not ready", "details": engine.error}), 503

    data = request.get_json(silent=True) or {}
    watched = data.get("watched", [])
    limit = int(data.get("limit", 10))
    detailed = bool(data.get("detailed", False))

    if not isinstance(watched, list):
        return jsonify({"error": "watched must be a list of movie titles"}), 400

    results = engine.from_history(watched, limit=limit)
    if detailed:
        catalog = get_catalog()
        enriched = []
        for item in results:
            found = catalog.get_by_title(item["title"])
            if not found:
                continue
            enriched.append(
                {
                    **catalog.card_payload(found),
                    "reasons": item.get("reasons", []),
                    "score": item.get("score"),
                }
            )
        return jsonify(enriched)
    return jsonify([item["title"] for item in results])


@app.route("/ai/chat", methods=["POST"])
def ai_chat():
    ensure_ready()
    data = request.get_json(silent=True) or {}
    message = data.get("message", "")
    history = data.get("history", [])
    result = get_rag().chat(message, history)
    return jsonify(result)


@app.route("/ai/tonight", methods=["POST"])
def tonight_pick():
    ensure_ready()
    data = request.get_json(silent=True) or {}
    mood = data.get("mood", "")
    runtime = data.get("runtime")
    watched = data.get("watched", [])

    query_parts = ["recommend one movie for tonight"]
    if mood:
        query_parts.append(f"mood: {mood}")
    if runtime:
        query_parts.append(f"under {runtime} minutes")
    if watched:
        query_parts.append(f"similar taste to {', '.join(watched[:3])}")

    rag = get_rag()
    result = rag.chat(" ".join(query_parts))
    top = result["movies"][0] if result["movies"] else None
    return jsonify({"pick": top, "answer": result["answer"], "alternatives": result["movies"][1:4]})


@app.route("/health")
def health():
    ensure_ready()
    engine = get_engine()
    rag = get_rag()
    catalog = get_catalog()
    return jsonify(
        {
            "status": "ok",
            "moviesLoaded": len(catalog.movies),
            "modelReady": engine.ready,
            "ragReady": rag.ready,
            "modelError": engine.error,
            "ragError": rag.error,
            "geminiEnabled": bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")),
        }
    )


if __name__ == "__main__":
    ensure_ready()
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
