"""Turn the two resume datasets into one candidate pool the app can load.

Two sources, kept distinguishable on purpose:

  Resume.csv      2,484 real resumes, 24 coarse life-sector categories, long
                  prose. Its employer names are already redacted to "Company
                  Name", but the redaction leaked, so contact details are
                  scrubbed here rather than at display time.
  gpt_dataset.csv 400 rows but only 188 distinct, 8 tech role categories,
                  short LLM-written prose.

The two 'category' columns are NOT the same kind of label, so they are not
reconciled. A category only means something alongside the 'source' column. The
synthetic rows are dense in skill names because a model wrote a skill list, so
any evaluation has to be reported per source or it will flatter itself.

Run once from the terminal:
    python build_candidates.py
"""

import re
from pathlib import Path

import numpy as np
import pandas as pd

from matcher import EXTRA_SKILLS, build_prose_patterns, extract_from_prose
from taxonomy import base_role, classify, role_label

HERE = Path(__file__).parent
RESUMES = HERE / "Resume.csv"
GPT = HERE / "gpt_dataset.csv"
SCARCITY_CSV = HERE / "skill-scarcity-index.csv"
OUT = HERE / "candidates.csv"

# the leaks the source's own redaction missed
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}")
PROFILE = re.compile(r"(?:https?://)?(?:www\.)?(?:linkedin|github)\.com/\S*", re.I)


def scrub(text):
    """Remove contact details, leaving a marker so the edit is auditable."""
    t = PROFILE.sub("[profile removed]", str(text))
    t = EMAIL.sub("[email removed]", t)
    return PHONE.sub("[phone removed]", t)


def reflow(text):
    """Recover line breaks from the source's runs of spaces.

    Resume.csv was converted from HTML, and section breaks survived as runs of
    three or more spaces rather than as newlines. Collapsing all whitespace would
    give one unreadable paragraph, so long runs become line breaks instead. This
    matters because the resume is displayed, not just matched on. The synthetic
    rows have no such runs, so this leaves them untouched.
    """
    t = re.sub(r" {3,}", "\n", str(text))
    t = re.sub(r"[ \t]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n", t).strip()


# ---------------------------------------------------------------- extraction
# Every field below was measured against the real file before being added. The
# coverage numbers are printed at the end of the run, because a recruiter column
# that is 89% dashes is worse than no column: it looks like an absent candidate
# rather than an absent field.

DEGREES = [                      # highest first, first match wins
    ("PhD", r"\b(ph\.?\s?d|doctorate|doctoral)\b"),
    ("Master's", r"\b(master'?s?|m\.?s\.?c?\b|m\.?eng\b|m\.?tech\b|m\.?b\.?a\b|mba)\b"),
    ("Bachelor's", r"\b(bachelor'?s?|b\.?s\.?c?\b|b\.?a\.?\b|b\.?eng\b|b\.?tech\b)\b"),
    ("Associate", r"\b(associate'?s? degree|a\.?a\.?s?\b)\b"),
    ("Diploma", r"\b(diploma|certificate program)\b"),
]

# A GPA is only a GPA with a number attached. "GPA available on request" is not.
GPA = re.compile(r"\bG\.?P\.?A\.?\b[^0-9\n]{0,12}([0-4](?:\.\d{1,2})?)\b"
                 r"|\b([0-4]\.\d{1,2})\s*/\s*4(?:\.0{1,2})?\b", re.I)

YEARS = re.compile(r"\b(\d{1,2})\s*\+?\s*years?(?:\s+of)?"
                   r"(?:\s+\w+){0,3}\s+experience\b", re.I)

# a major only counts when it follows a degree word, or "in Computer Science"
# matches half the sentences in a resume
# "Bachelor of Science in Computer Science" has two "in/of" clauses and only the
# second one is the major. Matching the first returns "Science", which is the
# degree type, not the subject. So the qualifier is consumed explicitly when
# present, and a bare Science/Arts/Engineering capture is rejected outright.
DEGREE_HEAD = r"\b(?:bachelor'?s?|master'?s?|b\.?s\.?c?|m\.?s\.?c?|b\.?a\.?|ph\.?d)\b"
QUALIFIER = r"(?:\s*(?:of|in)\s+(?:science|arts|engineering|technology|business administration))?"
MAJOR = re.compile(DEGREE_HEAD + QUALIFIER + r"\s*(?:in|,)\s+"
                   r"([A-Z][A-Za-z]+(?:\s+(?:and\s+)?[A-Z][A-Za-z]+){0,3})", re.I)
NOT_A_MAJOR = {"science", "arts", "engineering", "technology", "business administration",
               "the", "a", "an", "general studies", "progress", "candidate"}

# "University"/"College" alone is not a name, same reasoning as NOT_A_MAJOR: a
# bare institution type says nothing a recruiter can check.
COLLEGE = re.compile(
    r"\b((?:[A-Z][A-Za-z.&'-]+\s+){0,4}"
    r"(?:University|College|Institute of Technology|Polytechnic)"
    r"(?:\s+of\s+(?:[A-Z][A-Za-z.&'-]+\s*){1,3})?)\b")
NOT_A_COLLEGE = {"university", "college", "institute of technology", "polytechnic"}


def degree(text):
    for name, pattern in DEGREES:
        if re.search(pattern, text, re.I):
            return name
    return ""


def gpa(text):
    m = GPA.search(text)
    if not m:
        return ""
    v = m.group(1) or m.group(2)
    # a 4.0-scale GPA below 1.0 is almost always a version number or a typo
    return v if v and 1.0 <= float(v) <= 4.0 else ""


def years(text):
    """The LARGEST stated figure, not the first.

    A resume says "3 years of Python experience" in one bullet and "10 years of
    experience in IT" in the summary. The first match is whichever appears
    earlier, which is arbitrary. The largest is the closest thing to a career
    total that this text supports.
    """
    found = [int(m) for m in YEARS.findall(text) if int(m) <= 50]
    return max(found) if found else ""


def major(text):
    for m in MAJOR.finditer(text):
        found = re.sub(r"\s+", " ", m.group(1).strip())
        if found.lower() not in NOT_A_MAJOR and len(found) > 2:
            return found
    return ""


def college(text):
    for m in COLLEGE.finditer(text):
        found = re.sub(r"\s+", " ", m.group(1).strip())
        if found.lower() not in NOT_A_COLLEGE and len(found) > 2:
            return found
    return ""


# Section headers some resumes lead with instead of a title. Skipped rather
# than read as the job itself: "WORKING" is not a title, it's the start of a
# "WORKING EXPERIENCE" header that landed on its own line.
GENERIC_OPENERS = {
    "working", "work", "objective", "summary", "profile", "experience",
    "work experience", "professional summary", "career objective",
    "qualifications", "skills", "resume", "curriculum vitae", "cv", "about",
    "about me", "personal statement",
}


def first_line(text):
    """The resume's opening line, which in this dataset is usually the job
    title. Falls through a generic header word to the next line, since that
    is the real title in that case rather than the section header above it.
    """
    for line in str(text).split("\n")[:4]:
        line = line.strip()
        if line and line.lower() not in GENERIC_OPENERS and len(line) > 3:
            return line[:90]
    return str(text).split("\n")[0][:90]


def inferred_role(text):
    """The role from the resume's first line.

    This dataset puts the job title on line one, so base_role turns
    "SENIOR INFORMATION TECHNOLOGY MANAGER" into a role comparable with the ones
    in roles.csv. Seniority is stripped by base_role, which is what makes it
    comparable at all.
    """
    r = base_role(first_line(text))
    return role_label(r) if r else ""


def load_real():
    df = pd.read_csv(RESUMES)
    # Resume_html is 39 MB of the 56 MB and holds nothing the text does not
    df = df.drop(columns=["Resume_html"])
    print(f"{len(df):,} real resumes read")
    print(f"  contact details scrubbed: "
          f"{df.Resume_str.str.contains(EMAIL).sum()} emails, "
          f"{df.Resume_str.str.contains(PHONE).sum()} phone numbers, "
          f"{df.Resume_str.str.contains(PROFILE).sum()} profile links")
    return pd.DataFrame({
        # the id carries the source, so provenance survives even if a later
        # step loses the source column
        "candidate_id": "res-" + df.ID.astype(str),
        "source": "resume_dataset",
        "category": df.Category,
        "resume_text": df.Resume_str,
    })


def load_synthetic():
    df = pd.read_csv(GPT)
    print(f"{len(df):,} synthetic resumes read, {df.Resume.nunique()} distinct")
    return pd.DataFrame({
        "candidate_id": ["gpt-%03d" % i for i in range(len(df))],
        "source": "llm_generated",
        "category": df.Category,
        "resume_text": df.Resume,
    })


def main():
    pool = pd.concat([load_real(), load_synthetic()], ignore_index=True)
    pool["resume_text"] = pool.resume_text.map(scrub).map(reflow)

    # the SAME vocabulary as build_roles.py, or a candidate's skills and a role's
    # skills would be drawn from two different lists and could not be compared
    patterns = build_prose_patterns(
        sorted(set(pd.read_csv(SCARCITY_CSV).skill_name) | set(EXTRA_SKILLS)))
    found = [sorted(extract_from_prose(t, patterns)) for t in pool.resume_text]
    pool["n_skills"] = [len(f) for f in found]
    pool["skills"] = [", ".join(f) for f in found]

    print("\nextracting recruiter fields from the resume text...")
    text = pool.resume_text.fillna("")
    pool["degree"] = text.map(degree)
    pool["gpa"] = text.map(gpa)
    pool["years_experience"] = text.map(years)
    pool["major"] = text.map(major)
    pool["college"] = text.map(college)
    # The synthetic profiles open with marketing prose, not a job title, so
    # base_role turns them into nonsense like "Dynamic Cloud Engineer With A
    # Passion For". Their category IS their role, so use it and skip the guess.
    pool["inferred_role"] = np.where(pool.source == "llm_generated",
                                     pool.category, text.map(inferred_role))

    # only tech candidates: the job data is entirely technical, so a chef resume
    # can never be a real match and only dilutes every result.
    pool["is_tech"] = (
        pool.category.isin(["INFORMATION-TECHNOLOGY", "ENGINEERING"])
        | (pool.source == "llm_generated")
        # A resume filed under something else, but whose own first-line title the
        # taxonomy reads as technical, still belongs in the pool.
        #
        # classify() gets the RAW line, not inferred_role. base_role applies
        # ROLE_ALIAS, which maps "development" to "developer", so
        # "Business Development Manager" becomes "business developer manager" and
        # then matches the engineering pattern on the word "developer". That put
        # 30 business development resumes into the tech pool. The raw title has no
        # such word, so classifying it is correct and the alias stays useful for
        # its actual job of merging role spellings.
        | classify(text.map(first_line)).notna())

    before = len(pool)
    pool = (pool.drop_duplicates(subset=["resume_text"])
            .reset_index(drop=True)[["candidate_id", "source", "category",
                                     "is_tech", "inferred_role", "degree",
                                     "major", "college", "gpa", "years_experience",
                                     "n_skills", "skills", "resume_text"]])
    print(f"\n{before - len(pool)} duplicate resumes dropped")
    pool.to_csv(OUT, index=False)

    print(f"{OUT.name}: {len(pool):,} candidates, "
          f"{OUT.stat().st_size / 1024**2:.1f} MB")
    print("\nby source:")
    print(pool.groupby("source").agg(
        candidates=("candidate_id", "size"),
        median_chars=("resume_text", lambda s: int(s.str.len().median())),
        mean_skills=("n_skills", "mean"),
        no_skills=("n_skills", lambda s: int((s == 0).sum()))).round(1).to_string())

    print("\nskills found per candidate, by category:")
    print(pool.groupby(["source", "category"]).n_skills
          .agg(["size", "mean", "max"]).round(1).to_string())

    print("\nmost common skills across the pool:")
    flat = pool.skills.str.split(", ").explode()
    print(flat[flat != ""].value_counts().head(15).to_string())

    print("\nrecruiter field coverage. Anything low here is a column that will be")
    print("mostly blank on the page, which is stated there rather than hidden:")
    tech = pool[pool.is_tech]
    for col in ["inferred_role", "degree", "major", "college", "gpa", "years_experience"]:
        have_all = (pool[col].astype(str) != "").mean()
        have_tech = (tech[col].astype(str) != "").mean()
        print(f"  {col:18s} all {100*have_all:5.1f}%   tech pool {100*have_tech:5.1f}%")

    print(f"\ntech pool: {len(tech):,} of {len(pool):,} "
          f"({(tech.source=='llm_generated').sum()} synthetic, "
          f"{(tech.source=='resume_dataset').sum()} real)")
    print("\nmost common inferred roles in the tech pool:")
    ir = tech.inferred_role[tech.inferred_role.astype(str) != ""]
    print(ir.value_counts().head(10).to_string())


if __name__ == "__main__":
    main()
