# CareerLink: running the React frontend

The site is now a React app served by FastAPI. One process, one command.

## First time

Install Node 20 or newer from <https://nodejs.org>, then:

    cd web
    npm install
    npm run build
    cd ..
    python main.py

Open <http://127.0.0.1:8000>. It redirects to `/app/`.

`npm run build` writes into `static/app/`, which FastAPI serves. There is no
second server in production and no CORS to configure.

## While editing the frontend

Two terminals:

    python main.py          # terminal 1, the API on :8000
    cd web && npm run dev    # terminal 2, hot reload on :5173

Open the port Vite prints. `/api` calls are proxied to FastAPI, so you are
editing against real data with instant reload. Run `npm run build` again when you
are done so the FastAPI-served copy is up to date.

## What is where

    api.py                  JSON endpoints. Renames job_family to category and
                            never mentions the two data sources.
    web/src/pages/          one file per page
    web/src/components/     UI.jsx (states, chips) and Charts.jsx (Recharts)
    web/src/lib/api.js      useApi hook: one loading and error path for every page
    static/app/             the build output. Do not edit; it is regenerated.

## PyCharm

No IDE change needed. PyCharm handles the JS side; the run configuration for
`main.py` is unchanged.

## Still Jinja

`/analysis` is still a server-rendered page, on purpose. It is a written report
rather than an interactive view, and rewriting it in React would gain nothing.
The `templates/` folder and its other files are now unused but not deleted.
