# Deploying CareerLink

One process, one paid Render service. No second server, no Node on the host --
`static/app/` is already built and committed, so Render only ever runs Python.

## What's actually deployed

The live server only imports `main.py`, `api.py`, `data.py`, `queries.py`,
`context.py`, `matcher.py`, `taxonomy.py`, `config.py`, `resources.py`,
`learn.py`, `diversity.py`, `recommend.py`, `prep.py`, the small CSVs they
read, `jobs_enriched.csv`, `candidates.csv`, and `static/app/`. Checked by
walking the actual import graph, not guessed.

Everything else -- `job_summary.csv`, `linkedin_job_postings.csv`,
`job_skills.csv`, `tech_jobs.csv`, `Resume.csv`, `job_vectors.npy`, and the
`build_*.py` scripts that read them -- only exists to regenerate the small
files above. None of it ships. See `.gitignore`.

`jobs_enriched.csv` is 255MB (real, untruncated posting text), over GitHub's
100MB hard limit, so it's tracked with Git LFS instead of plain git. See
`.gitattributes`.

`requirements-deploy.txt` is the real runtime dependency list -- fastapi,
uvicorn, jinja2, pandas, numpy, scikit-learn (context.py's TF-IDF search),
requests (learn.py's API calls). `sentence-transformers`/`torch` are
build-script-only and deliberately left out to keep the deploy install fast.
`Requirements.txt` (capital R) is still the one to use for local dev, since
that's what runs the `build_*.py` scripts.

## One-time setup

1. Create an empty repo on GitHub (no README/license, this repo already has
   files).
2. From this folder:
   ```
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/<you>/<repo>.git
   git branch -M main
   git push -u origin main
   ```
   Git LFS uploads `jobs_enriched.csv` automatically as part of that push --
   expect it to take a few minutes on a home connection.
3. On Render: New -> Blueprint, connect the GitHub repo. `render.yaml` at the
   repo root defines the service, so Render fills in the build and start
   commands itself.
4. Render will prompt for `YOUTUBE_API_KEY` and `GOOGLE_BOOKS_API_KEY` (they're
   marked `sync: false` in `render.yaml`, meaning "ask, don't store in the
   file"). Paste the same values from your local `api_keys.py`.
5. Deploy. First build installs `requirements-deploy.txt` and starts
   `uvicorn main:app --host 0.0.0.0 --port $PORT`.

## Updating the live site later

```
git add .
git commit -m "..."
git push
```
Render redeploys automatically on every push to `main`, at the same URL --
nothing about the domain changes unless you explicitly add a custom one later
in the Render dashboard.

## Rebuilding the data

If you regenerate `roles.csv`, `candidates.csv`, `jobs_enriched.csv`, etc. with
the `build_*.py` scripts, commit the new versions the same way and push. The
raw source files those scripts read (`job_summary.csv` and friends) stay local
and gitignored either way.
