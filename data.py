"""Every table the website reads, loaded once at import.

This is the replacement for Streamlit's st.cache_data, and it is simpler than
caching. Streamlit reran the whole script on every click, so it needed a cache to
avoid rereading 15 MB of CSV per interaction. FastAPI starts once and serves many
requests from the same process, so the tables are just loaded at import and read
from memory afterwards. No decorators, no cache keys, no invalidation.

The cost is that a data change needs a server restart. That is the right trade
for a read-only site over files that are rebuilt by hand.

Nothing here touches the vector files. Role and job search by meaning needs
role_vectors.npy and job_vectors.npy, which go in as a separate step.
"""

from pathlib import Path

import pandas as pd

import context
from matcher import ALIASES, EXTRA_SKILLS, build_prose_patterns
from prep import load_and_aggregate
from taxonomy import classify

HERE = Path(__file__).parent
SCARCITY_CSV = HERE / "skill-scarcity-index.csv"
DEMAND_CSV = HERE / "linkedin_demand.csv"
COOC_CSV = HERE / "linkedin_cooccurrence.csv"
PAY_CSV = HERE / "linkedin_salary.csv"
PAIRS_CSV = HERE / "skill_pairs.csv"
DESC_CSV = HERE / "skill_descriptions.csv"
ROLES_CSV = HERE / "roles.csv"
ROLE_SKILLS_CSV = HERE / "role_skills.csv"
JOBS_CSV = HERE / "jobs_enriched.csv"
CANDIDATES_CSV = HERE / "candidates.csv"
CERTS_CSV = HERE / "certifications.csv"

# a median pay built on fewer employers than this is not a measurement
MIN_PAY_EMPLOYERS = 5

# labels that are debris rather than roles: a stray slash, a requisition number,
# or nothing at all. This replaces the base_role(r) == r test the Streamlit app
# used. That test was a proxy for "junk label" and the proxy broke when base_role
# gained its alias list: it started dropping 73 real roles such as
# "system administrator" and "qa engineer" purely because base_role now renames
# them. Testing for the junk directly says what is meant and cannot rot that way.
JUNK_ROLE = r"^/|\s/|/$|#\s*\d|^\s*$"


def _load_roles():
    """Roles, with the three display-time filters from the Streamlit app applied.

    Applied here rather than per route, so no page can show a role the filters
    were meant to hide. roles.csv predates the current taxonomy, so the
    classify() recheck still removes retail supervisors filed under engineering.
    Once roles.csv is rebuilt these filters stop removing anything, which is the
    point: they follow taxonomy.py rather than a stale file.
    """
    roles = pd.read_csv(ROLES_CSV)
    skills = pd.read_csv(ROLE_SKILLS_CSV)

    keep = (classify(roles.example_title).notna()          # not misfiled
            & roles.role.isin(set(skills.role))            # has skills to show
            & ~roles.role.str.contains(JUNK_ROLE, regex=True))
    roles = roles[keep].reset_index(drop=True)

    # Pay is blanked at load, not at display. A figure quoted by two employers is
    # not a median, and suppressing it in one place means it cannot leak out of
    # another. thin_pay is kept so a page can explain the blank.
    roles["thin_pay"] = roles.salary_companies < MIN_PAY_EMPLOYERS
    roles.loc[roles.thin_pay, "median_salary"] = pd.NA
    return roles, skills


def _load_relations():
    """Complement and substitute labels, keyed both ways so lookup is direction free."""
    pairs = pd.read_csv(PAIRS_CSV)
    out = {}
    for a, b, rel, mean in zip(pairs.skill_a, pairs.skill_b,
                               pairs.relation, pairs.meaning):
        out[(a, b)] = out[(b, a)] = (rel, mean)
    return out


def _skill_labels(names):
    """Display label per skill, with up to three aliases folded in.

    Aliases are not separate entries. Keeping them in the label means the list is
    one row per skill while someone typing "k8s" still finds Kubernetes, because
    a filter runs over the whole label.
    """
    aliases = {}
    for alias, target in ALIASES.items():
        if target in names and alias.lower() != target.lower():
            aliases.setdefault(target, []).append(alias)
    return {n: (f"{n} ({', '.join(aliases[n][:3])})" if n in aliases else n)
            for n in names}


scarcity = load_and_aggregate(SCARCITY_CSV)
demand = pd.read_csv(DEMAND_CSV)
cooc = pd.read_csv(COOC_CSV)
pay = pd.read_csv(PAY_CSV)
jobs = pd.read_csv(JOBS_CSV)
# keep_default_na=False on the extracted text columns: an empty cell means "this
# resume did not state it", and reading that as NaN puts the literal string "nan"
# into a recruiter's summary line.
candidates = pd.read_csv(CANDIDATES_CSV, keep_default_na=False,
                         na_values=[], dtype=str)
for _num in ("n_skills",):
    candidates[_num] = pd.to_numeric(candidates[_num], errors="coerce").fillna(0).astype(int)
candidates["is_tech"] = candidates.is_tech.isin(["True", "true", "1"])

# Hand-checked, not generated. Certification programmes change often, so the file
# carries a status column and the pages show it: Microsoft retired or is retiring
# four of these during 2026, and displaying a dead credential as current would be
# worse than showing none.
certs = pd.read_csv(CERTS_CSV) if CERTS_CSV.exists() else pd.DataFrame(
    columns=["job_family", "name", "provider", "level", "focus", "status"])

roles, role_skills = _load_roles()
relations = _load_relations()
descriptions = dict(pd.read_csv(DESC_CSV).itertuples(index=False, name=None))

# demand per skill across all families, the denominator for co-occurrence
totals = demand.groupby("skill_name").demand_count.sum()

vocab = sorted(set(scarcity.skill_name) | set(demand.skill_name) | set(EXTRA_SKILLS))
skill_labels = _skill_labels(vocab)
prose_patterns = build_prose_patterns(vocab)

# Only technical candidates. The job data is entirely technical, so a chef resume
# can never be a real match and only dilutes every ranking.
tech_candidates = (candidates[candidates.is_tech].reset_index(drop=True)
                   if "is_tech" in candidates else candidates)

# Context search indexes, fitted once at import. Roles take milliseconds and
# candidates well under a second, so there is nothing to cache beyond keeping
# these objects alive for the life of the process.
role_index = context.Index(context.role_documents(roles, role_skills))
candidate_index = context.Index(context.candidate_documents(tech_candidates))

categories = sorted(scarcity.category.unique())
families = sorted(demand.job_family.unique())


def summary():
    """What got loaded, printed at startup so a silent bad file is visible."""
    return (f"{len(scarcity)} scarcity rows, {len(demand)} demand rows, "
            f"{len(cooc):,} skill pairs, {len(roles)} roles, "
            f"{len(jobs):,} postings, {len(candidates):,} candidates, "
            f"{len(vocab)} skills, {len(certs)} certifications, "
            f"{len(tech_candidates):,} tech candidates, "
            f"role vocab {role_index.vocabulary_size():,}")


if __name__ == "__main__":
    print(summary())
    print(f"\nroles showing pay: {int(roles.median_salary.notna().sum())}, "
          f"suppressed for a thin employer sample: {int(roles.thin_pay.sum())}")
    print(f"candidates by source:\n{candidates.groupby('source').size().to_string()}")
    print(f"\nfamilies: {families}")
    print(f"categories: {categories}")
