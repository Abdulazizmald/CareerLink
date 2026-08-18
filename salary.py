"""Pull salary ranges and seniority out of job description text."""

import re

import numpy as np

HOURS_PER_YEAR = 2080
MONTHS = 12
PLAUSIBLE = (20_000, 800_000)

NUM = r"(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"

# $120,000 - $150,000   |   $120K-$150K   |   $60.00 to $75.00
RANGE = re.compile(
    r"\$\s*" + NUM + r"\s*([kK])?\s*(?:-|–|—|to|through)\s*\$?\s*" + NUM + r"\s*([kK])?",
    re.I)
SINGLE = re.compile(r"\$\s*" + NUM + r"\s*([kK])?", re.I)

HOURLY = re.compile(r"\b(?:per|an|/|hourly rate of)\s*hour|\bhourly\b|\b/\s*hr\b|\bper hr\b", re.I)
MONTHLY = re.compile(r"\bper month\b|\bmonthly\b|\b/\s*month\b", re.I)
# money that is not a salary
# a number is only a salary if a pay word sits near it
PAY_CONTEXT = re.compile(r"salary|compensation|\bpay\b|\bpaid\b|\bwage\b|"
                         r"base (?:range|rate)?|hiring range|pay range|"
                         r"per (?:year|hour|month|annum)|annual(?:ly|ized)?|"
                         r"hourly|\bhr\b|\bote\b|earn(?:s|ing)?|"
                         r"\brange (?:is|of|for)|\brate\b", re.I)

# scale words mean this is not a wage: "$608 million raised"
SCALE = re.compile(r"^\s*(?:million|billion|mm\b|bn\b|m\b|b\b)", re.I)

NOT_PAY = re.compile(r"\bbonus\b|\bsign.?on\b|\bsigning\b|\brelocation\b|\breferral\b|"
                     r"\bstipend\b|\btuition\b|\breimburse|\brevenue\b|\bbudget\b|"
                     r"\bportfolio\b|\bsavings\b|\bcontract value\b|\braise[ds]?\b|"
                     r"\bfunding\b|\bvaluation\b|\bseries [a-e]\b|"
                     r"\bmarket cap\b|assets under management|\baum\b|"
                     r"\binvest(?:ed|ment)?\b|\bacquisition\b|\bgrant\b|"
                     r"\bscholarship\b|\bdonat|\bprize\b|\bsavings of\b|"
                     r"\bcost savings\b|\bbudget of\b|\bendowment\b", re.I)

SENIORITY = [
    ("principal", r"\bprincipal\b|\bdistinguished\b|\bfellow\b|\bstaff\b"),
    ("lead", r"\blead\b|\bmanager\b|\bhead of\b|\bdirector\b|\bvp\b|\bchief\b"),
    ("senior", r"\bsenior\b|\bsr\.?\b|\biii\b|\biv\b"),
    ("junior", r"\bjunior\b|\bjr\.?\b|\bentry.?level\b|\bgraduate\b|\bintern\b|"
               r"\bassociate\b|\bapprentice\b|\bi{1,2}\b"),
]

# years of experience, read from the description rather than the title
YEARS = re.compile(r"(\d{1,2})\s*\+?\s*(?:-|–|to)?\s*(?:\d{1,2})?\s*years?"
                   r"(?:\s+of)?(?:\s+\w+){0,3}\s+experience", re.I)


def _number(raw, k_flag):
    value = float(raw.replace(",", ""))
    if k_flag:
        value *= 1000
    return value


def extract_salary(text):
    """Return (low, high) as annual figures, or (None, None) if unclear."""
    text = str(text)
    hit = RANGE.search(text)

    if hit:
        low = _number(hit.group(1), hit.group(2))
        high = _number(hit.group(3), hit.group(4))
    else:
        singles = SINGLE.findall(text)
        if len(singles) != 1:
            return None, None
        low = high = _number(singles[0][0], singles[0][1])

    if low > high:
        low, high = high, low

    # look near the match for a rate period, not across the whole document
    start = hit.start() if hit else 0
    end = hit.end() if hit else 60
    window = text[max(0, start - 55):end + 16]

    if NOT_PAY.search(window):
        return None, None

    # "$608 million" is not a wage
    tail = text[end:end + 14]
    if SCALE.match(tail):
        return None, None

    # a bare number with no pay word near it is not a salary
    if not PAY_CONTEXT.search(text[max(0, start - 90):end + 45]):
        return None, None

    if HOURLY.search(window) or high < 200:
        low, high = low * HOURS_PER_YEAR, high * HOURS_PER_YEAR
    elif MONTHLY.search(window):
        low, high = low * MONTHS, high * MONTHS

    if not (PLAUSIBLE[0] <= low <= PLAUSIBLE[1] and PLAUSIBLE[0] <= high <= PLAUSIBLE[1]):
        return None, None
    return low, high


def detect_seniority(title, text=""):
    """Seniority from the job title. Falls back to years of experience.

    Deliberately does NOT scan the description for words like 'lead' or
    'manager', because job ads are full of phrases like 'lead a team' and
    'reports to the manager' that have nothing to do with the role's level.
    """
    title = str(title)

    # a junior word at the START of a title wins. This keeps "Associate Product
    # Manager" junior while leaving "Senior Associate Analyst" senior.
    if re.match(r"\s*(?:junior|jr\.?|associate|entry.?level|graduate|intern|apprentice)\b",
                title, re.I):
        return "junior"

    for label, pattern in SENIORITY:
        if re.search(pattern, title, re.I):
            return label

    hit = YEARS.search(str(text)[:1500])
    if hit:
        years = int(hit.group(1))
        if years >= 7:
            return "senior"
        if years >= 3:
            return "mid"
        return "junior"

    return "unspecified"


def midpoint(low, high):
    if low is None:
        return np.nan
    return (low + high) / 2
