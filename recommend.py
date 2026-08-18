"""Steps 2 and 3: the two recommendation models."""

import numpy as np
import pandas as pd

SCORE_INPUTS = {
    "demand": "demand_pct",
    "scarcity": "median_days_open",
    "pay": "salary_premium_pct",
}


def _minmax(s):
    lo, hi = s.min(), s.max()
    if hi == lo:
        return pd.Series(0.5, index=s.index)
    return (s - lo) / (hi - lo)


def rank_skills(df, category, weights, top_n=10):
    """Knowledge-based recommender: score every skill in one category."""
    sub = df[df["category"] == category].copy()

    for name, col in SCORE_INPUTS.items():
        sub[f"n_{name}"] = _minmax(sub[col])

    total = sum(weights.values())
    sub["raw_score"] = sum(weights[n] * sub[f"n_{n}"] for n in SCORE_INPUTS) / total

    # a row built on guessed values gets a small haircut
    sub["confidence"] = 1 - 0.1 * sub["imputed_fields"]
    sub["score"] = (sub["raw_score"] * sub["confidence"] * 100).round(1)

    return sub.sort_values("score", ascending=False).head(top_n)


def build_skill_vectors(df):
    """One row per skill, one column per category, value is demand_pct."""
    return df.pivot_table(index="skill_name", columns="category",
                          values="demand_pct").fillna(0)


def similar_by_cooccurrence(cooc, totals, skill, top_n=8):
    """Content-based recommender using how often skills share a job posting.

    Raw counts favour common skills, so each pair is divided by the size of
    both skills. That turns 'appears a lot' into 'appears together unusually
    often', which is the thing we actually want.
    """
    rows = cooc[(cooc.skill_a == skill) | (cooc.skill_b == skill)].copy()
    if rows.empty:
        return rows.assign(skill_name=None, association=None)

    rows["skill_name"] = np.where(rows.skill_a == skill, rows.skill_b, rows.skill_a)
    size = np.sqrt(totals.get(skill, 1) * rows.skill_name.map(totals).fillna(1))
    rows["association"] = (rows["count"] / size).round(3)

    return (rows.sort_values("association", ascending=False)
                .head(top_n)[["skill_name", "count", "association"]])


def _unit_matrix(vectors):
    """Standardise each column, then scale every row to length 1."""
    X = vectors.values.astype(float)
    X = (X - X.mean(axis=0)) / (X.std(axis=0) + 1e-9)
    return X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-9)


def similar_skills(vectors, skill, top_n=5):
    """Content-based recommender: cosine similarity between skill vectors."""
    X = _unit_matrix(vectors)
    i = vectors.index.get_loc(skill)
    sims = X @ X[i]

    out = pd.DataFrame({"skill_name": vectors.index, "similarity": sims.round(3)})
    return out.drop(index=i).sort_values("similarity", ascending=False).head(top_n)


def recommend_next(df, vectors, known, category, weights,
                   closeness=0.5, top_n=10, pool_size=25):
    """Hybrid: retrieve skills near what you know, rank them by market value."""
    X = _unit_matrix(vectors)

    # stage 1, retrieval: average what you know into one profile, find its neighbours
    rows = [vectors.index.get_loc(s) for s in known]
    profile = X[rows].mean(axis=0)
    profile = profile / (np.linalg.norm(profile) + 1e-9)

    sims = pd.Series(X @ profile, index=vectors.index).drop(index=known)
    pool = sims.nlargest(pool_size)

    # stage 2, ranking: value scores computed against the whole category
    scored = rank_skills(df, category, weights, top_n=len(df))
    out = scored[scored["skill_name"].isin(pool.index)].copy()
    if out.empty:
        return out

    out["similarity"] = out["skill_name"].map(pool)
    out["fit"] = (closeness * _minmax(out["similarity"])
                  + (1 - closeness) * _minmax(out["score"]))
    out["fit"] = (out["fit"] * 100).round(1)

    return out.sort_values("fit", ascending=False).head(top_n)


if __name__ == "__main__":
    from prep import load_and_aggregate

    data = load_and_aggregate("data.csv")
    w = {"demand": 1.0, "scarcity": 1.0, "pay": 1.0}

    cols = ["skill_name", "score", "demand_pct", "median_days_open",
            "salary_premium_pct", "imputed_fields"]
    for cat in ["devops", "ai", "security"]:
        print(f"\n--- top 5 for {cat} ---")
        print(rank_skills(data, cat, w, top_n=5)[cols].to_string(index=False))

    vecs = build_skill_vectors(data)
    print("\n--- similar to Terraform ---")
    print(similar_skills(vecs, "Terraform").to_string(index=False))

    # sanity check: does our score agree with the one already in the file?
    scored = rank_skills(data, "devops", w, top_n=999)
    print("\ncorrelation with the file's scarcity_score:",
          round(scored["score"].corr(scored["scarcity_score"]), 2))

def neighbours_for_known(cooc, totals, relations, known, pool=40, min_share=0.5):
    """Complements and substitutes for a WHOLE SET of skills at once.

    A candidate has to be associated with at least min_share of the skills you
    already know, and is ranked on how many of them it links to first, then on
    the mean strength of those links. Scoring on the single strongest link
    instead would let a skill that pairs with only one of your five to the top,
    which is not what "what should I learn next" means.

    Substitutes are exempt from min_share. If you know Tableau, Power BI is
    still worth skipping even though it duplicates only that one skill.
    """
    known = list(known)
    hits = {}

    for skill in known:
        rows = similar_by_cooccurrence(cooc, totals, skill, top_n=pool)
        if rows.empty or rows.skill_name.isna().all():
            continue
        for other, assoc in zip(rows.skill_name, rows.association):
            if other in known:
                continue
            rec = hits.setdefault(other, {"assoc": [], "relation": "unlabelled"})
            rec["assoc"].append(float(assoc))
            rel = relations.get((skill, other), ("unlabelled", None))[0]
            if rel == "substitutes":
                rec["relation"] = "substitutes"
            elif rec["relation"] == "unlabelled" and rel == "complements":
                rec["relation"] = "complements"

    need = max(1, int(np.ceil(min_share * len(known))))
    rows = []
    for name, rec in hits.items():
        links = len(rec["assoc"])
        if rec["relation"] != "substitutes" and links < need:
            continue
        rows.append({"skill_name": name,
                     "association": round(float(np.mean(rec["assoc"])), 3),
                     "linked_to": f"{links} of {len(known)}",
                     "links": links,
                     "relation": rec["relation"]})

    cols = ["skill_name", "association", "linked_to", "links", "relation"]
    if not rows:
        return pd.DataFrame(columns=cols)
    return (pd.DataFrame(rows)[cols]
            .sort_values(["links", "association"], ascending=False)
            .reset_index(drop=True))
