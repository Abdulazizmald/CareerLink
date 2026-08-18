"""Search jobs by meaning, and roll the results up into skill suggestions."""

from pathlib import Path

import numpy as np
import pandas as pd

from diversity import mmr

HERE = Path(__file__).parent
MODEL = "sentence-transformers/all-MiniLM-L6-v2"

_model = None


def get_model():
    """Load the encoder once and reuse it."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL)
    return _model


def load_index(jobs_path=HERE / "tech_jobs.csv",
               vectors_path=HERE / "job_vectors.npy"):
    jobs = pd.read_csv(jobs_path)
    vectors = np.load(vectors_path)
    return jobs, vectors


def search_jobs(query, jobs, vectors, category=None, top_n=10, encoder=None,
                balance=1.0, pool=None, filter_col="job_family"):
    """Return the jobs whose descriptions are closest in meaning to the query.

    balance below 1.0 turns on diversity re-ranking, so the results are not
    twenty near-identical postings.
    """
    encode = encoder or (lambda t: get_model().encode(
        [t], normalize_embeddings=True).astype("float32")[0])
    q = encode(query)

    mask = np.ones(len(jobs), dtype=bool)
    if category:
        mask = (jobs[filter_col] == category).values
    if not mask.any():
        return jobs.iloc[:0].assign(relevance=[])

    scores = vectors[mask] @ q

    if balance >= 1.0:
        idx = np.argsort(-scores)[:top_n]
    else:
        # take a wider pool on relevance, then re-rank it for variety
        pool = pool or min(len(scores), top_n * 8)
        cand = np.argsort(-scores)[:pool]
        sim = vectors[mask][cand] @ vectors[mask][cand].T
        picked = mmr(scores[cand], sim, balance=balance, top_n=top_n)
        idx = cand[picked]

    out = jobs[mask].iloc[idx].copy()
    out["relevance"] = scores[idx].round(3)
    return out


def skills_in_results(results, cooc_skills, lookup, loose, extract, top_n=12):
    """Count which known skills appear in the matched job descriptions."""
    counts = {}
    for text in results.job_summary:
        for skill in extract(text, lookup, loose):
            counts[skill] = counts.get(skill, 0) + 1

    if not counts:
        return pd.DataFrame(columns=["skill_name", "jobs", "share_pct"])

    out = pd.DataFrame(sorted(counts.items(), key=lambda x: -x[1]),
                       columns=["skill_name", "jobs"])
    out["share_pct"] = (100 * out.jobs / len(results)).round(1)
    return out.head(top_n)
