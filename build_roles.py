"""Collapse 58,954 postings into distinct job roles.

A search that returns postings gives you Data Analyst, Senior Data Analyst and
Data Analyst II as three results for the same job. This groups them into one
role, then summarises what that role pays, where it sits, which skills it asks
for, and picks the single posting that best represents it.

Run after build_embeddings.py and build_salary.py:
    python build_roles.py
"""

import re
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from matcher import EXTRA_SKILLS, build_prose_patterns, extract_from_prose
from taxonomy import base_role, role_label

HERE = Path(__file__).parent
JOBS = HERE / "tech_jobs.csv"
ENRICHED = HERE / "jobs_enriched.csv"
VECTORS = HERE / "job_vectors.npy"
SCARCITY_CSV = HERE / "skill-scarcity-index.csv"
OUT_ROLES = HERE / "roles.csv"
OUT_ROLE_SKILLS = HERE / "role_skills.csv"
OUT_ROLE_VECTORS = HERE / "role_vectors.npy"

MIN_POSTINGS = 10     # fewer than this and the aggregates are not measurements
TOP_SKILLS = 15
SUMMARY_CHARS = 1200

DUTY_VERBS = {
    "develop", "design", "build", "manage", "lead", "analyze", "collaborate",
    "support", "maintain", "implement", "create", "write", "test", "deploy",
    "monitor", "optimize", "ensure", "provide", "assist", "coordinate",
    "conduct", "perform", "research", "review", "document", "train",
    "troubleshoot", "configure", "administer", "plan", "execute", "diagnose",
    "install", "oversee", "author", "define", "drive", "own", "identify",
    "prepare", "communicate", "partner", "work",
}

# Sentences that would otherwise pass the duty-verb check but are boilerplate
# (EEO statements, benefits, company-marketing intros) rather than anything
# about the work itself.
BOILERPLATE = re.compile(
    r"equal opportunit|reasonable accommodat|veteran status|sexual orientation|"
    r"background check|drug test|401\(?k\)?|paid time off|health insurance|"
    r"protected (?:class|veteran)|race,? color|disability status|"
    r"national origin|gender identity|"
    r"build your career|join our team|about us\b|who we are\b|"
    r"one of the nation|founded in \d|headquartered in", re.I)


def duty_sentences(companies, texts, limit=4):
    """Sentences that read like a real job duty, ranked by how many DIFFERENT
    companies phrase almost the same thing.

    Counting distinct companies rather than raw postings matters here for the
    same reason build_salary.py medians pay per company first: one employer
    that reposts a near-identical listing many times (common in this data)
    would otherwise dominate the ranking and make one company's phrasing look
    like the market norm.
    """
    seen_by = {}
    example = {}
    for company, text in zip(companies, texts):
        for sent in re.split(r"(?<=[.!?])\s+", str(text)):
            sent = sent.strip()
            if "\n" in sent or not (25 <= len(sent) <= 170) or BOILERPLATE.search(sent):
                continue
            first = re.match(r"[A-Za-z]+", sent)
            if not first or first.group(0).lower() not in DUTY_VERBS:
                continue
            key = re.sub(r"[^a-z0-9 ]", "", sent.lower())
            key = re.sub(r"\s+", " ", key).strip()
            if not key:
                continue
            seen_by.setdefault(key, set()).add(company)
            example.setdefault(key, sent.rstrip(". ") + ".")

    ranked = sorted(seen_by, key=lambda k: -len(seen_by[k]))
    chosen = [k for k in ranked if len(seen_by[k]) >= 2][:limit]
    if len(chosen) < limit:
        for k in ranked:          # not enough repeats: fill in whatever showed up
            if k not in chosen:
                chosen.append(k)
            if len(chosen) >= limit:
                break
    return [example[k] for k in chosen]


def summarize_role(role_label, duties):
    """What this role actually asks you to do, built from sentences real
    postings repeat rather than generated or taken from one company's ad."""
    if not duties:
        return (f"Postings for {role_label} do not phrase their day-to-day "
                f"duties consistently enough to summarise automatically.")
    return f"{role_label} postings typically ask you to: " + " ".join(duties)


def representative(vectors, rows):
    """Index of the posting closest to the average of its role.

    Averaging every posting for a role gives a point describing the role in
    general. The real posting nearest that point is the least unusual example of
    it, which makes it a fair thing to show as "what this job involves" rather
    than whichever posting happened to be first.
    """
    block = vectors[rows]
    centre = block.mean(axis=0)
    centre = centre / (np.linalg.norm(centre) + 1e-9)
    return rows[int(np.argmax(block @ centre))]


def main():
    jobs = pd.read_csv(JOBS)
    vectors = np.load(VECTORS)
    if len(jobs) != len(vectors):
        raise SystemExit(f"tech_jobs.csv has {len(jobs)} rows but "
                         f"job_vectors.npy has {len(vectors)}. Rebuild both.")

    extra = pd.read_csv(ENRICHED, usecols=[
        "job_link", "salary", "seniority", "worksite", "worksite_stated"])
    jobs = jobs.merge(extra.drop_duplicates("job_link"), on="job_link", how="left")

    jobs["role"] = jobs.job_title.map(base_role)
    jobs = jobs[jobs.role.notna()].reset_index()      # 'index' keeps the vector row
    print(f"{len(jobs):,} postings carry a usable role")

    counts = jobs.role.value_counts()
    keep = counts[counts >= MIN_POSTINGS].index
    jobs = jobs[jobs.role.isin(keep)]
    print(f"{len(keep):,} roles with {MIN_POSTINGS}+ postings, "
          f"covering {len(jobs):,} postings")

    patterns = build_prose_patterns(
        sorted(set(pd.read_csv(SCARCITY_CSV).skill_name) | set(EXTRA_SKILLS)))

    role_rows, skill_rows, centres = [], [], []
    for n, (role, group) in enumerate(jobs.groupby("role")):
        rows = group["index"].to_numpy()
        rep = representative(vectors, rows)
        rep_job = jobs[jobs["index"] == rep].iloc[0]

        # one salary per company, then the median across companies
        paid = group[group.salary.notna()]
        per_company = paid.groupby(group.company.fillna("?")).salary.median()
        median_pay = float(per_company.median()) if len(per_company) else np.nan

        stated = group[group.worksite_stated.fillna(False)]
        flexible = (stated.worksite != "onsite").mean() if len(stated) else np.nan

        levels = group.seniority.value_counts()
        senior_share = 100 * levels.reindex(
            ["senior", "lead", "principal"]).fillna(0).sum() / len(group)

        found = Counter()
        for text in group.job_summary:
            for skill in extract_from_prose(text, patterns):
                found[skill] += 1

        for skill, hits in found.most_common(TOP_SKILLS):
            skill_rows.append({"role": role, "skill_name": skill, "jobs": hits,
                               "share_pct": round(100 * hits / len(group), 1)})

        duties = duty_sentences(group.company.fillna("?"), group.job_summary, limit=4)
        if not duties:
            duties = duty_sentences([rep_job.company], [rep_job.job_summary], limit=4)

        label = role_label(role)
        n_companies = group.company.nunique()
        role_rows.append({
            "role": role,
            "role_label": label,
            "job_family": group.job_family.mode().iat[0],
            "postings": len(group),
            "companies": n_companies,
            "median_salary": round(median_pay) if median_pay == median_pay else np.nan,
            "salary_companies": len(per_company),
            "pct_senior_or_above": round(senior_share, 1),
            "pct_flexible_when_stated": round(100 * flexible, 1) if flexible == flexible else np.nan,
            "pct_stated_worksite": round(100 * group.worksite_stated.fillna(False).mean(), 1),
            "top_skills": ", ".join(s for s, _ in found.most_common(6)),
            "example_title": rep_job.job_title,
            "example_company": rep_job.company,
            "description": str(rep_job.job_summary)[:SUMMARY_CHARS],
            "summary": summarize_role(label, duties),
        })

        block = vectors[rows].mean(axis=0)
        centres.append(block / (np.linalg.norm(block) + 1e-9))

        if n % 50 == 0:
            print(f"  summarised {n} roles", end="\r")

    print(f"  summarised {len(role_rows)} roles")

    roles = pd.DataFrame(role_rows).sort_values("postings", ascending=False)
    roles.to_csv(OUT_ROLES, index=False)
    pd.DataFrame(skill_rows).to_csv(OUT_ROLE_SKILLS, index=False)

    # role centroids, in the same order as roles.csv, for searching by meaning
    order = {r: i for i, r in enumerate(sorted(jobs.role.unique()))}
    np.save(OUT_ROLE_VECTORS,
            np.stack([centres[order[r]] for r in roles.role]).astype("float32"))

    print(f"\n{OUT_ROLES.name}: {len(roles)} roles")
    print(f"{OUT_ROLE_SKILLS.name}: {len(skill_rows)} role and skill pairs")
    print(f"{OUT_ROLE_VECTORS.name}: {len(roles)} centroids")

    print("\ntop 15 roles by postings:")
    cols = ["role_label", "job_family", "postings", "companies", "median_salary",
            "pct_senior_or_above"]
    print(roles.head(15)[cols].to_string(index=False))

    print("\nskills asked for by the largest role:")
    top = roles.role.iat[0]
    rs = pd.DataFrame(skill_rows)
    print(rs[rs.role == top].head(8).to_string(index=False))


if __name__ == "__main__":
    main()

