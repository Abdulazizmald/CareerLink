"""Collapse messy posting titles into canonical job titles.

58,954 postings carry 26,459 distinct title strings, because a posting title is
advertising copy, not a job name: "Senior Data Analyst (Remote) - Urgent!" and
"Data Analyst II" are the same job. This strips the parts that describe the
level, the contract, or the ad, and keeps the part that describes the work.
"""

import re

from taxonomy import CLEARANCE

# LEVEL words describe how senior the role is, not what the role does.
# Stripping them is the whole point: seniority is already a separate column,
# so keeping it in the title would show the same job three times.
LEVEL = (r"\b(?:senior|sr|snr|junior|jr|lead|principal|staff|distinguished|"
         r"associate|assoc|entry.?level|graduate|grad|intern|trainee|"
         r"apprentice|experienced|mid.?level|entry)\b")
LEVEL_NUM = r"\b(?:level|lvl|grade)\s*\d+\b|\b(?:i{1,3}|iv|v)\b|\b[1-5]\b"

# NOISE describes the advert, not the job.
NOISE = (r"\b(?:remote|hybrid|onsite|on.?site|wfh|contract|contractor|c2c|w2|"
         r"full.?time|part.?time|permanent|perm|temp|temporary|freelance|"
         r"urgent|urgently|hiring|immediate|immediately|apply now|"
         r"opening|opportunity|position|vacancy|needed|wanted|required|"
         r"usa|united states|h1b|opt|cpt|clearance|ts.?sci|top secret|"
         r"public trust|per year|per annum)\b")

# spelling variants that mean the same job
ALIAS = [
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


def clean_title(raw):
    """Return the canonical form of one posting title, or '' if nothing is left."""
    t = str(raw).lower()
    # "with security clearance" is a background check, not a job. Left in, it
    # invents a title called "software engineer with security".
    t = re.sub(r"\bwith\s+" + CLEARANCE, " ", t)
    t = re.sub(CLEARANCE, " ", t)
    t = re.sub(r"\(.*?\)|\[.*?\]|\{.*?\}", " ", t)   # drop bracketed asides
    t = re.split(r"\s[-–—|•]\s|\s{2,}", t)[0]        # keep the head phrase only
    t = re.sub(r"[^a-z0-9+#/&,.\s-]", " ", t)
    t = re.sub(NOISE, " ", t)
    t = re.sub(LEVEL, " ", t)
    t = re.sub(LEVEL_NUM, " ", t)
    for pattern, repl in ALIAS:
        t = re.sub(pattern, repl, t)
    t = re.sub(r"\s*,\s*", ", ", t)                  # tidy commas, do not split
    t = re.sub(r"[\s\-.]+", " ", t).strip(" ,-")
    return t


def display_title(clean):
    """Title case for the interface, with a few acronyms left upper."""
    upper = {"it", "qa", "ux", "ui", "ai", "ml", "sre", "erp", "crm", "sap",
             "aws", "api", "etl", "bi", "hris", "sql", "hr", "iam", "soc"}
    return " ".join(w.upper() if w in upper else w.capitalize()
                    for w in clean.split())

