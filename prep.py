"""Step 1: turn 8 noisy daily snapshots into one stable table."""

import pandas as pd

FEATURES = ["demand_count", "demand_pct", "median_days_open",
            "salary_premium_pct", "repost_rate_pct", "scarcity_score"]

MIN_SNAPSHOTS = 3


def load_and_aggregate(path="data.csv"):
    df = pd.read_csv(path)

    # median across the 8 snapshots kills the day-to-day noise
    agg = df.groupby(["category", "skill_name"])[FEATURES].median()
    agg["n_snapshots"] = df.groupby(["category", "skill_name"]).size()
    agg = agg.reset_index()

    # drop rows we barely observed, they are guesses not measurements
    agg = agg[agg["n_snapshots"] >= MIN_SNAPSHOTS].copy()

    # remember which rows we had to guess at, before we fill them
    agg["imputed_fields"] = agg[["median_days_open", "salary_premium_pct"]].isna().sum(axis=1)

    # fill remaining gaps with the category median, not with zero
    for col in ["median_days_open", "salary_premium_pct"]:
        agg[col] = agg[col].fillna(agg.groupby("category")[col].transform("median"))
        agg[col] = agg[col].fillna(agg[col].median())

    return agg.reset_index(drop=True)


if __name__ == "__main__":
    clean = load_and_aggregate()
    print("rows:", len(clean))
    print("missing values left:\n", clean.isna().sum().to_string())
    print("\nKubernetes before vs after:")
    raw = pd.read_csv("data.csv")
    k = raw[(raw.skill_name == "Kubernetes") & (raw.category == "security")]
    print("raw daily scarcity scores:", k.scarcity_score.tolist())
    print(clean[clean.skill_name == "Kubernetes"].to_string(index=False))