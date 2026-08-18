"""The web server. Collects input from the URL, calls queries.py, renders a page.

Deliberately contains no logic, for the same reason app.py did not: every read
lives in queries.py, so it can be run and checked from the terminal without
starting a server. If you find yourself computing something in this file, it
belongs in queries.py instead.

Run it:
    uvicorn main:app --reload
Then open http://127.0.0.1:8000
"""

from pathlib import Path

import pandas as pd
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import data
import queries
from api import api
from learn import books_search_link, youtube_search_link
from taxonomy import label

HERE = Path(__file__).parent
TEMPLATES = HERE / "templates"
STATIC = HERE / "static"

# Every template the routes render. Checked at startup rather than on the request
# that needs it, because StaticFiles fails loudly at import while Jinja fails
# quietly on the first render, so a flat unzip gets you one error now and another
# one three clicks later. This reports the whole lot at once.
NEEDED = ["base.html", "macros.html", "dashboard.html", "analysis.html", "study.html", "study_role.html", "role.html",
          "skills.html", "skill.html", "jobs.html", "candidates.html",
          "candidate.html", "missing.html"]


def check_layout():
    missing = []
    if not TEMPLATES.is_dir():
        missing.append("the templates/ folder")
    else:
        missing += [f"templates/{n}" for n in NEEDED
                    if not (TEMPLATES / n).is_file()]
    if not STATIC.is_dir():
        missing.append("the static/ folder")
    elif not (STATIC / "style.css").is_file():
        missing.append("static/style.css")

    if missing:
        raise SystemExit(
            "Missing files, all paths relative to main.py:\n  "
            + "\n  ".join(missing)
            + f"\n\nmain.py is in {HERE}\ntemplates/ and static/ have to be "
              "folders next to it. If you downloaded the files individually they "
              "arrived flat, so create the two folders and move them in.")


check_layout()

app = FastAPI(title="CareerLink")
app.include_router(api)
app.mount("/static", StaticFiles(directory=STATIC), name="static")
templates = Jinja2Templates(directory=TEMPLATES)


# ------------------------------------------------------------------ filters
# Formatting is presentation, so it lives here rather than in queries.py.
def money(value):
    """$160,000, or None so a template can render the absent marker instead."""
    return None if value is None or pd.isna(value) else f"${float(value):,.0f}"


def count(value):
    return "0" if value is None or pd.isna(value) else f"{int(value):,}"


def pct(value, places=1):
    return None if value is None or pd.isna(value) else f"{float(value):.{places}f}%"


def signed(value):
    """+22.5% or -3.1%. A premium reads wrong without its sign."""
    return None if value is None or pd.isna(value) else f"{float(value):+.1f}%"


def plural(value, word, many=None):
    """"1 employer" and "23 employers". Counts appear all over this site as the
    evidence behind a figure, and "1 employers" undermines the point."""
    n = 0 if value is None or pd.isna(value) else int(value)
    return word if n == 1 else (many or word + "s")


def pay_basis(companies):
    """Why a median is present or absent, phrased for the count it rests on."""
    n = 0 if companies is None or pd.isna(companies) else int(companies)
    if n == 0:
        return "no employer stated pay"
    return f"only {n} {plural(n, 'employer')} stated pay"


templates.env.filters.update(money=money, count=count, pct=pct, signed=signed,
                             plural=plural)
# Search links, not fabricated URLs. A link built from a query cannot rot or point
# at a video that was removed, and this project never invents a resource URL.
templates.env.globals.update(family_label=label, families=data.families,
                             pay_basis=pay_basis,
                             youtube=youtube_search_link,
                             books=books_search_link,
                             skill_label=lambda s: data.skill_labels.get(s, s))


def page(request, name, **context):
    return templates.TemplateResponse(request, name, context)


def missing(request, what, where, back_url, back_label):
    """One shared not-found page. Says what to do next, not just what failed."""
    return templates.TemplateResponse(
        request, "missing.html",
        {"what": what, "where": where, "back_url": back_url,
         "back_label": back_label}, status_code=404)


# -------------------------------------------------------------------- routes
# ------------------------------------------------------------ React frontend
# The built app is served by FastAPI rather than by a second server, so
# `python main.py` still starts the whole site with one command and there is no
# CORS to configure in production. `npm run dev` inside web/ proxies /api back
# here when you want hot reload while editing the frontend.
APP_DIR = STATIC / "app"


@app.get("/", response_class=HTMLResponse)
def root():
    return RedirectResponse("/app/") if APP_DIR.is_dir() else legacy_home_stub()


def legacy_home_stub():
    return HTMLResponse(
        "<h1>Frontend not built</h1><p>Run <code>npm install &amp;&amp; npm run build</code> "
        "inside <code>web/</code>, then reload.</p>", status_code=503)


@app.get("/app/{path:path}", response_class=HTMLResponse)
def react_app(path: str = ""):
    """Serve the built React app, and hand every unknown path back to it.

    React Router owns the URLs under /app, so a deep link like /app/skills/Docker
    has no file behind it. Returning index.html lets the router resolve it, which
    is what makes refreshing a deep link work instead of 404ing.
    """
    if not APP_DIR.is_dir():
        return legacy_home_stub()
    target = APP_DIR / path
    if path and target.is_file():
        return FileResponse(target)
    return FileResponse(APP_DIR / "index.html")


@app.get("/legacy", response_class=HTMLResponse)
def home(request: Request):
    """The consumer front page. No coverage or data-quality figures here: someone
    deciding what to learn needs the market, not the method. The method lives on
    /analysis and is linked from the footer."""
    return page(request, "dashboard.html",
                stats=queries.headline(), roles=queries.top_roles(),
                paid=queries.best_paid_roles(), skills=queries.top_skills(),
                remote_rows=[{"label": r["family"], "value": r["pct"],
                              "display": "%.0f" % r["pct"]}
                             for r in queries.remote_friendly()])


@app.get("/analysis", response_class=HTMLResponse)
def analysis(request: Request):
    """The dashboard. Chart-ready rows are shaped here rather than in queries.py,
    because "label, value, display, basis" is a presentation format, not a fact
    about the data. queries.py returns the numbers; this turns them into marks."""
    m = queries.market()
    state = queries.pay_disclosure_by_state()
    missing = queries.missing_level()

    fam_postings = [{"label": r["label"], "value": r["postings"],
                     "display": f"{r['postings']:,}"} for r in m]
    fam_pay = sorted(
        [{"label": r["label"], "value": r["median_pay"],
          "display": money(r["median_pay"]) or "",
          "basis": f"{r['paid_n']:,} disclosed"} for r in m],
        key=lambda r: -(r["value"] or 0))
    fam_remote = sorted(
        [{"label": r["label"], "value": r["remote_pct"],
          "display": f"{r['remote_pct']:.0f}" if r["remote_pct"] is not None else "",
          "basis": f"of {r['told_n']:,} that stated"} for r in m],
        key=lambda r: -(r["value"] or 0))
    state_top = [{"label": r["state"] + ("  mandate" if r["mandate"] else ""),
                  "value": r["pct"], "display": f"{r['pct']:.1f}",
                  "basis": f"{r['postings']:,} postings"} for r in state["top"]]
    level_rows = [{"label": r["label"], "value": r["unspecified_pct"],
                   "display": f"{r['unspecified_pct']:.0f}",
                   "basis": (f"unlabelled ${r['unspecified_pay']:,.0f} vs senior "
                             f"${r['senior_pay']:,.0f}")
                            if r["unspecified_pay"] and r["senior_pay"] else "too few salaries"}
                  for r in missing["rows"]]

    return page(request, "analysis.html",
                kpis=queries.kpis(), state=state, missing=missing,
                repost=queries.repost_inflation(),
                quality=queries.data_quality(),
                subs=queries.substitute_balance(),
                worksite_coverage=100 * data.jobs.worksite_stated.fillna(False).mean(),
                fam_postings=fam_postings,
                fam_postings_max=max(r["value"] for r in fam_postings),
                fam_pay=fam_pay,
                fam_pay_max=max(r["value"] for r in fam_pay if r["value"]),
                fam_remote=fam_remote, state_top=state_top, level_rows=level_rows)


# ------------------------------------------- job seeker tab 1: study guide
@app.get("/study", response_class=HTMLResponse)
def study(request: Request, q: str = "", family: str = ""):
    rows, scored, pool = queries.roles_by_context(q, family or None, top_n=20)
    return page(request, "study.html", rows=rows, scored=scored, pool=pool,
                q=q, family=family, help=queries.CONTEXT_HELP)


@app.get("/study/{role:path}", response_class=HTMLResponse)
def study_role(request: Request, role: str):
    found = queries.role_detail(role)
    if found is None:
        return missing(request, "role", role, "/study", "Study guide")
    fam = found["role"].job_family
    return page(request, "study_role.html",
                plan=queries.study_plan(role),
                certs=queries.certifications_for(fam),
                cert_gone=queries.certification_note(fam), **found)


# ---------------------------------------------- recruiter tab 1: the market
@app.get("/hiring", response_class=HTMLResponse)
def hiring(request: Request, q: str = "", family: str = "", sort: str = "postings"):
    if (q or "").strip():
        rows, scored, pool = queries.roles_by_context(q, family or None, top_n=25)
        total = pool
    else:
        rows, total = queries.role_list(family or None, sort)
        scored = False
    return page(request, "hiring.html", rows=rows, total=total, scored=scored,
                q=q, family=family, sort=sort, help=queries.CONTEXT_HELP)


@app.get("/roles/{role:path}", response_class=HTMLResponse)
def role(request: Request, role: str):
    found = queries.role_detail(role)
    if found is None:
        return missing(request, "role", role, "/hiring", "All roles")
    fam = found["role"].job_family
    return page(request, "role.html",
                certs=queries.certifications_for(fam),
                cert_gone=queries.certification_note(fam), **found)


# --------------------------------------------- job seeker tab 3: the skills
@app.get("/skills", response_class=HTMLResponse)
def skills(request: Request, q: str = "", category: str = "", skill: str = ""):
    rows, total = queries.skill_list(q or None, category or None)
    related = queries.related_to(skill) if skill else []
    return page(request, "skills.html", rows=rows, total=total, q=q,
                category=category, skill=skill, related=related,
                categories=data.categories,
                all_skills=queries.skills_in_category(category or None))


@app.get("/skills/{skill:path}", response_class=HTMLResponse)
def skill(request: Request, skill: str, variety: float = 0.7):
    found = queries.skill_detail(skill)
    if found is None:
        return missing(request, "skill", skill, "/skills", "All skills")
    comps, subs = queries.skill_neighbours(skill, variety=variety)
    return page(request, "skill.html", complements=comps, substitutes=subs,
                variety=variety, **found)


# ------------------------------------------------ job seeker tab 2: the jobs
@app.get("/jobs", response_class=HTMLResponse)
def jobs(request: Request, q: str = "", family: str = "", worksite: str = "",
         seniority: str = "", dupes: str = ""):
    rows, total, stated, scored = queries.jobs_by_context(
        q, family or None, worksite or None, seniority or None,
        dedupe=not dupes)
    return page(request, "jobs.html", rows=rows, total=total, stated=stated,
                scored=scored, q=q, family=family, worksite=worksite,
                seniority=seniority, dupes=dupes, help=queries.CONTEXT_HELP)


# ----------------------------------------- recruiter tab 2: the candidates
@app.get("/candidates", response_class=HTMLResponse)
def candidates(request: Request, q: str = "", role: str = "",
               synthetic: str = "", top: int = 10):
    rows, pool, scored = queries.candidates_by_context(
        q, role or None, include_synthetic=bool(synthetic), top_n=top)
    return page(request, "candidates.html", rows=rows, pool=pool, scored=scored,
                q=q, role=role, synthetic=synthetic, top=top,
                summary=queries.candidate_summary,
                role_options=queries.role_options(),
                help=queries.CONTEXT_HELP)


@app.get("/candidates/{candidate_id}", response_class=HTMLResponse)
def candidate(request: Request, candidate_id: str):
    found = queries.candidate_detail(candidate_id)
    if found is None:
        return missing(request, "candidate", candidate_id, "/candidates",
                       "All candidates")
    return page(request, "candidate.html", **found)


print("loaded:", data.summary())


if __name__ == "__main__":
    # So `python main.py` and PyCharm's run button start the server. Without this,
    # running the file just imports it, prints the line above and exits 0, because
    # nothing in the module actually listens on a port.
    #
    # The app is passed as the string "main:app" rather than as the object, because
    # reload works by re-importing that string in a fresh subprocess. Passing the
    # object silently disables reload.
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
