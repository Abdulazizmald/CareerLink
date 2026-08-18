"""Search by context, over text this project already has.

Why TF-IDF and not sentence embeddings. The embedding route needs torch, a
sentence-transformer model, and an 86 MB vector file whose row order must stay in
lockstep with tech_jobs.csv. None of that is available here, and waiting for it
was blocking five tabs. TF-IDF over the same text needs scikit-learn and nothing
else, indexes in under a second, and answers a typed description well enough to
be useful.

What it costs. TF-IDF matches words, not meaning. "k8s" will not find a role whose
description says "Kubernetes" unless the alias appears in the text too. Embeddings
would. That is a real limitation and the pages say so, rather than implying the
search understands you.

Two mitigations that close most of the gap:
  - sublinear_tf, so a description repeating "engineer" nine times does not swamp
    a description that says it once
  - the project's own skill vocabulary is appended to each document, so a role
    whose postings ask for Kubernetes is findable by that word even when the one
    representative posting never used it

Everything here returns indices and scores. It never touches a DataFrame column
that a page displays, so swapping the backend for embeddings later means changing
this file and nothing else.
"""

import re

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from matcher import ALIASES

MIN_SCORE = 0.02          # below this the match is noise, not a weak match


def _expand_aliases(text):
    """Add the canonical name whenever an alias appears, and the reverse.

    A typed query saying "k8s" and a description saying "Kubernetes" share no
    token, so one of them has to carry both. Doing it on the query side is
    cheaper: one string instead of 437.
    """
    low = text.lower()
    extra = [target for alias, target in ALIASES.items()
             if re.search(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])", low)]
    extra += [alias for alias, target in ALIASES.items()
              if re.search(r"(?<![a-z0-9])" + re.escape(target.lower()) + r"(?![a-z0-9])", low)]
    return text + " " + " ".join(extra) if extra else text


class Index:
    """A fitted TF-IDF index over one set of documents.

    Built once at import and reused. Fitting on 437 roles takes milliseconds and
    on 2,670 resumes well under a second, so there is nothing to cache beyond
    keeping the object alive.
    """

    def __init__(self, documents, min_df=1, ngram=(1, 2)):
        self.vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=ngram,
            min_df=min_df,
            max_df=0.85,          # a word in 85% of documents separates nothing
            sublinear_tf=True,    # log-scaled counts, so repetition stops shouting
            strip_accents="unicode",
        )
        self.matrix = self.vectorizer.fit_transform(documents)
        # rows are L2-normalised by TfidfVectorizer, so a dot product is cosine
        self.n = self.matrix.shape[0]

    def search(self, query, top_n=25, subset=None):
        """Return [(row_index, score)] for the closest documents.

        subset is a boolean mask, applied BEFORE ranking rather than after, so
        asking for the top 10 inside a filter returns ten results and not
        whatever survives the filter out of a global top ten.
        """
        query = (query or "").strip()
        if not query:
            return []
        q = self.vectorizer.transform([_expand_aliases(query)])
        if q.nnz == 0:
            return []                     # no word in the query is in the vocabulary

        scores = (self.matrix @ q.T).toarray().ravel()
        if subset is not None:
            scores = np.where(np.asarray(subset, dtype=bool), scores, -1.0)

        order = np.argsort(-scores)[:top_n]
        return [(int(i), float(scores[i])) for i in order if scores[i] >= MIN_SCORE]

    def vocabulary_size(self):
        return len(self.vectorizer.vocabulary_)


def role_documents(roles, role_skills):
    """One document per role: its label, its example title, its representative
    posting, and every skill its postings actually asked for.

    The skills matter more than they look. The description is one posting out of
    thousands, so it mentions whatever that employer happened to write. The skill
    list is aggregated across all of them, which makes the document describe the
    role rather than one advert for it.
    """
    by_role = role_skills.groupby("role").skill_name.apply(lambda s: " ".join(s))
    parts = []
    for r in roles.itertuples():
        skills = by_role.get(r.role, "")
        parts.append(" ".join([
            str(r.role_label), str(r.role), str(r.example_title),
            str(r.job_family), skills, skills,      # skills twice: they are the signal
            str(r.description),
        ]))
    return parts


def candidate_documents(candidates):
    """One document per candidate: the resume, plus its extracted skills twice.

    Same reasoning. A resume describes work in prose and rarely names tools, so
    the extracted skill list is the part a recruiter's query will actually hit.
    """
    return [f"{s} {s} {t}" for s, t in
            zip(candidates.skills.fillna(""), candidates.resume_text.fillna(""))]
