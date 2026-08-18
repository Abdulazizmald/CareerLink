"""Encode tech job descriptions once, offline, so the app can search by meaning.

Run from the terminal, not from Streamlit:
    python build_embeddings.py

Needs:  pip install sentence-transformers
"""

from pathlib import Path

import numpy as np
import pandas as pd

from taxonomy import classify

HERE = Path(__file__).parent
SUMMARIES = HERE / "job_summary.csv"
POSTINGS = HERE / "linkedin_job_postings.csv"
OUT_JOBS = HERE / "tech_jobs.csv"
OUT_VECTORS = HERE / "job_vectors.npy"

MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK = 50_000
MAX_CHARS = 2000
# MiniLM-L6 is small and truncates at 256 tokens, so memory is not the constraint
# on any recent GPU. On an integrated GPU the memory is shared with the CPU, so a
# large batch competes with the rest of the machine rather than sitting in its own
# pool. 256 is still safe; drop it if the machine starts swapping.
BATCH_GPU = 256
BATCH_CPU = 64


def classify_titles():
    """Map each posting to a job family, using the shared taxonomy."""
    df = pd.read_csv(POSTINGS, usecols=["job_link", "job_title"], low_memory=False)
    df["family"] = classify(df.job_title)
    tech = df.dropna(subset=["family"])
    print("tech postings by job family:")
    print(tech.family.value_counts().to_string())
    return dict(zip(tech.job_link, tech.family))


def collect_summaries(link_to_cat):
    """Stream the big summaries file, keep only tech postings."""
    kept = []
    scanned = 0
    for chunk in pd.read_csv(SUMMARIES, chunksize=CHUNK):
        chunk = chunk[chunk.job_link.isin(link_to_cat)]
        kept.append(chunk)
        scanned += CHUNK
        print(f"  scanned ~{scanned:,} rows", end="\r")
    print()

    jobs = pd.concat(kept, ignore_index=True)
    jobs["job_family"] = jobs.job_link.map(link_to_cat)
    jobs["job_summary"] = jobs.job_summary.fillna("").str.slice(0, MAX_CHARS)
    return jobs[jobs.job_summary.str.len() > 50].reset_index(drop=True)


def add_titles(jobs):
    titles = pd.read_csv(POSTINGS,
                         usecols=["job_link", "job_title", "company", "job_location"],
                         low_memory=False)
    return jobs.merge(titles, on="job_link", how="left")


def encode(texts):
    """Encode on the GPU when torch can see one, otherwise on the CPU.

    SentenceTransformer already picks a GPU on its own, but silently. An
    unsupported card or a CPU-only torch wheel falls back without saying so, and
    the only symptom is a run that takes much longer than it should. So the device
    is printed.

    torch.cuda covers AMD too. PyTorch's ROCm builds expose themselves through the
    same torch.cuda API and the same "cuda" device string, so this needs no vendor
    branch. What it cannot tell you is that an integrated GPU shares system memory
    with the CPU, so the speedup over CPU for a model this small is modest.
    """
    import torch
    from sentence_transformers import SentenceTransformer

    if torch.cuda.is_available():
        device, batch = "cuda", BATCH_GPU
        print(f"encoding on GPU: {torch.cuda.get_device_name(0)}")
    else:
        device, batch = "cpu", BATCH_CPU
        print("encoding on CPU, torch reports no usable GPU")

    model = SentenceTransformer(MODEL, device=device)
    return model.encode(list(texts), batch_size=batch, show_progress_bar=True,
                        normalize_embeddings=True).astype("float32")


def main():
    link_to_cat = classify_titles()

    jobs = collect_summaries(link_to_cat)
    jobs = add_titles(jobs)
    print(f"tech jobs with a usable description: {len(jobs):,}")
    print(jobs.job_family.value_counts().to_string())

    vectors = encode(jobs.job_summary)
    np.save(OUT_VECTORS, vectors)
    jobs.to_csv(OUT_JOBS, index=False)

    print(f"\n{OUT_JOBS.name}: {len(jobs):,} rows")
    print(f"{OUT_VECTORS.name}: {vectors.shape}, "
          f"{vectors.nbytes / 1024**2:.0f} MB")


if __name__ == "__main__":
    main()
