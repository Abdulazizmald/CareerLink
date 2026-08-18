"""Match free-text skill strings from LinkedIn onto our 141 known skill names."""

import difflib
import re

# short or ambiguous names that must match a whole comma-separated item exactly
STRICT = {"Go", "C#", "C++", "C", "R", "SAS", "SAP", "Git", "PHP", "Ruby", "Rust",
          "Excel", "Java", "Linux", "Bash", "Jira", "Oracle", "MCP", "ETL",
          "Redis", "Scala", "Swift", "Kotlin", "Django", "Flask", "Vue",
          "HTML", "CSS", "XML", "JSON", "Unix", "Hive", ".NET"}

# real skills the LinkedIn data has that the original 141 do not
EXTRA_SKILLS = [
    "HTML", "CSS", "Jenkins", "NoSQL", "R", ".NET", "Hadoop", "PowerShell",
    "Unix", "Windows", "XML", "JSON", "GitHub", "GitLab", "Confluence",
    "Splunk", "MATLAB", "Active Directory", "VMware", "Spring Boot", "jQuery",
    "Hive", "C", "DevOps", "Cybersecurity", "Unit Testing", "Data Analysis",
    "Data Warehousing", "Distributed Systems", "Software Architecture",
    "Data Governance", "Risk Management", "Firewalls", "Kanban", "Big Data",
]

ALIASES = {
    "golang": "Go",
    "k8s": "Kubernetes",
    "postgres": "PostgreSQL",
    "js": "JavaScript",
    "node": "Node.js",
    "nodejs": "Node.js",
    "ci cd": "CI/CD",
    "cicd": "CI/CD",
    "agile": "Agile / Scrum",
    "scrum": "Agile / Scrum",
    "agile scrum": "Agile / Scrum",
    "ab testing": "A/B Testing",
    "a b testing": "A/B Testing",
    "ml": "Machine Learning",
    "machine learning ml": "Machine Learning",
    "natural language processing": "NLP",
    "amazon web services": "AWS",
    "microsoft azure": "Azure",
    "google cloud platform": "GCP",
    "google cloud": "GCP",
    "microsoft excel": "Excel",
    "ms excel": "Excel",
    "powerbi": "Power BI",
    "generative ai": "LLMs / GenAI",
    "genai": "LLMs / GenAI",
    "llm": "LLMs / GenAI",
    "llms": "LLMs / GenAI",
    "large language models": "LLMs / GenAI",
    "sklearn": "scikit-learn",
    "scikit learn": "scikit-learn",
    "restful api": "REST API",
    "rest apis": "REST API",
    "pen testing": "Penetration Testing",
    "sql server": "SQL",
    "tsql": "SQL",
    # recovered from the vocab.csv diagnostic
    "agile development": "Agile / Scrum",
    "agile methodologies": "Agile / Scrum",
    "agile methodology": "Agile / Scrum",
    "agile practices": "Agile / Scrum",
    "continuous integration": "CI/CD",
    "continuous integration continuous deployment": "CI/CD",
    "rest": "REST API",
    "restful apis": "REST API",
    "c c++": "C++",
    "data pipelines": "Data Pipeline",
    "stakeholder management": "Stakeholder Mgmt",
    "html5": "HTML",
    "html css": "HTML",
    "cyber security": "Cybersecurity",
    "information security": "Cybersecurity",
    "nosql databases": "NoSQL",
    "data analytics": "Data Analysis",
    "dot net": ".NET",
    "microsoft sql server": "SQL",
}


def normalise(text):
    """Lowercase and strip punctuation so 'Agile / Scrum' meets 'agile/scrum'."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9+#.]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def build_lookup(skill_names):
    """Map normalised forms to canonical skill names."""
    lookup = {normalise(s): s for s in skill_names}
    for alias, target in ALIASES.items():
        if target in skill_names:
            lookup[normalise(alias)] = target

    # loose patterns for names safe to find inside a longer phrase
    loose = []
    for s in skill_names:
        if s in STRICT:
            continue
        n = normalise(s)
        if len(n) >= 5:
            loose.append((re.compile(r"(?<![a-z0-9])" + re.escape(n) + r"(?![a-z0-9])"), s))

    return lookup, loose


def resolve(query, lookup, loose):
    """Turn whatever the user typed into a known skill.

    Returns (skill_name, how) on success, or (None, suggestions) on failure.
    """
    n = normalise(query)
    if not n:
        return None, []

    if n in lookup:
        return lookup[n], "exact"

    for pattern, name in loose:
        if pattern.search(n):
            return name, "matched"

    close = difflib.get_close_matches(n, list(lookup), n=1, cutoff=0.75)
    if close:
        return lookup[close[0]], "did you mean"

    return None, "unknown"


def extract(text, lookup, loose):
    """Return the set of known skills mentioned in one free-text skills string."""
    found = set()
    for item in str(text).split(","):
        n = normalise(item)
        if not n:
            continue
        if n in lookup:
            found.add(lookup[n])
            continue
        for pattern, name in loose:
            if pattern.search(n):
                found.add(name)
    return found


def build_prose_patterns(skill_names, min_len=3):
    """Word-boundary patterns for finding skills inside running text.

    Names under min_len characters (Go, R, C) are skipped on purpose. In prose
    they match things like "Go to our careers page" far too often, and a false
    positive is worse here than a miss.
    """
    out = []
    for s in skill_names:
        n = normalise(s)
        if len(n) < min_len:
            continue
        out.append((re.compile(r"(?<![a-z0-9])" + re.escape(n) + r"(?![a-z0-9])", re.I), s))
    return out


def extract_from_prose(text, patterns):
    """Return the set of known skills mentioned anywhere in a block of text."""
    t = normalise(text)
    return {name for pattern, name in patterns if pattern.search(t)}
