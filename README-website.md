# Running the website

## One time

    pip install fastapi "uvicorn[standard]" jinja2

Rename `skillscarcityindex.csv` to `skill-scarcity-index.csv`. Five scripts and
`data.py` look for the hyphenated name.

## Files this adds

    data.py                 every table, loaded once at import
    queries.py              every read the site performs
    main.py                 FastAPI routes, no logic
    smoke.py                hits all 32 routes, no browser needed
    templates/*.html        9 templates
    static/style.css        one stylesheet, no framework

## Run

    uvicorn main:app --reload

Then open http://127.0.0.1:8000

## Check

    python data.py          what loaded, and what got suppressed
    python queries.py       every read, from the terminal
    python smoke.py         all 32 routes, expects 29 x 200 and 3 x 404

## Deliberately not in this version

Search by description. Ranking postings or roles by meaning needs
`job_vectors.npy` and `role_vectors.npy`. Filters work; relevance order does not
exist yet. The jobs page says so on the page rather than hiding it.

The "skills these jobs ask for" panel. `jobs_enriched.csv` has no description
column, and scanning titles instead finds almost nothing, because a title names a
role while a description names the tools. It returns with `tech_jobs.csv`.
