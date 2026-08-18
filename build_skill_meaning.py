"""Embed the skill descriptions, then use them to separate complements from
substitutes.

Co-occurrence tells you two skills appear in the same job ad. It cannot tell
you WHY. Docker with Kubernetes and PyTorch with TensorFlow both co-occur about
80 to 90 percent of the time, but one pair means "you need both" and the other
means "either will do". Descriptions can tell them apart, because two tools that
do the same job have near-identical descriptions while two tools used together
do not.

Run once from the terminal:
    python build_skill_meaning.py
"""

import re
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
DESCRIPTIONS = HERE / "skill_descriptions.csv"
COOC = HERE / "linkedin_cooccurrence.csv"
DEMAND = HERE / "linkedin_demand.csv"
OUT_VECTORS = HERE / "skill_meaning.npy"
OUT_NAMES = HERE / "skill_meaning_names.csv"
OUT_PAIRS = HERE / "skill_pairs.csv"

MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# above this, two skills describe the same kind of thing.
# Check the calibration table this script prints and adjust if the boundary
# lands somewhere you disagree with. There is no correct value.
SAME_KIND = 0.75
# co-occurrence values are mostly small, so there is no useful floor here.
# The app already shows only a skill's closest neighbours, so every pair in the
# file gets a label and the app decides which are close enough to display.


# who made a tool is not what it does, so both are removed before comparing
VENDORS = (r"\b(?:from |by )?(?:Amazon Web Services|Amazon|Google|Microsoft|Meta|"
           r"Apple|JetBrains|Atlassian|Apache|Oracle)\b")


def plain_text(name, text):
    """Strip the skill name and its vendor, leaving only what the thing does.

    "AWS is a cloud platform from Amazon" and "GCP is a cloud platform from
    Google" differ by four tokens that say who owns it, not what it is. Removing
    them makes two tools with the same function look the same, which is exactly
    the comparison we want.
    """
    t = re.sub(r"^" + re.escape(name) + r"\s+(?:is|are)\s+", "", text,
               flags=re.I)
    t = re.sub(VENDORS, " ", t, flags=re.I)
    return re.sub(r"\s+", " ", t).strip()


def encode(texts):
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(MODEL)
    return model.encode(list(texts), batch_size=64, show_progress_bar=True,
                        normalize_embeddings=True).astype("float32")


def classify(meaning_sim):
    """Label a pair from how alike the two descriptions are.

    Same kind of thing -> substitutes, learning the second adds little.
    Different kinds    -> complements, the second is genuinely worth learning.

    Whether a pair is close enough to be worth showing is decided by the
    co-occurrence score, which the app sorts on. Gating the label on
    co-occurrence too left 98 percent of pairs unlabelled and the app empty.
    """
    return "substitutes" if meaning_sim >= SAME_KIND else "complements"


def main():
    desc = pd.read_csv(DESCRIPTIONS).sort_values("skill_name").reset_index(drop=True)
    print(f"embedding {len(desc)} skill descriptions...")

    desc["plain"] = [plain_text(n, t)
                     for n, t in zip(desc.skill_name, desc.description)]
    vectors = encode(desc.plain)
    np.save(OUT_VECTORS, vectors)
    desc[["skill_name"]].to_csv(OUT_NAMES, index=False)

    # meaning similarity for every pair, from the descriptions
    meaning = vectors @ vectors.T
    index = {s: i for i, s in enumerate(desc.skill_name)}

    # co-occurrence association for every pair, from real job ads
    cooc = pd.read_csv(COOC)
    totals = pd.read_csv(DEMAND).groupby("skill_name").demand_count.sum()

    rows = []
    for a, b, count in zip(cooc.skill_a, cooc.skill_b, cooc["count"]):
        if a not in index or b not in index:
            continue
        size = np.sqrt(totals.get(a, 1) * totals.get(b, 1))
        assoc = count / size
        sim = float(meaning[index[a], index[b]])
        rows.append({"skill_a": a, "skill_b": b, "cooccur": round(assoc, 3),
                     "meaning": round(sim, 3),
                     "relation": classify(sim)})

    pairs = pd.DataFrame(rows).sort_values("cooccur", ascending=False)
    pairs.to_csv(OUT_PAIRS, index=False)

    print(f"\n{OUT_VECTORS.name}: {vectors.shape}")
    print(f"{OUT_PAIRS.name}: {len(pairs)} pairs classified")
    print()
    print(pairs.relation.value_counts().to_string())

    print("\n--- calibration: pairs whose answer we already know ---")
    print("    substitutes should score HIGH on meaning, complements LOW.")
    print("    If the boundary is wrong, change SAME_KIND at the top.\n")
    known = [("PyTorch", "TensorFlow"), ("PostgreSQL", "MySQL"), ("AWS", "GCP"),
             ("Azure", "GCP"), ("JSON", "XML"), ("Django", "Flask"),
             ("Docker", "Kubernetes"), ("NumPy", "Pandas"),
             ("Grafana", "Prometheus"), ("Terraform", "Ansible"),
             ("HTML", "JavaScript"), ("Confluence", "Jira")]
    for a, b in known:
        r = pairs[((pairs.skill_a == a) & (pairs.skill_b == b))
                  | ((pairs.skill_a == b) & (pairs.skill_b == a))]
        if r.empty:
            print(f"  {a:12s} + {b:14s} not in the co-occurrence data")
        else:
            r = r.iloc[0]
            print(f"  {a:12s} + {b:14s} cooccur {r.cooccur:.2f}  "
                  f"meaning {r.meaning:.2f}  -> {r.relation}")

    m = pairs.meaning
    print(f"\nmeaning scores among co-occurring pairs: "
          f"min {m.min():.2f}  median {m.median():.2f}  max {m.max():.2f}")

    print("\n--- strongest substitute pairs, learning both adds least ---")
    subs = pairs[pairs.relation == "substitutes"].nlargest(10, "meaning")
    print(subs[["skill_a", "skill_b", "cooccur", "meaning"]].to_string(index=False))

    print("\n--- strongest complement pairs, the second is worth learning ---")
    comps = pairs[pairs.relation == "complements"].nlargest(10, "cooccur")
    print(comps[["skill_a", "skill_b", "cooccur", "meaning"]].to_string(index=False))


if __name__ == "__main__":
    main()
