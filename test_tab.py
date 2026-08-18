"""Runs the data lookups the Study guide tab performs, without Streamlit.

Streamlit is not installed here, so this copies the tab's data logic rather
than importing app.py. It checks the things that actually break: a skill that
is missing from one of the two sources, a role with no stated pay, and the
stale-role filter.
"""

import pandas as pd

from prep import load_and_aggregate
from recommend import similar_by_cooccurrence
from taxonomy import classify

scarcity = load_and_aggregate("skill-scarcity-index.csv")
linkedin = pd.read_csv("linkedin_demand.csv")
cooc = pd.read_csv("linkedin_cooccurrence.csv")
totals = linkedin.groupby("skill_name").demand_count.sum()
desc = pd.read_csv("skill_descriptions.csv")
descriptions = dict(zip(desc.skill_name, desc.description))
families = sorted(linkedin.job_family.unique())

pairs = pd.read_csv("skill_pairs.csv")
relations = {}
for a, b, rel, mean in zip(pairs.skill_a, pairs.skill_b, pairs.relation,
                           pairs.meaning):
    relations[(a, b)] = relations[(b, a)] = (rel, mean)

# ------------------------------------------------------------- role filter
roles = pd.read_csv("roles.csv")
before = len(roles)
role_skills = pd.read_csv("role_skills.csv")
roles = roles[classify(roles.example_title).notna()]
roles = roles[roles.role.isin(set(role_skills.role))].reset_index(drop=True)
print(f"roles: {before} -> {len(roles)} after dropping stale and skill-less ones")
# the exact number removed depends on which build produced roles.csv, so the
# properties are asserted instead of the count. base_role now clears slash debris
# and merges spelling variants, so junk labels must not appear at all.
assert before - len(roles) > 0, "the filter removed nothing, check roles.csv"
junk = roles.role[roles.role.str.contains(r"^/|\s/|/$|#\s*\d")]
assert junk.empty, (f"junk role labels in roles.csv: {list(junk)[:5]}. "
                    "If base_role was just patched, roles.csv is stale. "
                    "Rerun build_roles.py.")
retail = roles[(roles.job_family == "engineering")
               & roles.role.str.contains("supervisor")]
assert retail.empty, f"retail roles filed under engineering: {list(retail.role)[:5]}"
assert roles.role_label.is_unique, "two roles share a display label"

# ------------------------------------------------------------ skill branch
# HTML is an EXTRA_SKILL: it is in the postings but not in the 2026 index, so
# it is the case that breaks a naive .iloc[0]
for skill in ["Kubernetes", "HTML", "Stakeholder Mgmt", "C++"]:
    s_rows = scarcity[scarcity.skill_name == skill]
    j_rows = linkedin[linkedin.skill_name == skill]

    if s_rows.empty:
        days = premium = "not measured"
    else:
        days = f"{s_rows.median_days_open.median():.0f}"
        premium = f"{s_rows.salary_premium_pct.median():+.1f}%"

    near = similar_by_cooccurrence(cooc, totals, skill, top_n=40)
    partners = []
    if not near.empty and not near.skill_name.isna().all():
        for other in near.skill_name:
            if relations.get((skill, other), ("", None))[0] == "complements":
                partners.append(other)
            if len(partners) == 5:
                break

    print(f"\n{skill}")
    print(f"  description: {'yes' if skill in descriptions else 'MISSING'}")
    print(f"  days {days}, premium {premium}, "
          f"{j_rows.job_family.nunique()} of {len(families)} families")
    print(f"  learn alongside: {partners or 'none found'}")
    assert len(partners) <= 5

# ------------------------------------------------------------- role branch
no_pay = roles[roles.median_salary.isna()]
print(f"\nroles with no stated median pay: {len(no_pay)} of {len(roles)}")

picks = ["software engineer", "data analyst", roles.nsmallest(1, "postings").role.iat[0]]
if len(no_pay):
    picks.append(no_pay.role.iat[0])

for role in picks:
    row = roles[roles.role == role].iloc[0]
    rs = role_skills[role_skills.role == role]
    partners = list(rs.nlargest(6, "share_pct").skill_name)
    pay = ("not stated" if pd.isna(row.median_salary)
           else f"${row.median_salary:,.0f}")
    print(f"\n{row.role_label}  ({row.job_family})")
    print(f"  {row.postings:,} postings, {row.companies:,} employers, pay {pay}, "
          f"{row.pct_senior_or_above:.0f}% senior+")
    print(f"  example: {row.example_title} at {row.example_company}")
    print(f"  description chars: {len(str(row.description))}")
    print(f"  skills: {partners}")
    assert len(str(row.description)) > 100, "description too short to show"
    assert 0 < len(partners) <= 6

# every role must have skills, or section 3 is empty in the live app
missing = set(roles.role) - set(role_skills.role)
print(f"\nroles with no skills row at all: {len(missing)}")
assert not missing, sorted(missing)[:5]

print("\nall tab data checks passed")
