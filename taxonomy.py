"""How job titles map to job families.

This lives in one file on purpose. Three scripts and the app all need the same
classification, and three copies of these regexes would drift apart.

Note this is a SEPARATE taxonomy from the 2026 scarcity index, which has its
own six categories. Job postings are classified into job families here. The two
meet at the skill level, not the category level, because a job family and a
scarcity-index category are not the same kind of thing.
"""

import re

# "with security clearance" describes a background check, not a job function
CLEARANCE = r"(?:with |requires |active )?(?:ts.?sci|top secret|secret)? ?security clearance"
# physical security roles, never technical
GUARD = (r"security (?:officer|guard|supervisor|shift|specialist technician)|"
         r"unarmed|armed security|patrol|loss prevention")

# titles that are clearly not technical, checked before anything else
NOT_TECH = (r"\bnurse\b|\brn\b|\blpn\b|\bcna\b|physician|clinician|clinical|"
            r"pharmac|dental|veterinar|therapist|caregiver|"
            r"\bchef\b|\bcook\b|server|barista|housekeep|janitor|custodian|"
            r"\bdriver\b|\bcdl\b|forklift|warehouse associate|"
            r"teacher|professor|tutor|childcare|"
            r"welder|machinist|plumber|electrician|hvac|carpenter|"
            r"insurance agent|real estate|loan officer|tax preparer")

# order matters, first match wins, so narrow rules go above broad ones
FAMILIES = [
    ("security", r"security engineer|security analyst|security architect|infosec|"
                 r"cyber|penetration test|threat|soc analyst|security operations|"
                 r"vulnerability|incident response"),
    ("ai", r"machine learning|\bml engineer|\bai engineer|deep learning|"
           r"data scientist|\bnlp\b|computer vision|research scientist"),
    ("devops", r"devops|site reliability|\bsre\b|platform engineer|"
               r"infrastructure engineer|cloud engineer|systems engineer|"
               r"automation engineer|release engineer"),
    ("data", r"data engineer|data analyst|data architect|analytics engineer|\betl\b|"
             r"business intelligence|\bbi\b(?! ?directional)|data warehouse"),
    # "dba" alone also means "doing business as", which matched company names
    ("database", r"database admin|database engineer|database developer|"
                 r"database architect|\bdba admin|\bsql dba\b|oracle dba"),
    ("network_infra", r"network engineer|network admin|network architect|"
                      r"systems admin|sysadmin|system administrator|"
                      r"virtualization|cloud architect"),
    ("it_support", r"help desk|helpdesk|desktop support|technical support|"
                   r"\bit support\b|it technician|service desk|it specialist|"
                   r"\bit analyst\b"),
    # bare "quality assurance" is mostly manufacturing and pharma, not software
    ("qa", r"\bsdet\b|test engineer|test automation|automation tester|"
           r"software tester|\bqa engineer|\bqa analyst|\bqa automation|"
           r"quality assurance (?:engineer|analyst|automation|developer)"),
    ("product", r"product manager|product owner|product analyst|scrum master|"
                r"business analyst|technical program manager"),
    ("design_ux", r"\bux\b|user experience|user research|product designer|"
                  r"\bui designer|interaction designer|web designer"),
    # bare "front end" and "back end" also describe retail and warehouse roles,
    # so they only count when attached to a technical noun
    ("engineering", r"software engineer|software developer|developer|programmer|"
                    r"full.?stack|software architect|solutions architect|"
                    r"(?:front|back).?end (?:developer|engineer|dev\b|web)|"
                    r"embedded|firmware|mobile engineer|ios developer|"
                    r"android developer|game developer|web developer"),
]

FAMILY_LABELS = {
    "engineering": "Software engineering",
    "data": "Data and analytics",
    "ai": "AI and machine learning",
    "devops": "DevOps and platform",
    "security": "Cybersecurity",
    "product": "Product and business analysis",
    "database": "Database administration",
    "network_infra": "Network and systems",
    "it_support": "IT support",
    "qa": "Quality assurance",
    "design_ux": "Design and UX",
}


def clean_title(series):
    """Strip clearance boilerplate so the real role shows through."""
    t = series.str.lower().fillna("")
    t = t.str.replace(CLEARANCE, " ", regex=True)
    return t.str.replace(r"\b(?:ts.?sci|poly|clearance)\b", " ", regex=True)


def classify(titles):
    """Return a Series of job family names, or None where nothing matched."""
    clean = clean_title(titles)
    blocked = clean.str.contains(GUARD, regex=True) | clean.str.contains(NOT_TECH, regex=True)

    out = clean.copy()
    out[:] = None
    for name, pattern in FAMILIES:
        unset = out.isna()
        out[unset & ~blocked & clean.str.contains(pattern, regex=True)] = name
    return out


def label(family):
    return FAMILY_LABELS.get(family, family)


# ---------------------------------------------------------------- worksite
# Only phrasings that describe a working arrangement. A bare "remote" is not
# enough, because IT postings are full of remote desktop, remote access and
# remote monitoring, none of which say anything about where you sit.
REMOTE = (r"fully remote|100%? remote|remote position|remote role|remote job|"
          r"remote opportunit|remote work|work remotely|remote.first|"
          r"work from home|\bwfh\b|telecommut|virtual/remote|"
          r"anywhere in the (?:us|u\.s\.|united states)|location: remote")
HYBRID = (r"\bhybrid\b|\d\s*days? (?:per week )?(?:in|at) (?:the )?office|"
          r"partially remote|flexible.{0,12}(?:office|onsite|on.site)")
ONSITE = (r"\bon.?site\b|in.office|in the office|relocation (?:is )?required|"
          r"must (?:be able to )?(?:work|report) (?:on.?site|in person)")

TITLE_REMOTE = r"\bremote\b|\bvirtual\b|work from home|\bwfh\b|telecommut"
TITLE_NOT_LOCATION = r"remote (?:desktop|access|monitoring|sensing|hands|management)"


def detect_worksite(title, text=""):
    """Return 'remote', 'hybrid' or 'onsite'.

    On-site is the default when nothing is stated. That is an assumption, not a
    measurement: a posting that says nothing is being counted as on-site.
    """
    title = str(title)
    body = str(text)[:3000]

    if re.search(HYBRID, title, re.I) or re.search(HYBRID, body, re.I):
        return "hybrid"

    if re.search(TITLE_REMOTE, title, re.I) and not re.search(
            TITLE_NOT_LOCATION, title, re.I):
        return "remote"

    if re.search(REMOTE, body, re.I):
        return "remote"

    return "onsite"


def worksite_is_stated(title, text=""):
    """True when the posting actually says something, so you can report coverage."""
    blob = f"{title} {str(text)[:3000]}"
    return bool(re.search(HYBRID, blob, re.I) or re.search(REMOTE, blob, re.I)
                or re.search(ONSITE, blob, re.I)
                or re.search(TITLE_REMOTE, str(title), re.I))


# ---------------------------------------------------------------- base role
# Seniority words, so "Senior Data Analyst" and "Data Analyst II" collapse to
# the same role. Level is captured separately by salary.detect_seniority.
LEVEL = (r"\b(?:senior|sr\.?|junior|jr\.?|lead|principal|staff|associate|"
         r"entry.?level|graduate|intern|apprentice|mid.?level|distinguished|"
         r"fellow|experienced|i{1,3}|iv|v|[1-5])\b")

# things that describe the posting rather than the role
NOISE = (r"\bwith security clearance\b|\bts.?sci\b|\bclearance\b|\bremote\b|"
         r"\bhybrid\b|\bon.?site\b|\bfull.?time\b|\bpart.?time\b|\bcontract(?:or)?\b|"
         r"\bw2\b|\bc2c\b|\bh1b\b|\bnew grad\b|\burgent\b|\bhiring\b|\bopening\b|"
         r"\bimmediate\b|\btemp\b|\bpermanent\b|\bfte\b|\b\d{4,}\b|"
         # a store or requisition number is not part of the role. "# 20" was
         # surviving and creating a role called "business analyst # 20", because
         # LEVEL only strips single digits 1 to 5 and NOISE only stripped runs
         # of 4 or more. "c#" is safe: the hash there is not followed by digits
         # and not standing alone.
         r"#\s*\d+|\b\d+\b|(?<![a-z0-9])#(?![a-z0-9])")

# spelling variants that mean the same role. Absorbed from titles.py, which
# built job_titles.csv, a second role table that nothing reads. Without these,
# "software engineering", "software engineers" and "software engineer" are three
# roles, and "front end" and "frontend" are two.
ROLE_ALIAS = [
    (r"\bengineer\w+\b", "engineer"),          # engineering, engineers
    (r"\bdevelop(?:er|ers|ment)\b", "developer"),
    (r"\banalyst\w+\b", "analyst"),
    (r"\bsystem\b", "systems"),
    (r"\badmin\b", "administrator"),
    (r"\bsw\b", "software"),
    (r"\bqa\b", "quality assurance"),
    (r"\bui ?/ ?ux\b", "ux"),
    (r"\bfront ?end\b", "frontend"),
    (r"\bback ?end\b", "backend"),
    (r"\bfull ?stack\b", "fullstack"),
]

# a base role has to say more than this to be worth grouping on
TOO_GENERIC = {"manager", "engineer", "analyst", "developer", "specialist",
               "consultant", "architect", "administrator", "technician",
               "coordinator", "supervisor", "director", "scientist", "designer",
               "programmer", "tester", "support", "operations", "it", "",
               # surfaced once ROLE_ALIAS started merging labels together
               "work", "team", "technical", "frontend", "backend", "fullstack"}


def base_role(title):
    """Strip seniority and posting noise, leaving the role itself.

    "Senior Cybersecurity Analyst" and "Cyber Security Analyst II" both become
    a comparable base role, so a search returns one row per kind of job rather
    than the same job once per seniority level.
    Returns None when nothing meaningful survives.
    """
    t = str(title).lower()
    t = re.sub(r"\(.*?\)|\[.*?\]|\{.*?\}", " ", t)        # bracketed extras
    t = re.split(r" - | – | at | \| |, |/ ", t)[0]        # company and location tails
    t = re.sub(NOISE, " ", t)
    t = re.sub(LEVEL, " ", t)
    t = re.sub(r"[^a-z0-9+#/ ]", " ", t)
    for pattern, repl in ROLE_ALIAS:
        t = re.sub(pattern, repl, t)

    # A slash left touching whitespace or an end is debris from stripping a level
    # word, not part of the role: "Senior/Staff Backend Engineer" becomes
    # "/ backend engineer" and "Publishing Systems Engineer I/II/III" becomes
    # "publishing systems engineer / /". A slash inside a token is left alone,
    # so "ui/ux" survives.
    t = re.sub(r"(?:^|(?<=\s))/|/(?=\s|$)", " ", t)
    t = re.sub(r"\s+", " ", t).strip()

    if t in TOO_GENERIC or len(t) < 4:
        return None
    return t


ACRONYMS = {"it", "qa", "ui", "ux", "ai", "ml", "sre", "dba", "erp", "crm",
            "api", "sql", "aws", "gcp", "etl", "bi", "soc", "sap", "nlp", "hris"}
SPELLINGS = {"devops": "DevOps", "javascript": "JavaScript", "ios": "iOS",
             "sysadmin": "SysAdmin", "fullstack": "FullStack",
             "postgresql": "PostgreSQL", "mysql": "MySQL", "nodejs": "Node.js",
             "dotnet": ".NET", "salesforce": "Salesforce", "sharepoint": "SharePoint"}


def role_label(role):
    """Title case for display, keeping acronyms and known spellings intact."""
    out = []
    for w in str(role).split():
        if w in SPELLINGS:
            out.append(SPELLINGS[w])
        elif w in ACRONYMS:
            out.append(w.upper())
        else:
            out.append(w.capitalize())
    return " ".join(out)

