# CareerLink

A job market app: search real postings, see what skills are in demand per role,
and browse candidate resumes. FastAPI backend, React frontend (built and served
as static files, so you don't need Node just to run it).

## Requirements

- Python 3.11+
- Git LFS (`git lfs install`, one-time) — `jobs_enriched.csv` is tracked with LFS

## Setup

```
git clone https://github.com/Abdulazizmald/CareerLink.git
cd CareerLink
pip install -r requirements-deploy.txt
```

### API keys

Video and book recommendations on the study guide pages call the YouTube Data
API and Google Books API. Create `api_keys.py` in the project root:

```python
YOUTUBE_API_KEY = "your-key-here"
GOOGLE_BOOKS_API_KEY = "your-key-here"
```

(Or set `YOUTUBE_API_KEY` / `GOOGLE_BOOKS_API_KEY` as environment variables
instead — either works, and env vars take priority.) Without keys, those
sections just show as unavailable; the rest of the app works fine.

## Run

```
python main.py
```

Open http://127.0.0.1:8000 — it redirects to `/app/`.

## Frontend development

The built frontend is already committed under `static/app/`, so the steps
above are all you need to run the site. If you want to edit the React source
in `web/src/`, install Node 20+, then:

```
cd web
npm install
npm run build   # writes into static/app/, picked up by FastAPI
```

For hot reload while editing, run `python main.py` in one terminal and
`cd web && npm run dev` in another — Vite proxies `/api` calls to FastAPI.

## Rebuilding the data

The `build_*.py` scripts regenerate the CSVs the app reads from raw source
data (not included in this repo) — see `Requirements.txt` for the extra
dependencies they need, like `sentence-transformers`. Not required to run
the app itself.
