"""JSON endpoints for the React frontend.

Naming note, and it is not cosmetic. The two data sources have different internal
taxonomies, and the site used to say so on every page: "2026 index categories",
"2024 job families", "6 of 6", "11 of 11". That is the engineer's view of the
problem leaking into the product. A person looking for work does not need to know
there are two sources, only what the job market looks like.

So this layer renames as it serves:
    job_family  ->  category
    "2026 index" / "2024 postings" -> nothing, the distinction is not surfaced
The Python underneath keeps its own names, because the two taxonomies really are
different things and merging them in the data would be a lie. They are merged
only in the words shown to a user.
"""

import math

import pandas as pd
from fastapi import APIRouter

import data
import queries
import resources
from taxonomy import label

api = APIRouter(prefix="/api")


def clean(value):
    """Anything pandas produced, made safe for json.dumps.

    NaN is a float in Python but is not valid JSON, and `where(notna(), None)`
    does not catch it once a column has been cast back to float64. Rather than
    guard at every endpoint, everything returned here passes through one
    conversion, so a NaN cannot leak from a route that was added later.
    """
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if value is None or value is pd.NaT:
        return None
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value
    if isinstance(value, (pd.Timestamp,)):
        return str(value)
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):          # numpy scalars
        return clean(value.item())
    return value


def _rows(frame, columns=None):
    """DataFrame to a list of plain dicts, with NaN turned into null."""
    if frame is None or len(frame) == 0:
        return []
    out = frame[columns] if columns else frame
    return clean(out.to_dict("records"))


def _category(fam):
    return {"id": fam, "name": label(fam)}


@api.get("/meta")
def meta():
    """Everything the frontend needs to build its dropdowns, fetched once."""
    return clean({
        "categories": [_category(f) for f in data.families],
        "skillGroups": data.categories,
        "worksites": ["remote", "hybrid", "onsite"],
        "levels": ["junior", "mid", "senior", "lead", "principal"],
        "roles": queries.role_options(),
        "skills": data.vocab,
        "counts": queries.headline(),
    })


@api.get("/home")
def home():
    stats = queries.headline()
    return clean({
        "stats": stats,
        "topRoles": queries.top_roles(8),
        "bestPaid": queries.best_paid_roles(6),
        "topSkills": queries.top_skills(10),
        "remote": queries.remote_friendly(6),
        "byCategory": [
            {"category": r["label"], "postings": r["postings"],
             "pay": r["median_pay"], "paidCount": r["paid_n"],
             "remote": r["remote_pct"]}
            for r in queries.market()
        ],
        "levels": queries.level_mix(),
    })


@api.get("/roles")
def roles(q: str = "", category: str = "", sort: str = "postings", limit: int = 30):
    if (q or "").strip():
        rows, scored, pool = queries.roles_by_context(q, category or None, limit)
        total = pool
    else:
        rows, total = queries.role_list(category or None, sort, limit)
        scored = False
    cols = ["role", "role_label", "job_family", "postings", "companies",
            "median_salary", "salary_companies", "pct_senior_or_above",
            "top_skills"]
    if scored:
        cols.append("relevance")
    out = _rows(rows, cols)
    for r in out:
        r["category"] = label(r.pop("job_family"))
        r["skills"] = [s for s in str(r.pop("top_skills") or "").split(", ") if s]
    return clean({"rows": out, "total": total, "scored": scored})


@api.get("/roles/{role:path}")
def role(role: str):
    found = queries.role_detail(role)
    if found is None:
        return {"error": "not found"}
    r = found["role"]
    fam = r.job_family
    return clean({
        "role": role,
        "label": r.role_label,
        "category": label(fam),
        "postings": int(r.postings),
        "companies": int(r.companies),
        "pay": clean(r.median_salary),
        "payEmployers": int(r.salary_companies),
        "seniorPct": float(r.pct_senior_or_above),
        "remotePct": clean(r.pct_flexible_when_stated),
        "summary": str(r.summary),
        "skills": _rows(found["skills"], ["skill_name", "jobs", "share_pct"]),
        "plan": [
            {"title": s["title"], "why": s["why"],
             "skills": [{"name": x.skill_name, "share": x.share_pct}
                        for x in s["skills"]]}
            for s in queries.study_plan(role)
        ],
        "certifications": [
            {"name": c["name"], "provider": c["provider"], "level": c["level"],
             "focus": c["focus"], "url": c.get("url")}
            for c in queries.certifications_for(fam)
        ],
        "related": _rows(found["siblings"], ["role", "role_label", "postings"]),
    })


@api.get("/jobs")
def jobs(q: str = "", category: str = "", worksite: str = "", level: str = "",
         dupes: bool = False, limit: int = 50):
    rows, total, stated, scored = queries.jobs_by_context(
        q, category or None, worksite or None, level or None,
        dedupe=not dupes, top_n=limit)
    out = []
    for src in rows.itertuples():
        out.append({
            "link": src.job_link, "title": src.job_title, "company": src.company,
            "location": src.job_location, "category": label(src.job_family),
            # a worksite is only reported when the advert actually said one, so
            # the default-to-onsite assumption never reaches a user as a fact
            "worksite": src.worksite if src.worksite_stated else None,
            "level": None if src.seniority == "unspecified" else src.seniority,
            "pay": None if src.salary_label == "Undisclosed" else src.salary_label,
            "relevance": float(src.relevance) if scored else None,
            "description": src.description,
        })
    return clean({"rows": out, "total": total,
                  "statedPct": round(100 * stated, 0), "scored": scored})


@api.get("/skills")
def skills(q: str = "", group: str = "", limit: int = 60):
    rows, total = queries.skill_list(q or None, group or None, limit)
    out = []
    for r in rows.itertuples():
        out.append({"name": r.skill_name, "label": r.label,
                    "postings": int(r.postings),
                    "description": data.descriptions.get(r.skill_name)})
    return clean({"rows": out, "total": total})


@api.get("/skills/{skill:path}")
def skill(skill: str):
    found = queries.skill_detail(skill)
    if found is None:
        return {"error": "not found"}
    comps, subs = queries.skill_neighbours(skill)

    def pack(frame, relation):
        return [{"name": r.skill_name, "strength": float(r.association),
                 "overlap": None if r.meaning is None else float(r.meaning),
                 "relation": relation}
                for r in frame.itertuples()] if len(frame) else []

    demand = [{"category": r.family_label, "postings": int(r.demand_count),
               "share": float(r.demand_pct)}
              for r in found["post_rows"].itertuples()]
    pay = [{"category": r.family_label, "pay": float(r.median_salary),
            "premium": float(r.salary_premium_pct), "employers": int(r.companies)}
           for r in found["pay_rows"].itertuples()]
    return clean({"name": skill, "description": found["description"],
                  "learnNext": pack(comps, "next"),
                  "alternatives": pack(subs, "covered"),
                  "demand": demand, "pay": pay})


@api.get("/candidates")
def candidates(q: str = "", role: str = "", synthetic: bool = False,
               limit: int = 10):
    rows, pool, scored = queries.candidates_by_context(
        q, role or None, include_synthetic=synthetic, top_n=limit)
    out = []
    for r in rows.itertuples():
        d = r._asdict()
        out.append({
            "id": r.candidate_id,
            "real": r.source == "resume_dataset",
            "role": r.inferred_role or None,
            "degree": r.degree or None,
            "major": r.major or None,
            "gpa": r.gpa or None,
            "years": r.years_experience or None,
            "skills": [s for s in str(r.skills or "").split(", ") if s],
            "summary": queries.candidate_summary(d),
            "bio": queries.candidate_bio(d),
            "relevance": float(r.relevance) if scored else None,
        })
    return clean({"rows": out, "pool": pool, "scored": scored})


@api.get("/candidates/{candidate_id}")
def candidate(candidate_id: str):
    found = queries.candidate_detail(candidate_id)
    if found is None:
        return {"error": "not found"}
    c = found["candidate"]
    return clean({"id": c.candidate_id, "real": c.source == "resume_dataset",
            "role": c.inferred_role or None, "degree": c.degree or None,
            "major": c.major or None, "gpa": c.gpa or None,
            "years": c.years_experience or None, "skills": found["skills"],
            "summary": queries.candidate_summary(c.to_dict()),
            "bio": queries.candidate_bio(c.to_dict()),
            "resume": c.resume_text})


# ------------------------------------------------------------------- learn
# One video and one book per skill (the study guide dropdown), three of each
# per role (the bottom of the role page). resources.py caches both by query,
# so opening the same skill twice never spends API quota twice.
@api.get("/learn/skill/{skill:path}")
def learn_skill(skill: str):
    videos, video_error = resources.videos_for(f"{skill} tutorial", n=1)
    books, book_error = resources.books_for(skill, n=1)
    return clean({
        "video": videos[0] if videos else None, "videoError": video_error,
        "book": books[0] if books else None, "bookError": book_error,
    })


@api.get("/learn/role/{role:path}")
def learn_role(role: str):
    found = queries.role_detail(role)
    if found is None:
        return {"error": "not found"}
    role_label = found["role"].role_label
    videos, video_error = resources.videos_for(f"{role_label} career guide", n=3)
    books, book_error = resources.books_for(role_label, n=3)
    return clean({
        "videos": videos, "videosError": video_error,
        "books": books, "booksError": book_error,
    })
