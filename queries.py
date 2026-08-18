"""Every read the website performs. main.py routes call these and nothing else.

Same split as the Streamlit version: the interface collects input and draws
output, the logic lives here. That is what let app.py be replaced without
rewriting anything underneath it, and it is worth keeping.

Each function returns plain frames, dicts and lists. None of them know that a web
server exists, so they can be run and checked from the terminal.
"""

from functools import lru_cache

import pandas as pd

import data
from diversity import mmr, skill_similarity_matrix
from recommend import similar_by_cooccurrence
from taxonomy import base_role, label

# A zero in the 2026 index means "not measured", not "filled the same day".
# Displaying it as a number would invent a fact, so it is treated as missing.
MISSING_MARKER = 0


def _absent(value):
    """None where a figure is missing or is a zero standing in for missing."""
    if value is None or pd.isna(value) or value == MISSING_MARKER:
        return None
    return float(value)


# --------------------------------------------------------------------- roles
def role_list(family=None, sort="postings", limit=50):
    """Roles, optionally within one job family. Returns (rows, total_matched)."""
    rows = data.roles
    if family:
        rows = rows[rows.job_family == family]
    total = len(rows)

    if sort == "pay":
        # blank pay sorts last, because "unknown" is not "low"
        rows = rows.sort_values("median_salary", ascending=False,
                                na_position="last")
    elif sort == "employers":
        rows = rows.sort_values("companies", ascending=False)
    else:
        rows = rows.sort_values("postings", ascending=False)

    return rows.head(limit), total


def role_detail(role):
    """One role, its skills, and its sibling roles. None if the role is unknown."""
    rows = data.roles[data.roles.role == role]
    if rows.empty:
        return None
    row = rows.iloc[0]

    skills = (data.role_skills[data.role_skills.role == role]
              .nlargest(10, "share_pct"))
    siblings = (data.roles[(data.roles.job_family == row.job_family)
                           & (data.roles.role != role)]
                .nlargest(6, "postings"))
    # No "family_label" key here. Templates get label() as a global, and a context
    # key of the same name shadows it with a string, which then fails to be called.
    return {"role": row, "skills": skills, "siblings": siblings}


# -------------------------------------------------------------------- skills
def skill_list(query=None, category=None, limit=80):
    """Skills matching a typed fragment, with how many sources measure each."""
    names = skills_in_category(category)
    if query:
        q = query.lower()
        names = [n for n in names if q in data.skill_labels[n].lower()]

    in_index = data.scarcity.groupby("skill_name").size()
    in_posts = data.demand.groupby("skill_name").size()
    rows = [{"skill_name": n,
             "label": data.skill_labels[n],
             "categories": int(in_index.get(n, 0)),
             "families": int(in_posts.get(n, 0)),
             "postings": int(data.totals.get(n, 0))}
            for n in names]
    # columns are declared, so a search that matches nothing still returns a frame
    # with a "postings" column to sort on rather than an empty one that raises
    out = pd.DataFrame(rows, columns=["skill_name", "label", "categories",
                                      "families", "postings"])
    out = out.sort_values("postings", ascending=False)
    return out.head(limit), len(out)


def skill_detail(skill):
    """One skill across both sources, kept side by side and never added up."""
    if skill not in data.vocab:
        return None

    index_rows = data.scarcity[data.scarcity.skill_name == skill].copy()
    if not index_rows.empty:
        index_rows["median_days_open"] = index_rows.median_days_open.map(_absent)

    post_rows = data.demand[data.demand.skill_name == skill].copy()
    if not post_rows.empty:
        post_rows["family_label"] = post_rows.job_family.map(label)

    pay_rows = data.pay[data.pay.skill_name == skill].copy()
    if not pay_rows.empty:
        pay_rows["family_label"] = pay_rows.job_family.map(label)

    return {
        "skill": skill,
        "description": data.descriptions.get(skill),
        "index_rows": index_rows.sort_values("scarcity_score", ascending=False),
        "post_rows": post_rows.sort_values("demand_pct", ascending=False),
        "pay_rows": pay_rows.sort_values("salary_premium_pct", ascending=False),
    }


def skill_neighbours(skill, variety=0.7, n=8, pool=40):
    """Skills that share job ads with this one, split into complements and
    substitutes.

    Two signals. 'association' is how often the pair is asked for together,
    divided by how common each is, so it means "unusually often" and not "common".
    'meaning' is how alike the two written descriptions are. Sharing ads while
    describing the same kind of thing means substitutes. Sharing ads while
    describing different things means complements.

    Diversity re-ranking is applied per group, because ranking on association
    alone returns eight flavours of the same neighbour.
    """
    near = similar_by_cooccurrence(data.cooc, data.totals, skill, top_n=pool)
    if near.empty or near.skill_name.isna().all():
        return pd.DataFrame(), pd.DataFrame()

    near = near.copy()
    near["relation"] = [data.relations.get((skill, o), ("unlabelled", None))[0]
                        for o in near.skill_name]
    near["meaning"] = [data.relations.get((skill, o), (None, None))[1]
                       for o in near.skill_name]

    def shortlist(frame, take):
        names = list(frame.skill_name)
        if variety >= 1.0 or len(names) < 2:
            return frame.head(take)
        m = skill_similarity_matrix(names, data.cooc, data.totals)
        keep = mmr(frame.association.values, m, balance=variety, top_n=take)
        return frame.iloc[keep]

    comps = near[near.relation == "complements"]
    subs = near[near.relation == "substitutes"]
    return (shortlist(comps, n) if not comps.empty else comps,
            shortlist(subs, 6) if not subs.empty else subs)


# ---------------------------------------------------------------------- jobs
def job_list(family=None, worksite=None, seniority=None, limit=50):
    """Postings matching the filters. Returns (rows, total, share_that_stated_site).

    No relevance order, because ranking by meaning needs job_vectors.npy. The
    order here is the file's own order and means nothing, which the page says.
    """
    rows = data.jobs
    if family:
        rows = rows[rows.job_family == family]
    if worksite:
        rows = rows[rows.worksite == worksite]
    if seniority:
        rows = rows[rows.seniority == seniority]

    total = len(rows)
    stated = float(rows.worksite_stated.fillna(False).mean()) if total else 0.0
    return rows.head(limit), total, stated


# There is no "skills these jobs ask for" panel on the jobs page. The Streamlit
# version scanned job descriptions for it, and jobs_enriched.csv has no
# description column. Scanning the titles instead was tried and finds almost
# nothing, because a title names a role and a description names the tools. The
# panel returns when tech_jobs.csv is wired in, not before.


# ---------------------------------------------------------------- candidates
def candidate_list(source=None, category=None, min_skills=0, limit=50):
    """Candidates matching the filters. Returns (rows, total).

    Sorted by how many known skills were found, which is a proxy and a weak one.
    Ranking against a stated need requires embedding the resumes, which is a
    later step. Until then this is a browse, not a match, and the page says so.
    """
    rows = data.candidates
    if source:
        rows = rows[rows.source == source]
    if category:
        rows = rows[rows.category == category]
    if min_skills:
        rows = rows[rows.n_skills >= min_skills]

    total = len(rows)
    rows = rows.sort_values("n_skills", ascending=False).head(limit)
    return rows, total


def candidate_detail(candidate_id):
    rows = data.candidates[data.candidates.candidate_id == candidate_id]
    if rows.empty:
        return None
    row = rows.iloc[0]
    skills = [s for s in str(row.skills).split(", ") if s and s != "nan"]
    return {"candidate": row, "skills": skills}


def candidate_sources():
    """Counts per source, so a page can show provenance without hardcoding it."""
    g = data.candidates.groupby("source").agg(
        candidates=("candidate_id", "size"),
        mean_skills=("n_skills", "mean"))
    g["mean_skills"] = g.mean_skills.round(1)
    return g.reset_index()


# ---------------------------------------------------------------- front page
def overview():
    """The counts the home page quotes, read rather than written down."""
    paid = data.roles.median_salary.notna()
    return {
        "postings": len(data.jobs),
        "roles": len(data.roles),
        "families": len(data.families),
        "skills": len(data.vocab),
        "candidates": len(data.candidates),
        "roles_with_pay": int(paid.sum()),
        "roles_pay_suppressed": int(data.roles.thin_pay.sum()),
        "salary_coverage": round(100 * data.jobs.salary.notna().mean(), 1),
        "worksite_coverage": round(
            100 * data.jobs.worksite_stated.fillna(False).mean(), 1),
        "substitute_pairs": sum(1 for v in data.relations.values()
                                if v[0] == "substitutes") // 2,
    }


if __name__ == "__main__":
    print(data.summary())
    print("\noverview:", overview())

    rows, total = role_list(family="engineering", sort="pay", limit=3)
    print(f"\nengineering roles by pay, {total} total:")
    print(rows[["role_label", "postings", "companies", "median_salary"]]
          .to_string(index=False))

    d = role_detail("software engineer")
    print(f"\nsoftware engineer: {d['role'].postings} postings, "
          f"{len(d['skills'])} skills, {len(d['siblings'])} siblings")

    for s in ["Kubernetes", "Tableau", "HTML"]:
        comps, subs = skill_neighbours(s)
        print(f"\n{s}: {len(comps)} complements, {len(subs)} substitutes")
        if not comps.empty:
            print("  learn next:", list(comps.skill_name))
        if not subs.empty:
            print("  skippable :", list(subs.skill_name))

    rows, total, stated = job_list(family="devops", worksite="remote", limit=5)
    print(f"\nremote devops postings: {total}, {100 * stated:.0f}% stated a worksite")
    print(rows[["job_title", "company", "salary_label", "seniority"]]
          .to_string(index=False))

    rows, total = candidate_list(min_skills=5, limit=3)
    print(f"\ncandidates with 5+ skills: {total}")
    print(rows[["candidate_id", "source", "category", "n_skills"]]
          .to_string(index=False))


# ============================================================== dashboard
# Pay-range-in-posting mandates in force when this data was collected, January
# 2024. Illinois, Minnesota and New Jersey passed comparable laws that took
# effect in 2025, so they are deliberately NOT here: including them would test
# the hypothesis against the wrong calendar.
MANDATE_STATES = {"CO", "CA", "NY", "WA", "HI"}
MIN_STATE_POSTINGS = 100


def _states():
    """US state per posting, from a 'City, ST' tail only.

    Anything else is left blank rather than guessed. About 11,000 postings carry
    a region, a metro area or a non-US location, and inventing a state for those
    would put fabricated rows into the root cause analysis below.
    """
    return data.jobs.job_location.fillna("").str.extract(r",\s*([A-Z]{2})\s*$")[0]


@lru_cache(maxsize=1)
def kpis():
    """The headline figures. Each one carries its own time anchor and says what
    it gates, because a coverage percentage on its own is not actionable."""
    j = data.jobs
    adverts = j.groupby(["job_title", "company"]).ngroups
    return [
        {"label": "Postings analysed", "value": f"{len(j):,}",
         "basis": "January 2024", "gates": "filtered from 1.3M raw rows"},
        {"label": "Distinct roles", "value": f"{len(data.roles)}",
         "basis": "10 or more postings each",
         "gates": "seniority stripped, so a role appears once"},
        {"label": "Unique adverts", "value": f"{adverts:,}",
         "basis": f"{100 * adverts / len(j):.0f}% of postings",
         "gates": f"{len(j) - adverts:,} are reposts of a job already counted"},
        {"label": "Pay disclosed", "value": f"{100 * j.salary.notna().mean():.1f}%",
         "basis": f"{int(j.salary.notna().sum()):,} postings",
         "gates": f"blanks the median for {int(data.roles.thin_pay.sum())} of "
                  f"{len(data.roles)} roles"},
        {"label": "Level stated", "value": f"{100 * (j.seniority != 'unspecified').mean():.1f}%",
         "basis": f"{int((j.seniority == 'unspecified').sum()):,} unlabelled",
         "gates": "read from the title, never from the description"},
        {"label": "Worksite stated", "value": f"{100 * j.worksite_stated.fillna(False).mean():.1f}%",
         "basis": "the rest default to onsite",
         "gates": "so the onsite count is an upper bound"},
    ]


@lru_cache(maxsize=1)
def market():
    """Descriptive: what the market looks like, per job family."""
    j = data.jobs
    paid = j[j.salary.notna()]
    rows = []
    for fam, g in j.groupby("job_family"):
        gp = paid[paid.job_family == fam]
        told = g[g.worksite_stated.fillna(False)]
        rows.append({
            "family": fam, "label": label(fam), "postings": len(g),
            "companies": g.company.nunique(),
            "median_pay": float(gp.salary.median()) if len(gp) else None,
            "paid_n": len(gp),
            # remote share is computed over postings that SAID something, because
            # the default-to-onsite rule would otherwise invent onsite postings
            "remote_pct": (100 * (told.worksite == "remote").mean()
                           if len(told) else None),
            "told_n": len(told),
            "unspecified_pct": 100 * (g.seniority == "unspecified").mean(),
        })
    return sorted(rows, key=lambda r: -r["postings"])


@lru_cache(maxsize=1)
def pay_disclosure_by_state():
    """Diagnostic: why is pay missing from three quarters of postings?

    Tests one explanation against the data rather than asserting it. If pay
    transparency law drives disclosure, states with a posting mandate in force in
    January 2024 should disclose far more often than states without one.
    """
    j = data.jobs.assign(state=_states())
    us = j[j.state.notna()]
    g = us.groupby("state").agg(postings=("salary", "size"),
                               disclosed=("salary", lambda s: int(s.notna().sum())))
    g = g[g.postings >= MIN_STATE_POSTINGS].copy()
    g["pct"] = (100 * g.disclosed / g.postings).round(1)
    g["mandate"] = g.index.isin(MANDATE_STATES)

    a, b = g[g.mandate], g[~g.mandate]
    top = g.nlargest(10, "pct").reset_index()
    return {
        "parsed": len(us), "unparsed": len(j) - len(us),
        "states": len(g),
        "mandate_pct": round(100 * a.disclosed.sum() / a.postings.sum(), 1),
        "other_pct": round(100 * b.disclosed.sum() / b.postings.sum(), 1),
        "mandate_n": int(a.postings.sum()), "other_n": int(b.postings.sum()),
        "ratio": round((a.disclosed.sum() / a.postings.sum())
                       / (b.disclosed.sum() / b.postings.sum()), 2),
        "mandate_states": sorted(a.index),
        "top": top.to_dict("records"),
        "in_top10": int(top.mandate.sum()),
    }


@lru_cache(maxsize=1)
def repost_inflation():
    """Diagnostic: 30% of postings are the same job posted again.

    The largest offender is also the source of the retail contamination in the
    role table, so one cause produced two separate data problems.
    """
    j = data.jobs
    counts = j.groupby(["job_title", "company"]).size().sort_values(ascending=False)
    worst = [{"title": t, "company": c, "times": int(n)}
             for (t, c), n in counts.head(5).items()]
    return {"adverts": len(counts), "postings": len(j),
            "repeats": len(j) - len(counts),
            "repeat_pct": round(100 * (len(j) - len(counts)) / len(j), 1),
            "repeated_pairs": int((counts > 1).sum()),
            "worst": worst}


@lru_cache(maxsize=1)
def missing_level():
    """Diagnostic: the level label is missing at scale, and it is not random.

    detect_seniority reads the title only, on purpose, because descriptions are
    full of "lead a team" and "reports to the manager". The cost is that a title
    saying nothing leaves the posting unlabelled, and that is 35% of the market.
    """
    j = data.jobs
    paid = j[j.salary.notna()]
    rows = []
    for fam, g in j.groupby("job_family"):
        gp = paid[paid.job_family == fam]
        u = gp[gp.seniority == "unspecified"].salary
        s = gp[gp.seniority == "senior"].salary
        rows.append({
            "family": fam, "label": label(fam),
            "unspecified_pct": round(100 * (g.seniority == "unspecified").mean(), 1),
            "unspecified_pay": float(u.median()) if len(u) else None,
            "senior_pay": float(s.median()) if len(s) else None,
            "u_n": len(u), "s_n": len(s),
            "exceeds": bool(len(u) and len(s) and u.median() > s.median()),
        })
    rows.sort(key=lambda r: -r["unspecified_pct"])
    return {"rows": rows,
            "total": int((j.seniority == "unspecified").sum()),
            "exceeding": [r["label"] for r in rows if r["exceeds"]]}


@lru_cache(maxsize=1)
def data_quality():
    """Every field a page relies on, with what its gaps actually mean.

    A completeness percentage is only half the assessment. The other half is
    whether a blank means "unknown" or "zero", because the two are treated the
    same by almost every chart and that is where wrong conclusions come from.
    """
    j, r, c = data.jobs, data.roles, data.candidates
    return [
        {"field": "salary", "where": "postings", "complete": round(100 * j.salary.notna().mean(), 1),
         "means": "the posting did not disclose pay",
         "blocks": "medians for 296 of 437 roles"},
        {"field": "seniority", "where": "postings",
         "complete": round(100 * (j.seniority != "unspecified").mean(), 1),
         "means": "the title carried no level word",
         "blocks": "any pay ladder by level"},
        {"field": "worksite", "where": "postings",
         "complete": round(100 * j.worksite_stated.fillna(False).mean(), 1),
         "means": "nothing was said; the row defaults to onsite",
         "blocks": "remote share is only valid among those that stated it"},
        {"field": "median_salary", "where": "roles",
         "complete": round(100 * r.median_salary.notna().mean(), 1),
         "means": "fewer than 5 employers stated pay",
         "blocks": "sorting roles by pay covers 141 of 437"},
        {"field": "median_days_open", "where": "2026 index",
         "complete": round(100 * (data.scarcity.median_days_open > 0).mean(), 1),
         "means": "a zero marks missing data, not a same-day fill",
         "blocks": "zeros are shown as absent, never as fast hiring"},
        {"field": "skills", "where": "candidates",
         "complete": round(100 * (c.n_skills > 0).mean(), 1),
         "means": "the resume named no tool from the 176-skill list",
         "blocks": "skill-overlap ranking, which is why matching needs embeddings"},
    ]


@lru_cache(maxsize=1)
def substitute_balance():
    """The complement and substitute split, stated with its own weakness.

    29 substitutes in 7,705 pairs means "always complements" would score 99.6%,
    so the headline accuracy of this classifier is not the interesting number.
    """
    subs = sum(1 for v in data.relations.values() if v[0] == "substitutes") // 2
    total = len(data.relations) // 2
    return {"substitutes": subs, "total": total,
            "pct": round(100 * subs / total, 2),
            "majority_baseline": round(100 * (total - subs) / total, 1)}


# ------------------------------------------------------------ certifications
# Ordered entry first, because someone reading a role page for the first time
# needs the credential they can actually sit, not the expert one.
LEVEL_ORDER = {"entry": 0, "associate": 1, "professional": 2, "expert": 3}


def certifications_for(family, include_retired=False):
    """Certifications for one job family, easiest first.

    Retired ones are hidden by default but kept in the file, because a role page
    should not present a dead credential as a plan while the report may still
    need to explain what replaced it.
    """
    rows = data.certs[data.certs.job_family == family].copy()
    if rows.empty:
        return []
    rows["retired"] = ~rows.status.str.startswith("current")
    if not include_retired:
        rows = rows[~rows.retired]
    rows["order"] = rows.level.map(LEVEL_ORDER).fillna(9)
    return rows.sort_values(["order", "name"]).to_dict("records")


def certification_note(family):
    """What was hidden, so the omission is visible rather than silent."""
    rows = data.certs[data.certs.job_family == family]
    gone = rows[~rows.status.str.startswith("current")]
    return [{"name": r["name"], "status": r["status"]} for _, r in gone.iterrows()]


# ========================================================== context search
# TF-IDF, not embeddings. See context.py for why, and for what it costs.
CONTEXT_HELP = ("Matches the words you type against role descriptions and the "
                "skills their postings ask for. It matches words, not meaning, so "
                "name the tools you know rather than describing them.")


def roles_by_context(query, family=None, top_n=25):
    """Roles closest to a typed description. Returns (rows, scored, total_pool).

    The family filter is applied to the mask BEFORE ranking, so asking for the top
    25 inside one family gives 25 results from that family rather than whatever
    survives a global top 25.
    """
    mask = None
    if family:
        mask = (data.roles.job_family == family).to_numpy()
    pool = int(mask.sum()) if mask is not None else len(data.roles)

    if not (query or "").strip():
        rows = data.roles[mask] if mask is not None else data.roles
        return rows.nlargest(top_n, "postings"), False, pool

    hits = data.role_index.search(query, top_n=top_n, subset=mask)
    if not hits:
        return data.roles.iloc[:0], True, pool
    idx = [i for i, _ in hits]
    out = data.roles.iloc[idx].copy()
    out["relevance"] = [round(s, 3) for _, s in hits]
    return out, True, pool


def jobs_by_context(query, family=None, worksite=None, seniority=None,
                    dedupe=True, top_n=50):
    """Postings, optionally ranked by context. Returns (rows, total, stated, scored).

    jobs_enriched.csv has no description column, so a posting cannot be scored
    directly. Instead the ROLE is scored, and postings inherit their role's score.
    That is not a workaround: a query describing work should return every posting
    for the matching kind of job, not only the ones whose title happened to use
    your words.
    """
    rows = data.jobs
    if family:
        rows = rows[rows.job_family == family]
    if worksite:
        rows = rows[rows.worksite == worksite]
    if seniority:
        rows = rows[rows.seniority == seniority]

    if dedupe:
        # 30% of postings repeat a job already listed. One advert per
        # title-and-company pair, so the same job does not fill the page.
        rows = rows.drop_duplicates(subset=["job_title", "company"])

    total = len(rows)
    stated = float(rows.worksite_stated.fillna(False).mean()) if total else 0.0

    scored = bool((query or "").strip())
    if not scored:
        return rows.head(top_n), total, stated, False

    hits = data.role_index.search(query, top_n=60)
    if not hits:
        return rows.iloc[:0], total, stated, True
    score = {data.roles.role.iat[i]: s for i, s in hits}

    rows = rows.assign(role=rows.job_title.map(base_role))
    rows = rows[rows.role.isin(score)].copy()
    rows["relevance"] = rows.role.map(score).round(3)
    return (rows.sort_values("relevance", ascending=False).head(top_n),
            len(rows), stated, True)


def candidates_by_context(query=None, role=None, include_synthetic=False,
                          top_n=10):
    """Rank the tech candidate pool. Returns (rows, total_pool, scored).

    Synthetic profiles are excluded by default. They average 7 named skills to a
    real resume's 3 because a model wrote them as a skill list, so on any text
    ranking they take every top slot. Including them is a deliberate choice a
    recruiter makes, not the default.

    A role name is turned into a query by pulling that role's own skills out of
    role_skills, so "search by job role" and "search by context" are one code
    path rather than two that can disagree.
    """
    pool = data.tech_candidates
    mask = None
    if not include_synthetic:
        mask = (pool.source == "resume_dataset").to_numpy()

    terms = (query or "").strip()
    if role:
        skills = data.role_skills[data.role_skills.role == role]
        role_words = " ".join(skills.nlargest(10, "share_pct").skill_name)
        terms = f"{role} {role_words} {terms}".strip()

    available = int(mask.sum()) if mask is not None else len(pool)
    if not terms:
        rows = pool[mask] if mask is not None else pool
        return rows.nlargest(top_n, "n_skills"), available, False

    hits = data.candidate_index.search(terms, top_n=top_n, subset=mask)
    if not hits:
        return pool.iloc[:0], available, True
    out = pool.iloc[[i for i, _ in hits]].copy()
    out["relevance"] = [round(s, 3) for _, s in hits]
    return out, available, True


def candidate_summary(row):
    """A one-line description built from extracted fields, not generated.

    Only the parts that were actually found are mentioned. A resume with no stated
    degree says nothing about education rather than saying "unknown", because a
    sentence full of unknowns reads as a broken record instead of a thin one.
    """
    bits = []
    if str(row.get("inferred_role", "")):
        bits.append(str(row["inferred_role"]))
    if row.get("years_experience") not in ("", None) and pd.notna(row.get("years_experience")):
        bits.append(f"{int(float(row['years_experience']))} years stated")
    if str(row.get("degree", "")):
        deg = str(row["degree"])
        if str(row.get("major", "")):
            deg += f" in {row['major']}"
        bits.append(deg)
    if str(row.get("gpa", "")):
        bits.append(f"GPA {row['gpa']}")
    n = int(row.get("n_skills") or 0)
    bits.append(f"{n} recognised {'skill' if n == 1 else 'skills'}")
    return " · ".join(bits) if bits else "nothing extractable from this resume"


def candidate_bio(row):
    """Up to two plain sentences: education, then experience.

    Same rule as candidate_summary: only parts the resume actually stated are
    mentioned. Returns "" when nothing is extractable, so a card can skip the
    line rather than show two empty sentences.
    """
    degree = str(row.get("degree", "") or "")
    major = str(row.get("major", "") or "")
    college = str(row.get("college", "") or "")
    role = str(row.get("inferred_role", "") or "")
    years = row.get("years_experience")

    sentences = []
    if degree or major or college:
        if degree:
            edu = f"Holds a {degree}"
            if major:
                edu += f" in {major}"
        elif major:
            edu = f"Studied {major}"
        else:
            edu = "Attended"
        if college:
            edu += f" from {college}" if (degree or major) else f" {college}"
        sentences.append(edu + ".")

    def article(word):
        return "an" if word[:1] in "AEIOU" else "a"

    has_years = years not in ("", None) and pd.notna(years)
    if has_years or role:
        if has_years:
            y = int(float(years))
            bit = f"Has {y} year{'s' if y != 1 else ''} of stated experience"
            if role:
                bit += f" as {article(role)} {role}"
        else:
            bit = f"Currently working as {article(role)} {role}"
        sentences.append(bit + ".")

    return " ".join(sentences)


# ------------------------------------------------------ study guide, no LLM
# Built from this project's own data, deterministically. llm.py is still in the
# tree for later use, but nothing here calls it: a study plan assembled from
# measured skill shares is checkable, and a 3B model's ordering is not.
FOUNDATION = {"SQL", "Excel", "HTML", "CSS", "Git", "Linux", "Python",
              "JavaScript", "Bash", "Agile / Scrum", "REST API", "JSON"}


def study_plan(role):
    """Order a role's own skills into learning steps by how common they are.

    The ordering rule is the data, not an opinion: a skill asked for by 70% of a
    role's postings is needed before one asked for by 12%. Foundations are pulled
    forward only when they are already in the role's own skill list, so nothing is
    recommended that the postings did not ask for.
    """
    rows = data.role_skills[data.role_skills.role == role].nlargest(15, "share_pct")
    if rows.empty:
        return []

    skills = list(rows.itertuples())
    base = [s for s in skills if s.skill_name in FOUNDATION]
    rest = [s for s in skills if s.skill_name not in FOUNDATION]

    steps = []
    if base:
        steps.append({"title": "Foundations", "skills": base,
                      "why": "General-purpose tools that everything else sits on, "
                             "and every one of them is already asked for by this "
                             "role's postings."})
    core = rest[:4]
    if core:
        steps.append({"title": "What this role is built on", "skills": core,
                      "why": f"The most-asked-for skills specific to this role, "
                             f"led by {core[0].skill_name} at "
                             f"{core[0].share_pct}% of its postings."})
    mid = rest[4:8]
    if mid:
        steps.append({"title": "Next, to be competitive", "skills": mid,
                      "why": "Asked for often enough to appear in a large minority "
                             "of postings, so these separate candidates rather "
                             "than qualifying them."})
    tail = rest[8:12]
    if tail:
        steps.append({"title": "Specialising", "skills": tail,
                      "why": "A smaller share of postings ask for these, so treat "
                             "them as a direction to pick rather than a checklist."})
    return steps


# ---------------------------------------------------------- skills browsing
def skills_in_category(category=None):
    """Skill names, optionally only those the 2026 index measures in one category."""
    if not category:
        return data.vocab
    names = set(data.scarcity[data.scarcity.category == category].skill_name)
    return [s for s in data.vocab if s in names]


def related_to(skill, top_n=5):
    """The five skills most associated with this one, labelled and explained.

    Five, not eight, because the dropdown exists to answer "what goes with this"
    and a longer list stops being an answer.
    """
    comps, subs = skill_neighbours(skill, n=top_n)
    out = []
    for frame, relation in ((comps, "complements"), (subs, "substitutes")):
        for r in frame.itertuples():
            out.append({"skill_name": r.skill_name, "association": r.association,
                        "meaning": r.meaning, "relation": relation})
    out.sort(key=lambda r: -r["association"])
    return out[:top_n]


def role_options():
    """Roles a recruiter can pick from, largest first, for the candidate search."""
    return [{"role": r.role, "label": r.role_label, "postings": r.postings}
            for r in data.roles.nlargest(120, "postings").itertuples()]


# ================================================== consumer front page
@lru_cache(maxsize=1)
def headline():
    """The few numbers a person actually wants on arrival.

    Deliberately not the coverage and quality figures: those live on /analysis.
    Someone deciding what to learn needs to know the market is big and current,
    not how many postings failed to state a worksite.
    """
    j = data.jobs
    return {
        "postings": len(j),
        "employers": int(j.company.nunique()),
        "roles": len(data.roles),
        "skills": len(data.vocab),
        "families": len(data.families),
    }


@lru_cache(maxsize=1)
def top_roles(n=8):
    """Roles with the most openings, for someone browsing rather than searching."""
    return [{"role": r.role, "label": r.role_label, "family": label(r.job_family),
             "postings": int(r.postings), "companies": int(r.companies),
             "pay": None if pd.isna(r.median_salary) else float(r.median_salary),
             "skills": [s for s in str(r.top_skills).split(", ") if s][:4]}
            for r in data.roles.nlargest(n, "postings").itertuples()]


@lru_cache(maxsize=1)
def best_paid_roles(n=6):
    """Only roles whose pay survived the employer floor, so every row has a figure."""
    rows = data.roles[data.roles.median_salary.notna()].nlargest(n, "median_salary")
    return [{"role": r.role, "label": r.role_label, "family": label(r.job_family),
             "pay": float(r.median_salary), "postings": int(r.postings),
             "employers": int(r.salary_companies)} for r in rows.itertuples()]


@lru_cache(maxsize=1)
def top_skills(n=10):
    """The skills the most postings ask for, across every job family."""
    t = data.demand.groupby("skill_name").demand_count.sum().nlargest(n)
    fams = data.demand.groupby("skill_name").job_family.nunique()
    return [{"skill": s, "postings": int(c), "families": int(fams.get(s, 0))}
            for s, c in t.items()]


@lru_cache(maxsize=1)
def remote_friendly(n=5):
    """Families where the most postings that stated a worksite said remote."""
    rows = []
    for fam, g in data.jobs[data.jobs.worksite_stated.fillna(False)].groupby("job_family"):
        if len(g) < 100:
            continue
        rows.append({"family": label(fam),
                     "pct": round(100 * (g.worksite != "onsite").mean(), 0),
                     "n": len(g)})
    return sorted(rows, key=lambda r: -r["pct"])[:n]


@lru_cache(maxsize=1)
def level_mix():
    """Experience level split per category, for the front page chart.

    'unspecified' is folded into "not stated" here rather than shown as a level,
    because to a person reading a chart an unlabelled bar segment looks like a
    kind of job rather than a gap in the advert.
    """
    out = []
    for fam, g in data.jobs.groupby("job_family"):
        counts = g.seniority.value_counts()
        out.append({
            "category": label(fam),
            "junior": int(counts.get("junior", 0) + counts.get("mid", 0)),
            "senior": int(counts.get("senior", 0)),
            "lead": int(counts.get("lead", 0) + counts.get("principal", 0)),
            "unstated": int(counts.get("unspecified", 0)),
        })
    return sorted(out, key=lambda r: -(r["junior"] + r["senior"] + r["lead"]))
