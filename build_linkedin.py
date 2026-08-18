"""Turn the 1.3M LinkedIn files into two small CSVs the app can load.

Run this once from the terminal, not from Streamlit:
    python build_linkedin.py
"""

from collections import Counter
from itertools import combinations
from pathlib import Path

import pandas as pd

from matcher import build_lookup, extract, normalise, EXTRA_SKILLS
from taxonomy import classify

HERE = Path(__file__).parent
SCARCITY_CSV = HERE / "skill-scarcity-index.csv"
POSTINGS = HERE / "linkedin_job_postings.csv"
SKILLS = HERE / "job_skills.csv"
OUT_DEMAND = HERE / "linkedin_demand.csv"
OUT_COOC = HERE / "linkedin_cooccurrence.csv"
OUT_VOCAB = HERE / "vocab.csv"

CHUNK = 200_000
MIN_PAIR_COUNT = 5
VOCAB_SIZE = 3000

def classify_titles():
    """Map each posting to a job family, using the shared taxonomy."""
    df = pd.read_csv(POSTINGS, usecols=["job_link", "job_title"], low_memory=False)
    df["family"] = classify(df.job_title)

    tech = df.dropna(subset=["family"])
    print("tech postings by job family:")
    print(tech.family.value_counts().to_string())
    return dict(zip(tech.job_link, tech.family))


def scan_skills(link_to_cat, lookup, loose):
    """Stream the skills file, count skills per category, pairs, and raw vocabulary."""
    per_category = Counter()      # (category, skill) -> postings
    postings_seen = Counter()     # category -> postings with at least one match
    pairs = Counter()             # (skill_a, skill_b) -> postings
    vocab = Counter()             # every raw skill string, matched or not
    rows_read = Counter()         # category -> postings present in the skills file

    total = 0
    for chunk in pd.read_csv(SKILLS, chunksize=CHUNK):
        chunk = chunk[chunk.job_link.isin(link_to_cat)]
        for link, text in zip(chunk.job_link, chunk.job_skills):
            cat = link_to_cat[link]
            rows_read[cat] += 1

            for item in str(text).split(","):
                n = normalise(item)
                if n:
                    vocab[n] += 1

            found = extract(text, lookup, loose)
            if not found:
                continue
            postings_seen[cat] += 1
            for skill in found:
                per_category[(cat, skill)] += 1
            for a, b in combinations(sorted(found), 2):
                pairs[(a, b)] += 1
        total += len(chunk)
        print(f"  scanned {total:,} tech postings", end="\r")

    print()
    return per_category, postings_seen, pairs, vocab, rows_read


def main():
    known = sorted(set(pd.read_csv(SCARCITY_CSV).skill_name) | set(EXTRA_SKILLS))
    lookup, loose = build_lookup(known)

    link_to_cat = classify_titles()
    per_category, postings_seen, pairs, vocab, rows_read = scan_skills(
        link_to_cat, lookup, loose)

    demand = pd.DataFrame(
        [{"job_family": c, "skill_name": s, "demand_count": n,
          "demand_pct": round(100 * n / postings_seen[c], 2)}
         for (c, s), n in per_category.items()]
    ).sort_values(["job_family", "demand_count"], ascending=[True, False])
    demand.to_csv(OUT_DEMAND, index=False)

    cooc = pd.DataFrame(
        [{"skill_a": a, "skill_b": b, "count": n}
         for (a, b), n in pairs.items() if n >= MIN_PAIR_COUNT]
    ).sort_values("count", ascending=False)
    cooc.to_csv(OUT_COOC, index=False)

    # every raw skill string, flagged for whether our matcher recognises it
    matched = {normalise(k) for k in lookup}
    v = pd.DataFrame(vocab.most_common(VOCAB_SIZE), columns=["skill", "count"])
    v["known"] = v.skill.isin(matched)
    v.to_csv(OUT_VOCAB, index=False)

    print(f"\n{OUT_DEMAND.name}: {len(demand)} skill and category pairs")
    print(f"{OUT_COOC.name}: {len(cooc)} skill pairs")
    print(f"{OUT_VOCAB.name}: {len(vocab):,} distinct strings, top {len(v)} saved")

    print("\nmatch rate per category:")
    rate = pd.DataFrame({"postings": pd.Series(rows_read),
                         "matched": pd.Series(postings_seen)})
    rate["pct"] = (100 * rate.matched / rate.postings).round(1)
    print(rate.to_string())

    print("\ntop pairs:")
    print(cooc.head(10).to_string(index=False))

    print("\ntop unmatched strings, these are your missing aliases:")
    print(v[~v.known].head(25).to_string(index=False))


if __name__ == "__main__":
    main()
