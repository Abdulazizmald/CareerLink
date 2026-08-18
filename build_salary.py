"""Extract salary and seniority from job descriptions, then aggregate per skill.

Run after build_embeddings.py, which produces tech_jobs.csv:
    python build_salary.py
"""

from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from matcher import build_prose_patterns, extract_from_prose, EXTRA_SKILLS
from salary import extract_salary, detect_seniority, midpoint
from taxonomy import detect_worksite, worksite_is_stated

HERE = Path(__file__).parent
JOBS = HERE / "tech_jobs.csv"
SUMMARIES = HERE / "job_summary.csv"
SCARCITY_CSV = HERE / "skill-scarcity-index.csv"
OUT = HERE / "linkedin_salary.csv"
OUT_JOBS = HERE / "jobs_enriched.csv"

CHUNK = 50_000
MIN_COMPANIES = 15     # a premium built on fewer employers than this is noise
MIN_SALARIED = 25      # and it needs enough actual salaried postings behind it


def full_summaries(links):
    """Reread the untruncated descriptions.

    tech_jobs.csv was cut to 2,000 characters for embedding, but US postings
    put the pay disclosure at the very end, so the truncated text loses most
    salaries. Embeddings do not need the tail; salary extraction does.
    """
    kept = []
    for chunk in pd.read_csv(SUMMARIES, chunksize=CHUNK):
        kept.append(chunk[chunk.job_link.isin(links)])
    full = pd.concat(kept, ignore_index=True)
    return dict(zip(full.job_link, full.job_summary.fillna("")))


def main():
    jobs = pd.read_csv(JOBS)

    if SUMMARIES.exists():
        print("reading untruncated descriptions...")
        text_by_link = full_summaries(set(jobs.job_link))
        jobs["job_summary"] = jobs.job_link.map(text_by_link).fillna(jobs.job_summary)
    else:
        print("job_summary.csv not found, using truncated text "
              "(expect much lower salary coverage)")

    vocab = sorted(set(pd.read_csv(SCARCITY_CSV).skill_name) | set(EXTRA_SKILLS))
    patterns = build_prose_patterns(vocab)

    salaries, seniorities, skills_per_job = [], [], []
    worksites, stated = [], []
    total = len(jobs)
    for i, (title, text) in enumerate(zip(jobs.job_title.fillna(""), jobs.job_summary)):
        low, high = extract_salary(text)
        salaries.append(midpoint(low, high))
        seniorities.append(detect_seniority(title, text))
        worksites.append(detect_worksite(title, text))
        stated.append(worksite_is_stated(title, text))
        skills_per_job.append(extract_from_prose(text, patterns))
        if i % 2000 == 0:
            print(f"  parsed {i:,} of {total:,} jobs", end="\r")
    print(f"  parsed {total:,} of {total:,} jobs")

    jobs["salary"] = salaries
    jobs["seniority"] = seniorities
    jobs["worksite"] = worksites
    jobs["worksite_stated"] = stated

    # every job is kept. Missing pay is a fact about the posting, not a reason
    # to throw the job away, so it is labelled rather than dropped.
    jobs["salary_label"] = jobs.salary.apply(
        lambda v: "Undisclosed" if pd.isna(v) else f"${v:,.0f}")
    # job_summary is kept (renamed) rather than dropped: the Jobs tab shows each
    # posting's real text as-is, and this is the untruncated version already
    # fetched above for salary extraction.
    jobs.rename(columns={"job_summary": "description"}).to_csv(OUT_JOBS, index=False)
    print(f"{OUT_JOBS.name}: all {len(jobs):,} jobs kept, pay labelled where missing")

    found = jobs.salary.notna()
    print(f"jobs with a usable salary: {found.sum():,} of {len(jobs):,} "
          f"({100 * found.mean():.1f}%)")
    print(f"median across all: ${jobs.salary.median():,.0f}")
    print("\nby job family:")
    print(jobs[found].groupby("job_family").salary.agg(["count", "median"]).round(0).to_string())
    print("\nseniority mix:")
    print(jobs.seniority.value_counts().to_string())

    print("\nworksite mix:")
    print(jobs.worksite.value_counts().to_string())
    told = jobs.worksite_stated.mean()
    print(f"the posting actually said something in {100 * told:.1f}% of cases; "
          f"the rest defaulted to onsite")
    print("\namong postings that DID state it:")
    print(jobs[jobs.worksite_stated].worksite.value_counts().to_string())

    # for the AGGREGATION only, drop repeat postings of the same job
    agg = jobs.drop_duplicates(subset=["job_title", "company", "job_summary"])
    print(f"\nfor salary aggregation: {len(agg):,} unique postings "
          f"({len(jobs) - len(agg):,} repeats set aside)")
    agg_found = agg.salary.notna()

    # baseline pay per family, one vote per company
    company_pay = (agg[agg_found].groupby(["job_family", "company"]).salary.median()
                   .reset_index())
    baseline = company_pay.groupby("job_family").salary.median()

    # collect salaries per skill, keyed by company so no single employer dominates
    pay = defaultdict(lambda: defaultdict(list))
    seen = Counter()
    keep = agg.index
    for cat, comp, sal, found_skills in zip(agg.job_family, agg.company.fillna("?"),
                                            agg.salary,
                                            [skills_per_job[i] for i in keep]):
        for skill in found_skills:
            seen[(cat, skill)] += 1
            if not np.isnan(sal):
                pay[(cat, skill)][comp].append(sal)

    rows = []
    for (cat, skill), by_company in pay.items():
        salaried = sum(len(v) for v in by_company.values())
        if len(by_company) < MIN_COMPANIES or salaried < MIN_SALARIED:
            continue
        # one figure per company, then the median across companies
        per_company = [float(np.median(v)) for v in by_company.values()]
        med = float(np.median(per_company))
        rows.append({
            "job_family": cat,
            "skill_name": skill,
            "jobs_mentioning": seen[(cat, skill)],
            "companies": len(by_company),
            "jobs_with_salary": salaried,
            "median_salary": round(med),
            "salary_premium_pct": round(100 * (med - baseline[cat]) / baseline[cat], 1),
        })

    out = pd.DataFrame(rows).sort_values(["job_family", "salary_premium_pct"],
                                         ascending=[True, False])
    out.to_csv(OUT, index=False)

    print(f"\n{OUT.name}: {len(out)} skill and category pairs "
          f"with {MIN_COMPANIES}+ employers and {MIN_SALARIED}+ salaried postings")
    print("\nhighest paying skills overall:")
    print(out.nlargest(12, "salary_premium_pct").to_string(index=False))


if __name__ == "__main__":
    main()
