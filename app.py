"""Streamlit interface. Collects input, calls the models, draws results.

Deliberately contains no logic: everything it needs lives in the modules
alongside it, so the whole system is testable without launching a browser.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from diversity import mmr, skill_similarity_matrix
from matcher import (ALIASES, EXTRA_SKILLS, build_prose_patterns,
                     extract_from_prose)
from learn import (books_search_link, search_books, search_videos,
                   youtube_search_link)
from prep import load_and_aggregate
from recommend import (neighbours_for_known, rank_skills,
                       similar_by_cooccurrence)
from search import get_model, load_index, search_jobs
from taxonomy import base_role, classify, label

HERE = Path(__file__).parent
SCARCITY_CSV = HERE / "skill-scarcity-index.csv"
LK_DEMAND = HERE / "linkedin_demand.csv"
LK_COOC = HERE / "linkedin_cooccurrence.csv"
LK_SALARY = HERE / "linkedin_salary.csv"
SKILL_PAIRS = HERE / "skill_pairs.csv"
SKILL_DESC = HERE / "skill_descriptions.csv"
JOBS_CSV = HERE / "tech_jobs.csv"
JOBS_ENRICHED = HERE / "jobs_enriched.csv"
VECTORS_NPY = HERE / "job_vectors.npy"
ROLES_CSV = HERE / "roles.csv"
ROLE_SKILLS_CSV = HERE / "role_skills.csv"
ROLE_VECTORS = HERE / "role_vectors.npy"

# a median pay built on fewer employers than this is not a measurement
MIN_PAY_EMPLOYERS = 5

INDEX_2026 = "Scarcity index only (Jul 2026)"
POSTINGS = "Job postings only (Jan 2024)"
BOTH = "Both sources"

st.set_page_config(page_title="Skill and Job Recommender", layout="wide")


# ------------------------------------------------------------------ loading
@st.cache_data
def get_tables():
    scarcity = load_and_aggregate(SCARCITY_CSV)
    demand = pd.read_csv(LK_DEMAND)
    cooc = pd.read_csv(LK_COOC)
    pay = pd.read_csv(LK_SALARY) if LK_SALARY.exists() else pd.DataFrame()
    totals = demand.groupby("skill_name").demand_count.sum()
    vocab = sorted(set(scarcity.skill_name) | set(demand.skill_name) | set(EXTRA_SKILLS))

    # complement vs substitute labels, keyed both ways so lookup is direction free
    relations = {}
    if SKILL_PAIRS.exists():
        pairs = pd.read_csv(SKILL_PAIRS)
        for a, b, rel, mean in zip(pairs.skill_a, pairs.skill_b,
                                   pairs.relation, pairs.meaning):
            relations[(a, b)] = relations[(b, a)] = (rel, mean)

    descriptions = {}
    if SKILL_DESC.exists():
        d = pd.read_csv(SKILL_DESC)
        descriptions = dict(zip(d.skill_name, d.description))

    return scarcity, demand, cooc, pay, totals, vocab, relations, descriptions


@st.cache_data
def get_roles():
    """Distinct job roles and the skills they ask for, from build_roles.py.

    Roles whose example title no longer passes the current taxonomy are dropped.
    roles.csv was built before the bare "front end" fix, so it still holds
    retail supervisors filed under engineering. Re-checking here means this tab
    follows taxonomy.py rather than a stale file, and the filter quietly stops
    removing anything once the data is rebuilt.
    """
    if not (ROLES_CSV.exists() and ROLE_SKILLS_CSV.exists()):
        return pd.DataFrame(), pd.DataFrame(), None
    roles = pd.read_csv(ROLES_CSV)
    skills = pd.read_csv(ROLE_SKILLS_CSV)

    # a role with no skills row would show an empty section 3. There are 33 and
    # they are small and mostly misfiled, so they are not worth displaying.
    #
    # The base_role test catches labels the CURRENT taxonomy would clean but
    # roles.csv still carries, because the file was built before the fix:
    # "Business Analyst # 20", "/ Backend Engineer". That is 8 roles and 274 of
    # 37,453 postings. When roles.csv is eventually rebuilt those postings fold
    # back into their real roles and this test stops removing anything.
    keep = (classify(roles.example_title).notna()
            & roles.role.isin(set(skills.role))
            & roles.role.map(lambda r: base_role(r) == r))

    # role_vectors.npy is written in roles.csv row order, so the SAME mask has
    # to be applied to both or every search result points at the wrong role.
    # This is the alignment trap from jobs_enriched.csv in a new place.
    vectors = None
    if ROLE_VECTORS.exists():
        v = np.load(ROLE_VECTORS)
        if len(v) == len(roles):
            vectors = v[keep.to_numpy()]
    return roles[keep].reset_index(drop=True), skills, vectors


# Streamlit reruns this whole file on every click, so an uncached call here
# would spend YouTube quota every time a slider moves. ttl rather than forever,
# so results refresh eventually without a restart.
@st.cache_data(ttl=3600, show_spinner=False)
def cached_videos(query, api_key, n=3):
    return search_videos(query, api_key, n)


@st.cache_data(ttl=3600, show_spinner=False)
def cached_books(query, api_key, n=3):
    return search_books(query, api_key, n)


def show_books(books, error):
    """Cover, title, authors, year and blurb for each book."""
    if error:
        st.caption(f"No books loaded: {error}")
    for b in books:
        c1, c2 = st.columns([1, 5])
        if b["thumbnail"]:
            c1.image(b["thumbnail"])
        else:
            c1.caption("no cover")
        c2.markdown(f"**{b['title']}**")
        c2.caption(f"{b['authors']}  ·  {b['year'] or 'year unknown'}")
        if b["blurb"]:
            c2.write(b["blurb"][:400] + ("..." if len(b["blurb"]) > 400 else ""))
        if b["url"]:
            c2.link_button("View on Google Books", b["url"])


def skill_material_buttons(names, api_key):
    """A button per skill, then videos AND a book for whichever was clicked.

    Called from both branches so the buttons sit under the list they belong to.
    Fetching every skill on load would be one search each at 100 quota units,
    about 16 page views a day, so quota is spent only on a click.
    """
    st.caption("Click one to load videos and a book for that skill.")
    for col, name in zip(st.columns(len(names)), names):
        if col.button(name, key=f"lbtn_{name}"):
            st.session_state.lextra = name

    extra = st.session_state.get("lextra")
    if extra not in names:
        return
    st.markdown(f"**Material for {extra}**")
    vids, err = cached_videos(f"{extra} tutorial", api_key)
    if err:
        st.caption(err)
        st.link_button(f"Search YouTube for {extra}",
                       youtube_search_link(extra + " tutorial"))
    if vids:
        show_videos(vids)
    books, berr = cached_books(extra, api_key, 1)
    show_books(books, berr)


def show_videos(vids):
    """Draw videos as embedded players side by side.

    One function, two call sites, so the skill videos and the role videos
    cannot end up looking different from each other again.
    """
    for col, v in zip(st.columns(len(vids)), vids):
        col.video(v["url"])
        col.caption(f"{v['title']}  ·  {v['channel']}")


@st.cache_resource
def get_index():
    """Vectors and job metadata. cache_resource, not cache_data, because a
    loaded model is not something Streamlit can serialise."""
    if not (JOBS_CSV.exists() and VECTORS_NPY.exists()):
        return None, None
    jobs, vectors = load_index(JOBS_CSV, VECTORS_NPY)

    if JOBS_ENRICHED.exists():
        extra = pd.read_csv(JOBS_ENRICHED, usecols=[
            "job_link", "salary", "salary_label", "seniority", "worksite",
            "worksite_stated"])
        # drop_duplicates matters: a left merge on a duplicated key ADDS rows,
        # which would break alignment with job_vectors.npy and make every
        # search result wrong
        jobs = jobs.merge(extra.drop_duplicates("job_link"), on="job_link",
                          how="left")
    return jobs, vectors


@st.cache_data
def skill_options(names):
    """One entry per skill, with its aliases in the label.

    Aliases used to be separate entries, which made the list look full of
    duplicates that all led to the same data. Folding them into the label keeps
    the list one-per-skill while still letting someone type k8s and find
    Kubernetes, because the selectbox filters on the whole label.
    """
    aliases = {}
    for alias, target in ALIASES.items():
        if target in names and alias.lower() != target.lower():
            aliases.setdefault(target, []).append(alias)

    opts = {}
    for n in sorted(names):
        extra = aliases.get(n, [])[:3]
        opts[f"{n}  ({', '.join(extra)})" if extra else n] = n
    return opts


@st.cache_data
def combined_demand(scarcity, postings, side=None, group=None):
    """Demand per skill from both sources, optionally within one group.

    The two taxonomies are not compatible (6 categories vs 11 job families), so
    a group can only be defined by one side. The chosen side is filtered to that
    group; the other side reports its overall figure for the same skills, since
    it has no equivalent group to filter to.
    """
    a_src, b_src = scarcity, postings
    if side == "2026":
        a_src = scarcity[scarcity.category == group]
        b_src = postings[postings.skill_name.isin(a_src.skill_name)]
    elif side == "2024":
        b_src = postings[postings.job_family == group]
        a_src = scarcity[scarcity.skill_name.isin(b_src.skill_name)]

    a = (a_src.groupby("skill_name")
         .agg(demand_count_2026=("demand_count", "sum"),
              demand_pct_2026=("demand_pct", "mean")).reset_index())
    b = (b_src.groupby("skill_name")
         .agg(demand_count_2024=("demand_count", "sum"),
              demand_pct_2024=("demand_pct", "mean")).reset_index())
    out = a.merge(b, on="skill_name", how="outer")
    out["demand_pct_avg"] = out[["demand_pct_2026", "demand_pct_2024"]].mean(axis=1)
    return out.sort_values("demand_pct_avg", ascending=False).round(2)


scarcity, linkedin, cooc, lk_pay, totals, vocab, relations, descriptions = get_tables()
prose = build_prose_patterns(vocab)
jobs_idx, vectors = get_index()

categories = sorted(scarcity.category.unique())
families = sorted(linkedin.job_family.unique())

st.title("Skill and Job Recommender")

# ------------------------------------------------------------------ sidebar
# Streamlit sidebars are global, so the two groups are kept visually separate
# rather than merged into one pile of controls.
st.sidebar.subheader("Job search")
job_variety = st.sidebar.slider(
    "Variety in job results", 0.0, 1.0, 0.7, 0.1, key="jvar",
    help="Only applies when you type a description. 1.0 ranks purely by text "
         "match and returns near-duplicates. Lower gives a broader spread.")

st.sidebar.divider()

st.sidebar.subheader("Skill search")
source = st.sidebar.radio("Data source", [INDEX_2026, POSTINGS, BOTH], key="ssrc")

if source == INDEX_2026:
    st.sidebar.caption("141 skills, 6 categories, July 2026. Scarcity, pay and demand.")
elif source == POSTINGS:
    st.sidebar.caption("58,954 postings, 11 job families, January 2024. Demand and "
                       "stated pay only.")
else:
    st.sidebar.caption("Only demand is reported by both sources, so that is the only "
                       "measure used. The taxonomies differ, so results are per "
                       "skill rather than per category.")

skill_variety = st.sidebar.slider(
    "Variety in skill results", 0.0, 1.0, 0.7, 0.1, key="svar",
    help="Lower values give fewer near-duplicate skills.")

weights = {"demand": st.sidebar.slider("Demand", 0.0, 1.0, 0.5, 0.1, key="wdem")}
if source == INDEX_2026:
    weights["scarcity"] = st.sidebar.slider("Scarcity", 0.0, 1.0, 1.0, 0.1, key="wsca")
    weights["pay"] = st.sidebar.slider("Salary premium", 0.0, 1.0, 0.8, 0.1, key="wpay")
else:
    weights["scarcity"] = weights["pay"] = 0.0

jobs_tab, skills_tab, learn_tab = st.tabs(
    ["Find jobs", "Find skills", "Study guide"])

# =============================================================== FIND JOBS
with jobs_tab:
    if jobs_idx is None:
        st.error("Search index missing. Run `python build_embeddings.py` first.")
    else:
        st.header("Find jobs")
        query = st.text_area(
            "Describe the work you want, or leave blank and just use the filters",
            height=70, key="jobq",
            placeholder="remote platform work with kubernetes and some python")

        f1, f2, f3 = st.columns(3)
        fam_pick = f1.selectbox(
            "Job family", ["any"] + families, key="jfam",
            format_func=lambda f: "any" if f == "any" else label(f))
        site_pick = f2.selectbox("Worksite", ["any", "remote", "hybrid", "onsite"],
                                 key="jsite")
        level_pick = f3.selectbox(
            "Seniority", ["any", "junior", "mid", "senior", "lead", "principal"],
            key="jlvl")

        # ---------------------------------------------------------- filtering
        if query:
            hits = search_jobs(query, jobs_idx, vectors, top_n=200,
                               category=None if fam_pick == "any" else fam_pick,
                               balance=job_variety)
        else:
            hits = jobs_idx.copy()
            if fam_pick != "any":
                hits = hits[hits.job_family == fam_pick]

        if site_pick != "any" and "worksite" in hits:
            hits = hits[hits.worksite == site_pick]
        if level_pick != "any" and "seniority" in hits:
            hits = hits[hits.seniority == level_pick]

        matched = len(hits)

        hits = hits.head(25)

        # ------------------------------------------------------------ display
        if hits.empty:
            st.warning("Nothing matched those filters. Try loosening one.")
        else:
            if query:
                st.subheader(f"Closest {len(hits)} of {matched:,} matching jobs")
            else:
                st.subheader(f"{len(hits)} of {matched:,} matching jobs")
                st.caption("No description given, so there is no relevance score "
                           "and no meaningful order. Type a description to rank "
                           "these by how well they match.")

            show = [c for c in ["job_title", "company", "job_location",
                                "job_family", "salary_label", "worksite",
                                "seniority", "relevance"] if c in hits]
            st.caption("Click a row to read that job's description below.")
            event = st.dataframe(hits[show], hide_index=True,
                                 on_select="rerun", selection_mode="single-row",
                                 key="jtable")

            if "worksite_stated" in hits:
                told = hits.worksite_stated.fillna(False).mean()
                st.caption(
                    f"{100 * told:.0f}% of these postings actually stated a "
                    "worksite. The rest default to onsite, so treat the onsite "
                    "count as an upper bound.")

            chosen_rows = event.selection.rows if event and event.selection else []
            if chosen_rows:
                row = hits.iloc[chosen_rows[0]]
                st.subheader(row.job_title)
                st.caption(f"{row.company}  ·  {row.job_location}")
                st.write(row.job_summary)
            else:
                st.info("Select a row above to read the full job description.")

            st.subheader("Skills these jobs ask for")
            st.caption("Counted across the matched jobs above, so this reflects "
                       "your filters, not the whole market.")
            counts = {}
            for text in hits.job_summary:
                for skill in extract_from_prose(text, prose):
                    counts[skill] = counts.get(skill, 0) + 1

            if counts:
                found = pd.DataFrame(sorted(counts.items(), key=lambda x: -x[1]),
                                     columns=["skill_name", "jobs"]).head(12)
                found["share_pct"] = (100 * found.jobs / len(hits)).round(1)
                st.dataframe(found, hide_index=True)
                st.bar_chart(found.set_index("skill_name")["share_pct"])
            else:
                st.caption("No known skills found in these descriptions.")

# ============================================================= FIND SKILLS
with skills_tab:
    st.header("Find skills")

    st.subheader("Look up a skill")

    options = skill_options(tuple(vocab))
    picked = st.selectbox(
        "Pick a skill, or start typing to filter the list", list(options),
        index=None, key="spick",
        placeholder=f"kubernetes, k8s, html, excel...  ({len(vocab)} skills)")
    skill = options.get(picked) if picked else None

    if skill:
        if skill in descriptions:
            st.caption(descriptions[skill])

        in_2026 = sorted(scarcity[scarcity.skill_name == skill].category.unique())
        in_jobs = sorted(linkedin[linkedin.skill_name == skill].job_family.unique())

        c1, c2 = st.columns(2)
        c1.metric("2026 index categories", f"{len(in_2026)} of 6")
        c1.caption(", ".join(in_2026) if in_2026 else "not measured in 2026")
        c2.metric("2024 job families", f"{len(in_jobs)} of {len(families)}")
        c2.caption(", ".join(label(f) for f in in_jobs) if in_jobs
                   else "not found in postings")

        if source == INDEX_2026 and in_2026:
            chosen = st.selectbox(f"Where {skill} appears", ["any"] + in_2026,
                                  key="swhere")
            rows = scarcity[scarcity.skill_name == skill]
            if chosen != "any":
                rows = rows[rows.category == chosen]
            st.dataframe(rows[["category", "skill_name", "demand_count",
                               "demand_pct", "median_days_open",
                               "salary_premium_pct", "repost_rate_pct",
                               "scarcity_score"]].sort_values("scarcity_score",
                                                             ascending=False),
                         hide_index=True)
            if chosen == "any" and len(rows) > 1:
                st.caption("The same skill behaves differently in each category, "
                           "which is why the two are kept together as one row "
                           "rather than averaged into a single figure per skill.")
        elif source == POSTINGS and in_jobs:
            chosen = st.selectbox(f"Where {skill} appears", ["any"] + in_jobs,
                                  key="swheref",
                                  format_func=lambda v: "any" if v == "any"
                                  else label(v))
            rows = linkedin[linkedin.skill_name == skill]
            if chosen != "any":
                rows = rows[rows.job_family == chosen]
            st.dataframe(rows.sort_values("demand_pct", ascending=False),
                         hide_index=True)
        elif source == BOTH:
            st.dataframe(combined_demand(scarcity, linkedin)
                         .query("skill_name == @skill"), hide_index=True)
        else:
            st.warning(f"{skill} does not appear in the selected source.")

        if source != INDEX_2026 and not lk_pay.empty:
            rows = lk_pay[lk_pay.skill_name == skill]
            if not rows.empty:
                st.subheader("What postings mentioning this skill paid, Jan 2024")
                st.caption("One figure per employer, then the median across "
                           "employers, so one large company cannot set the number.")
                st.dataframe(rows[["job_family", "median_salary",
                                   "salary_premium_pct", "companies",
                                   "jobs_with_salary"]], hide_index=True)

        st.subheader(f"Skills that appear alongside {skill}")
        near = similar_by_cooccurrence(cooc, totals, skill, top_n=40)

        if near.empty or near.skill_name.isna().all():
            st.caption("No co-occurrence data for this skill.")
        elif not relations:
            st.caption("Run `python build_skill_meaning.py` to label these as "
                       "complements or substitutes.")
            st.dataframe(near.head(8), hide_index=True)
        else:
            near["relation"] = [relations.get((skill, o), ("unlabelled", None))[0]
                                for o in near.skill_name]
            near["meaning"] = [relations.get((skill, o), (None, None))[1]
                               for o in near.skill_name]

            def shortlist(frame, n=8):
                """Apply diversity re-ranking, then take the top n."""
                names = list(frame.skill_name)
                if skill_variety < 1.0 and len(names) > 1:
                    m = skill_similarity_matrix(names, cooc, totals)
                    keep = mmr(frame.association.values, m,
                               balance=skill_variety, top_n=n)
                    return frame.iloc[keep]
                return frame.head(n)

            cols = ["skill_name", "association", "meaning"]
            comps = near[near.relation == "complements"]
            subs = near[near.relation == "substitutes"]

            st.markdown("**Worth learning next**")
            st.caption("These share job ads with " + skill + " but do a different "
                       "job, so learning them adds something you do not have.")
            if comps.empty:
                st.caption("None found.")
            else:
                st.dataframe(shortlist(comps)[cols], hide_index=True)

            st.markdown("**Alternatives, you probably only need one**")
            st.caption("These share job ads with " + skill + " and do the same "
                       "kind of job, so the second one adds little.")
            if subs.empty:
                st.caption("None found.")
            else:
                st.dataframe(shortlist(subs, 6)[cols], hide_index=True)

            with st.expander("How is this decided?"):
                st.markdown(
                    "Two separate signals.\n\n"
                    "**association** comes from real job ads and says how often "
                    "the two skills are asked for together.\n\n"
                    "**meaning** comes from embedding a one-line description of "
                    "each skill, with the name and vendor stripped out so the "
                    "comparison is about what the tool does rather than who makes "
                    "it.\n\n"
                    "Sharing job ads and describing the same kind of thing means "
                    "**substitutes**, like PyTorch and TensorFlow. Sharing job "
                    "ads while describing different things means "
                    "**complements**, like Docker and Kubernetes. Co-occurrence "
                    "alone cannot tell these apart, because a job ad saying "
                    "\"X and Y\" looks identical to one saying \"X or Y\".")
    else:
        st.info("Pick a skill above to see where it appears, what it pays, and "
                "which skills go with it.")

    st.divider()
    st.subheader("Best skills in a group")

    if sum(weights.values()) == 0:
        st.warning("Set at least one slider above zero.")
    elif source == INDEX_2026:
        cat = st.selectbox("Category", categories, key="srank")
        ranked = rank_skills(scarcity, cat, weights)
        st.dataframe(ranked[["skill_name", "score", "demand_pct",
                             "median_days_open", "salary_premium_pct"]],
                     hide_index=True)
        st.bar_chart(ranked.set_index("skill_name")["score"])
    elif source == POSTINGS:
        fam = st.selectbox("Job family", families, key="srankf", format_func=label)
        top = linkedin[linkedin.job_family == fam].nlargest(15, "demand_pct")
        st.caption("Ranked by demand share. January 2024 data.")
        st.dataframe(top, hide_index=True)
        st.bar_chart(top.set_index("skill_name")["demand_pct"])
    else:
        # The two taxonomies are not interchangeable, so instead of inventing a
        # shared grouping the user picks which side defines the group. The other
        # source then contributes its own demand for those same skills.
        labels = ({f"2026 index  ·  {c}": ("2026", c) for c in categories}
                  | {f"Job postings  ·  {label(f)}": ("2024", f) for f in families})
        labels = {"All skills, no grouping": (None, None), **labels}

        pick = st.selectbox("Group", list(labels), key="srankb")
        side, group = labels[pick]

        top = combined_demand(scarcity, linkedin, side, group).head(20)

        if side == "2026":
            st.caption(f"Demand within the 2026 index category **{group}**. The "
                       "2024 columns are that skill's overall posting demand, "
                       "because the postings have no equivalent category.")
        elif side == "2024":
            st.caption(f"Demand within the 2024 job family **{label(group)}**. The "
                       "2026 columns are that skill's overall index demand, "
                       "because the index has no equivalent family.")
        else:
            st.caption("Ranked by average demand across both sources. A blank means "
                       "that source does not measure the skill, which is not the "
                       "same as zero demand.")
        if top.empty:
            st.warning("No skills in that group appear in either table.")
        else:
            st.dataframe(top, hide_index=True)
            st.bar_chart(top.set_index("skill_name")["demand_pct_avg"])

# ============================================================= STUDY GUIDE
with learn_tab:
    st.header("Study guide")
    st.caption("Pick skills or a job role. Everything above the videos comes "
               "from this project's own data. The videos and the book come from "
               "the YouTube and Google Books APIs.")

    try:
        api_key = st.secrets.get("YOUTUBE_API_KEY", "")
    except Exception:
        # older Streamlit raises rather than returning empty when there
        # is no secrets.toml at all, and that would kill the whole tab
        api_key = ""

    roles, role_skills, role_vectors = get_roles()

    if not api_key:
        st.warning("No YOUTUBE_API_KEY in .streamlit/secrets.toml, so videos "
                   "will fall back to a search link. Books still work.")

    kind = st.radio("Build a guide for", ["Skills", "A job role"],
                    horizontal=True, key="lkind")

    # subject is what the videos and book are about, and both branches fill it,
    # so one shared block at the bottom draws sections 'Watch' and 'Read' and
    # the two paths cannot drift apart.
    subject = video_q = book_q = None
    step = 1

    # ------------------------------------------------------------ skills
    if kind == "Skills":
        lopts = skill_options(tuple(vocab))
        lpicks = st.multiselect(
            "Skills you already know", list(lopts), key="lskills",
            placeholder=f"pick one or several  ({len(vocab)} skills)")
        chosen = [lopts[p] for p in lpicks]

        if chosen:
            st.subheader(f"{step}. What these are")
            step += 1
            for s in chosen:
                st.markdown(f"**{s}**  ·  "
                            + descriptions.get(s, "no description written yet."))

            st.subheader(f"{step}. Why they matter")
            step += 1
            rows = []
            for s in chosen:
                sc = scarcity[scarcity.skill_name == s]
                jb = linkedin[linkedin.skill_name == s]
                rows.append({
                    "Skill": s,
                    "Salary premium %": (None if sc.empty
                                         else round(sc.salary_premium_pct.median(), 1)),
                    "Share of index postings %": (None if sc.empty
                                                  else round(sc.demand_pct.median(), 1)),
                    "Postings asking for it": int(jb.demand_count.sum()),
                    "Job families asking for it": jb.job_family.nunique(),
                })
            st.dataframe(pd.DataFrame(rows), hide_index=True)
            st.caption("The first two columns come from the 2026 index, the last "
                       "two from the 2024 postings. Two sources side by side, "
                       "never added. A blank means the 2026 index does not "
                       "measure that skill, which is not the same as zero.")

            st.subheader(f"{step}. Demand by job family")
            step += 1
            jb = linkedin[linkedin.skill_name.isin(chosen)]
            if jb.empty:
                st.caption("None of these appear in the 2024 postings.")
            else:
                counts = (jb.pivot_table(index="job_family", columns="skill_name",
                                         values="demand_count", aggfunc="sum")
                          .fillna(0))
                counts = counts.loc[counts.sum(axis=1)
                                    .sort_values(ascending=False).index]
                counts.index = [label(f) for f in counts.index]
                st.bar_chart(counts)
                st.caption("Number of postings in each job family that ask for "
                           "the skill, January 2024.")

                detail = jb[["job_family", "skill_name", "demand_count",
                             "demand_pct"]].copy()
                detail["job_family"] = detail.job_family.map(label)
                st.dataframe(detail.sort_values("demand_count", ascending=False)
                             .rename(columns={
                                 "job_family": "Job family",
                                 "skill_name": "Skill",
                                 "demand_count": "Postings",
                                 "demand_pct": "Share of that family %"}),
                             hide_index=True)
                st.caption("The count says how many jobs. The share says how "
                           "normal the skill is in that family, which matters "
                           "because the families are very different sizes.")

            near = neighbours_for_known(cooc, totals, relations, chosen)
            comps = near[near.relation == "complements"].head(6)
            subs = near[near.relation == "substitutes"].head(6)
            # "1 of 1" is noise when only one skill is picked
            ncols = (["skill_name", "association", "linked_to"] if len(chosen) > 1
                     else ["skill_name", "association"])

            st.subheader(f"{step}. Learn these next")
            step += 1
            if comps.empty:
                st.caption("No complementary skills found.")
            else:
                st.caption("These share job ads with what you know but do a "
                           "different job, so each one adds something new. "
                           "Ranked by how many of your skills they go with, "
                           "then by how strong the link is.")
                st.dataframe(comps[ncols], hide_index=True)
                st.bar_chart(comps.set_index("skill_name")["association"])
                skill_material_buttons(list(comps.skill_name), api_key)

            st.subheader(f"{step}. Skills you can skip")
            step += 1
            if subs.empty:
                st.caption("Nothing in the data does the same job as what you "
                           "already know.")
            else:
                st.caption("These do the same kind of job as a skill you have, "
                           "so learning them adds little.")
                st.dataframe(subs[ncols], hide_index=True)

            # videos and a book are about ONE thing, so with several skills
            # picked you say which. Doing all of them would multiply the quota.
            if len(chosen) == 1:
                subject = chosen[0]
            else:
                subject = st.selectbox("Material for which skill?", chosen,
                                       key="lmat")
            video_q, book_q = f"{subject} tutorial", subject

    # ---------------------------------------------------------- a job role
    else:
        if roles.empty:
            st.error("roles.csv missing. Run `python build_roles.py` first.")
        else:
            rquery = st.text_area(
                "Describe the work, or leave blank and just use the filters",
                height=70, key="lrq",
                placeholder="designing cloud networks for a large company")

            g1, g2 = st.columns(2)
            rfam = g1.selectbox(
                "Job family", ["any"] + families, key="lrfam",
                format_func=lambda f: "any" if f == "any" else label(f))
            rsort = g2.selectbox("Sort by", ["best match", "highest pay",
                                             "most postings"], key="lrsort")

            # filtering the table means filtering the vectors by the SAME mask,
            # or a search result would point at the wrong role
            fmask = (np.ones(len(roles), dtype=bool) if rfam == "any"
                     else (roles.job_family == rfam).to_numpy())
            pool = roles[fmask]
            pool_vecs = None if role_vectors is None else role_vectors[fmask]

            if pool.empty:
                st.warning("No roles in that job family.")
                shown = pool
            elif rquery and pool_vecs is not None:
                # the role centroid is the average of every posting for that
                # role, so this matches on what the job involves rather than on
                # the words in its title
                q = get_model().encode([rquery], normalize_embeddings=True)
                scores = pool_vecs @ q.astype("float32")[0]
                take = np.argsort(-scores)[:50]
                shown = pool.iloc[take].assign(relevance=scores[take].round(3))
                st.caption(f"Closest 50 of {len(pool)} roles by meaning, then "
                           "sorted.")
            else:
                if rquery and pool_vecs is None:
                    st.warning("role_vectors.npy is missing or does not line up "
                               "with roles.csv, so search by meaning is off. "
                               "Rerun `python build_roles.py`.")
                shown = pool
                st.caption(f"{len(pool)} roles. Type above to narrow this by "
                           "meaning.")

            if not shown.empty:
                # A median pay from one or two employers is not a median, so it
                # is blanked everywhere rather than only excluded from the pay
                # sort. Showing $421,000 quoted by a single company, however it
                # got to the top of the table, is worse than showing nothing.
                shown = shown.copy()
                thin = shown.salary_companies < MIN_PAY_EMPLOYERS
                shown.loc[thin, "median_salary"] = np.nan

                if rsort == "highest pay":
                    shown = shown.sort_values("median_salary", ascending=False,
                                              na_position="last")
                elif rsort == "most postings":
                    shown = shown.sort_values("postings", ascending=False)
                elif "relevance" not in shown:
                    shown = shown.sort_values("postings", ascending=False)
                shown = shown.head(25)
                st.caption(f"Pay is left blank unless {MIN_PAY_EMPLOYERS} or more "
                           f"employers stated it, so one company cannot set a "
                           f"figure. That hides pay for {int(thin.sum())} of "
                           f"these roles.")

            cols = [c for c in ["role_label", "job_family", "postings",
                                "companies", "median_salary",
                                "salary_companies", "pct_senior_or_above",
                                "relevance"] if c in shown]
            if not shown.empty:
                st.caption("Click a row to build that role's study guide.")
                revent = st.dataframe(shown[cols], hide_index=True,
                                      on_select="rerun",
                                      selection_mode="single-row", key="lrtable")
                picked = revent.selection.rows if revent and revent.selection else []
                if picked:
                    subject = shown.role.iat[picked[0]]

            if subject:
                row = shown[shown.role == subject].iloc[0]
                video_q = f"{row.role_label} career guide"
                book_q = row.role_label

                st.subheader(f"{step}. What the job is")
                step += 1
                st.caption(f"Closest real posting to the average of all "
                           f"{row.postings:,}: **{row.example_title}** at "
                           f"{row.example_company}")
                st.write(row.description)

                st.subheader(f"{step}. Why bother")
                step += 1
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Postings", f"{row.postings:,}")
                m2.metric("Employers hiring", f"{row.companies:,}")
                m3.metric("Median pay",
                          "not enough employers" if pd.isna(row.median_salary)
                          else f"${row.median_salary:,.0f}")
                m4.metric("Senior or above", f"{row.pct_senior_or_above:.0f}%")
                if pd.isna(row.median_salary):
                    st.caption(f"Fewer than {MIN_PAY_EMPLOYERS} employers stated "
                               f"pay for this role, so no median is reported.")
                else:
                    st.caption(f"One figure per employer, then the median "
                               f"across {row.salary_companies} of them.")

                st.subheader(f"{step}. Learn these skills")
                step += 1
                rs = role_skills[role_skills.role == subject].nlargest(
                    6, "share_pct")
                st.dataframe(rs[["skill_name", "jobs", "share_pct"]].rename(
                    columns={"skill_name": "Skill",
                             "jobs": "Postings asking for it",
                             "share_pct": "Share of this role's postings %"}),
                    hide_index=True)
                st.bar_chart(rs.set_index("skill_name")["share_pct"])
                st.caption(f"Out of {row.postings:,} postings for this role. "
                           "The share is the useful number: 300 mentions means "
                           "something different in a role with 400 postings than "
                           "in one with 6,000.")
                skill_material_buttons(list(rs.skill_name), api_key)

    # ------------------------------------------------- shared: watch and read
    if subject and video_q:
        st.divider()
        st.subheader(f"{step}. Watch")
        step += 1
        vids, err = cached_videos(video_q, api_key)
        if err:
            st.caption(f"No videos loaded: {err}")
        if vids:
            show_videos(vids)
        st.link_button("More videos on YouTube", youtube_search_link(video_q))

        st.subheader(f"{step}. Read")
        books, berr = cached_books(book_q, api_key)
        show_books(books, berr)
        st.link_button("More books", books_search_link(book_q))

        # A failed call is cached like a successful one, so enabling an API or
        # waiting out a quota reset would otherwise change nothing for an hour.
        if err or berr:
            if st.button("Try the APIs again", key="lretry"):
                cached_videos.clear()
                cached_books.clear()
                st.rerun()

    elif not subject:
        st.info("Pick skills or a job role above to build a study guide.")