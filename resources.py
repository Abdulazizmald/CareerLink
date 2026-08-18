"""Cached access to learn.py's video and book search, for the live site.

learn.py talks to real, quota-limited APIs. A study guide page can trigger the
same query many times over — every visitor who opens a given skill's dropdown
asks the same question — so results are kept in memory for the life of the
process instead of being re-fetched. A plain dict is enough here, the same
reasoning data.py gives for loading tables once at import: this is one
long-running FastAPI process, not many short-lived ones.
"""

import config
import learn

_video_cache = {}
_book_cache = {}


def videos_for(query, n=1):
    """Return (videos, error), cached by (query, n)."""
    key = (query, n)
    if key not in _video_cache:
        _video_cache[key] = learn.search_videos(query, config.YOUTUBE_API_KEY, n=n)
    return _video_cache[key]


def books_for(query, n=1):
    """Return (books, error), cached by (query, n)."""
    key = (query, n)
    if key not in _book_cache:
        _book_cache[key] = learn.search_books(query, config.GOOGLE_BOOKS_API_KEY, n=n)
    return _book_cache[key]
