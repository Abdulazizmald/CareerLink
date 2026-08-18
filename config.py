import os
from pathlib import Path

HERE = Path(__file__).parent
SCARCITY_CSV = HERE / "skill-scarcity-index.csv"
LINKEDIN_POSTINGS = HERE / "linkedin_job_postings.csv"
LINKEDIN_SKILLS = HERE / "job_skills.csv"

# Real values live in api_keys.py (gitignored) so they never sit in a file this
# project would commit. Environment variables, if set, take priority over that
# file -- handy for anyone who prefers not to keep keys in a file at all.
#   PowerShell:  $env:YOUTUBE_API_KEY = "..."
try:
    from api_keys import YOUTUBE_API_KEY as _YOUTUBE_KEY, GOOGLE_BOOKS_API_KEY as _BOOKS_KEY
except ImportError:
    _YOUTUBE_KEY = _BOOKS_KEY = ""

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY") or _YOUTUBE_KEY
GOOGLE_BOOKS_API_KEY = os.environ.get("GOOGLE_BOOKS_API_KEY") or _BOOKS_KEY