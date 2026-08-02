# MovieMate

AI-powered movie app that runs **fully offline from your local dataset** — no TMDb API required (works in India).

## Features

- Browse 4,800+ movies from local TMDB CSV data
- Search, genres, popular / trending / top-rated sections
- ML recommendations with explainable reasons
- RAG vector chatbot (`MovieMate AI` button)
- Generated SVG posters (no blocked CDN)
- Optional Gemini answers when `GEMINI_API_KEY` is set

## Quick start

```bash
cd backend
pip install -r requirements.txt
cd ..
python run.py
```

Open **http://127.0.0.1:5000**

First run builds:
- `movie_catalog.json`
- `movies.pkl`, `similarity.pkl`
- RAG vector index (`rag_*.pkl`)

## Optional: smarter AI replies

Copy `backend/.env.example` to `backend/.env` and add:

```
GEMINI_API_KEY=your_key_here
```

Without it, the chatbot still works using local RAG + template answers.

## API

| Endpoint | Purpose |
|----------|---------|
| `/api/v3/*` | TMDb-compatible movie data (local) |
| `/recommend/<title>` | Similar movies |
| `/recommend/history` | Personalized picks |
| `/ai/chat` | RAG chatbot |
| `/health` | Server status |

## Project structure

```
backend/
  app.py           Flask server
  data_store.py    Local movie catalog
  ml_engine.py     TF-IDF recommendations
  rag_engine.py    Vector RAG chatbot
  train_model.py   Bootstrap script
assets/js/
  api.js           Routes all movie calls to local API
  chatbot.js       AI chat widget
```

## CAP615 demo script

1. Open home — movies load without TMDb
2. Search "Avatar" — local search
3. Open detail — AI similar + history recommendations
4. Click **AI** button — ask "intense sci-fi under 2 hours"

## Author & License

- **Author**: [Dushyant-code2003](https://github.com/Dushyant-code2003)
- **Repository**: [Movie-Recommendation-Website](https://github.com/Dushyant-code2003/Movie-Recommendation-Website)
- **License**: [MIT License](LICENSE) © 2026 Dushyant

