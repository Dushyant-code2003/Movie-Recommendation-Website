"""One-command bootstrap: build catalog, train ML, build RAG index, warm poster cache."""

from data_store import get_catalog
from ml_engine import get_engine
from poster_generator import poster_color_for_movie, render_poster_png
from rag_engine import get_rag
from pathlib import Path

POSTER_CACHE_DIR = Path(__file__).resolve().parent / "poster_cache"
POSTER_CACHE_DIR.mkdir(exist_ok=True)


def warm_poster_cache(limit=60):
    from poster_generator import get_movie_image_bytes
    catalog = get_catalog()
    sizes = ["w342", "w1280", "w154"]
    for movie in catalog.movies[:limit]:
        for size_name in sizes:
            try:
                get_movie_image_bytes(movie["id"], size_name, movie)
            except Exception:
                pass
    print(f"  Poster cache warmed for top {limit} movies")


def main():
    print("Building local movie catalog...")
    catalog = get_catalog()
    print(f"  {len(catalog.movies)} movies indexed")

    print("Training recommendation model...")
    engine = get_engine()
    if not engine.ready:
        engine.train()
    print("  Recommendation model ready")

    print("Building RAG vector index...")
    rag = get_rag()
    if not rag.ready:
        rag.build()
    print("  RAG index ready")

    print("Warming poster cache...")
    warm_poster_cache()
    print("  Poster cache ready")

    print("\nMovieMate backend is ready. Run: python app.py")


if __name__ == "__main__":
    main()
