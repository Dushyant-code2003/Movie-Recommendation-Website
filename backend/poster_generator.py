"""Generate or fetch real poster/backdrop images for movies."""

from __future__ import annotations

import html
import io
import json
import textwrap
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from data_store import GENRE_PALETTE

BACKEND_DIR = Path(__file__).resolve().parent
POSTER_CACHE_DIR = BACKEND_DIR / "poster_cache"
POSTER_CACHE_DIR.mkdir(exist_ok=True)

TMDB_API_KEYS = [
    "8265bd1679663a7ea12ac168da84d2e8",
    "c13c72b2203714b6bd27b876a40a5a3a",
]

_path_cache: dict[int, dict[str, str | None]] = {}


def _gradient_background(width: int, height: int, color: str) -> Image.Image:
    base = Image.new("RGB", (width, height), "#111111")
    draw = ImageDraw.Draw(base)
    r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
    for y in range(height):
        ratio = y / max(height - 1, 1)
        red = int(r * (1 - ratio * 0.75))
        green = int(g * (1 - ratio * 0.75))
        blue = int(b * (1 - ratio * 0.75))
        draw.line([(0, y), (width, y)], fill=(red, green, blue))
    return base


def _load_font(size: int):
    for name in ("arial.ttf", "Arial.ttf", "segoeui.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render_poster_png(title: str, subtitle: str, color: str, width: int, height: int) -> bytes:
    image = _gradient_background(width, height, color)
    draw = ImageDraw.Draw(image)

    title_font = _load_font(max(18, width // 14))
    subtitle_font = _load_font(max(12, width // 24))
    brand_font = _load_font(max(10, width // 30))

    wrapped = textwrap.fill(html.unescape(title), width=max(12, width // 18))
    bbox = draw.multiline_textbbox((0, 0), wrapped, font=title_font, spacing=6)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.multiline_text(
        ((width - text_w) / 2, height * 0.34 - text_h / 2),
        wrapped,
        font=title_font,
        fill="#ffffff",
        align="center",
        spacing=6,
    )

    sub = html.unescape(subtitle)
    sub_bbox = draw.textbbox((0, 0), sub, font=subtitle_font)
    sub_w = sub_bbox[2] - sub_bbox[0]
    draw.text(((width - sub_w) / 2, height * 0.62), sub, font=subtitle_font, fill="#cccccc")

    draw.rectangle((0, height - 6, width, height), fill="#00d7fd")
    brand = "MovieMate"
    brand_bbox = draw.textbbox((0, 0), brand, font=brand_font)
    brand_w = brand_bbox[2] - brand_bbox[0]
    draw.text(((width - brand_w) / 2, height - 28), brand, font=brand_font, fill="#00d7fd")

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def poster_color_for_movie(movie: dict) -> str:
    genre = movie["genres"][0]["name"] if movie.get("genres") else "Drama"
    return movie.get("poster_color") or GENRE_PALETTE.get(genre, "#00d7fd")


def fetch_tmdb_paths(movie_id: int) -> dict[str, str | None]:
    if movie_id in _path_cache:
        return _path_cache[movie_id]

    for key in TMDB_API_KEYS:
        try:
            url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={key}"
            req = urllib.request.Request(url, headers={"User-Agent": "MovieMate/1.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                result = {
                    "poster_path": data.get("poster_path"),
                    "backdrop_path": data.get("backdrop_path"),
                }
                _path_cache[movie_id] = result
                return result
        except Exception:
            continue

    _path_cache[movie_id] = {"poster_path": None, "backdrop_path": None}
    return _path_cache[movie_id]


def get_movie_image_bytes(movie_id: int, size: str, movie: dict) -> tuple[bytes, str]:
    is_backdrop = size.startswith("w1280") or size.startswith("w780")
    cache_file = POSTER_CACHE_DIR / f"{movie_id}_{size}.jpg"

    if cache_file.exists():
        return cache_file.read_bytes(), "image/jpeg"

    # Try TMDB real image download
    paths = fetch_tmdb_paths(movie_id)
    img_path = paths["backdrop_path"] if is_backdrop else paths["poster_path"]

    if img_path:
        cdn_size = "w1280" if is_backdrop else ("w154" if "154" in size else "w500")
        cdn_url = f"https://image.tmdb.org/t/p/{cdn_size}{img_path}"
        try:
            req = urllib.request.Request(cdn_url, headers={"User-Agent": "MovieMate/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                img_bytes = resp.read()
                if img_bytes:
                    cache_file.write_bytes(img_bytes)
                    return img_bytes, "image/jpeg"
        except Exception:
            pass

    png_cache = POSTER_CACHE_DIR / f"{movie_id}_{size}.png"
    if png_cache.exists():
        return png_cache.read_bytes(), "image/png"

    # Fallback to generated PIL image
    if is_backdrop:
        width, height = 1280, 720
    elif size.startswith("w154"):
        width, height = 154, 231
    else:
        width, height = 342, 513

    genre = movie["genres"][0]["name"] if movie.get("genres") else "Movie"
    color = poster_color_for_movie(movie)
    release_date = movie.get("release_date") or ""
    subtitle = f"{genre} · {release_date[:4] if release_date else 'N/A'}"
    png_bytes = render_poster_png(movie["title"], subtitle, color, width, height)
    png_cache.write_bytes(png_bytes)
    return png_bytes, "image/png"


def get_tmdb_direct_image_bytes(size: str, path: str) -> tuple[bytes, str]:
    path_clean = path.strip("/").replace("/", "_")
    cache_file = POSTER_CACHE_DIR / f"tmdb_{size}_{path_clean}"
    if cache_file.exists():
        return cache_file.read_bytes(), "image/jpeg"

    is_backdrop = size.startswith("w1280") or size.startswith("w780")
    cdn_size = "w1280" if is_backdrop else ("w154" if "154" in size else "w500")
    cdn_url = f"https://image.tmdb.org/t/p/{cdn_size}/{path_clean}"
    try:
        req = urllib.request.Request(cdn_url, headers={"User-Agent": "MovieMate/1.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            img_bytes = resp.read()
            if img_bytes:
                cache_file.write_bytes(img_bytes)
                return img_bytes, "image/jpeg"
    except Exception:
        pass

    png_bytes = render_poster_png("Movie", "MovieMate", "#00d7fd", 342, 513)
    return png_bytes, "image/png"
