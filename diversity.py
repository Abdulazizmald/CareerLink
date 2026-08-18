"""Diversity re-ranking, shared by the skill and job recommenders.

Ranking purely by relevance returns near-duplicates: 25 security jobs, or
TensorFlow recommended to someone who already knows PyTorch. Maximal Marginal
Relevance fixes this by scoring each candidate on how good it is MINUS how
similar it already is to what has been picked.
"""

import numpy as np


def mmr(relevance, similarity, balance=0.7, top_n=10):
    """Pick top_n indices trading relevance against redundancy.

    relevance:  1d array, higher is better
    similarity: square matrix, similarity[i, j] is how alike candidates i and j are
    balance:    1.0 is pure relevance, 0.0 is pure diversity
    """
    relevance = np.asarray(relevance, dtype=float)
    n = len(relevance)
    top_n = min(top_n, n)

    # scale relevance to 0..1 so it is comparable with similarity
    lo, hi = relevance.min(), relevance.max()
    rel = (relevance - lo) / (hi - lo) if hi > lo else np.full(n, 0.5)

    chosen = [int(np.argmax(rel))]
    remaining = set(range(n)) - set(chosen)

    while len(chosen) < top_n and remaining:
        idx = list(remaining)
        redundancy = similarity[np.ix_(idx, chosen)].max(axis=1)
        score = balance * rel[idx] - (1 - balance) * redundancy
        pick = idx[int(np.argmax(score))]
        chosen.append(pick)
        remaining.discard(pick)

    return chosen


def skill_similarity_matrix(skills, cooc, totals):
    """Association between every pair of skills, for use as the similarity input."""
    index = {s: i for i, s in enumerate(skills)}
    m = np.zeros((len(skills), len(skills)))

    rel = cooc[cooc.skill_a.isin(index) & cooc.skill_b.isin(index)]
    for a, b, count in zip(rel.skill_a, rel.skill_b, rel["count"]):
        size = np.sqrt(totals.get(a, 1) * totals.get(b, 1))
        i, j = index[a], index[b]
        m[i, j] = m[j, i] = count / size

    np.fill_diagonal(m, 1.0)
    return m
