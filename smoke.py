"""Hit every route and every awkward input. No browser, no server.

The awkward cases are the point: a skill whose name contains a slash, a role with
one employer, a filter combination that matches nothing, a search with no hits,
and three names that do not exist. Those are what broke while this was written.
"""
from fastapi.testclient import TestClient

import main

client = TestClient(main.app)

OK = [
    "/",
    # the five tabs, each with and without a context query
    "/study", "/study?q=python+and+sql+i+build+dashboards",
    "/study?q=zzzznomatch", "/study?family=qa",
    "/study/data%20analyst", "/study/software%20engineer",
    "/hiring", "/hiring?q=run+our+kubernetes+platform", "/hiring?family=ai&sort=pay",
    "/jobs?q=kubernetes+platform&family=devops", "/jobs?dupes=1",
    "/skills?category=devops&skill=Kubernetes", "/skills?category=ai&skill=PyTorch",
    "/candidates?role=data%20analyst&top=5",
    "/candidates?q=aws+terraform&synthetic=1",
    "/candidates?q=zzzznomatch",
    "/roles/software%20engineer", "/roles/data%20analyst",
    "/roles/ddi%20network%20engineer",              # 177 postings, 1 employer, no pay
    "/roles/research%20scientist%20model%20engineer",   # 1 to 4 employers stated pay
    "/skills", "/skills?q=k8s", "/skills?q=zzzz",   # zzzz matches nothing
    "/skills/Kubernetes", "/skills/Tableau",        # Tableau is the substitute case
    "/skills/HTML",                                 # in postings, not in the 2026 index
    "/skills/Agile%20%2F%20Scrum", "/skills/CI%2FCD",   # slashes in the name
    "/skills/C%2B%2B", "/skills/Stakeholder%20Mgmt",
    "/jobs", "/jobs?family=devops&worksite=remote",
    "/jobs?worksite=hybrid&seniority=junior",
    "/jobs?family=ai&worksite=remote&seniority=principal",
    "/candidates", "/candidates?source=llm_generated", "/candidates?min_skills=10",
    "/candidates?category=CHEF", "/candidates?min_skills=99",   # matches nothing
    "/candidates/res-21297521", "/candidates/gpt-000",
]
NOT_FOUND = ["/roles/not-a-role", "/study/not-a-role", "/skills/NotASkill", "/candidates/nope"]

failed = []
for url in OK:
    r = client.get(url)
    if r.status_code != 200:
        failed.append((url, r.status_code))
    print(f"{r.status_code}  {len(r.text):>6}  {url}")

for url in NOT_FOUND:
    r = client.get(url)
    if r.status_code != 404:
        failed.append((url, r.status_code))
    print(f"{r.status_code}  {len(r.text):>6}  {url}")

# A suppressed pay figure must never reach a page as a bare blank. All three pay
# branches are checked, because they take different wording: nobody stated pay,
# one to four employers did, or five or more did.
none_stated = client.get("/roles/ddi%20network%20engineer").text
assert "fig-absent" in none_stated and "stated pay" in none_stated
assert "$" not in none_stated.split("Median pay")[1][:400], "a median leaked out"

thin = client.get("/roles/research%20scientist%20model%20engineer").text
assert "fig-absent" in thin and "stated pay" in thin
assert "1 employers" not in thin and "1 companies" not in thin, "plural is wrong at one"

enough = client.get("/roles/software%20engineer").text
assert "$" in enough, "a role with enough employers showed no pay"
print("\nall three pay branches render, and none leaks a suppressed median")

# the substitute split has to actually populate, or the strongest result is invisible
page = client.get("/skills/Tableau").text
assert "Power BI" in page, "Tableau's substitutes did not render"
print("complement and substitute split renders")

if failed:
    raise SystemExit(f"\nFAILED: {failed}")
print(f"\nall {len(OK) + len(NOT_FOUND)} routes returned the expected status")
