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
    """Return (videos, error), cached by (query, n).

    Only a success is cached. learn.py already retries a transient 5xx a
    couple of times, but if Google's backend is still down after that, the
    failure is not remembered -- the next visitor who opens the same skill
    tries again fresh rather than replaying the same error for the rest of
    this process's life.
    """
    key = (query, n)
    if key in _video_cache:
        return _video_cache[key]
    result = learn.search_videos(query, config.YOUTUBE_API_KEY, n=n)
    if result[1] is None:
        _video_cache[key] = result
    return result


def books_for(query, n=1):
    """Return (books, error), cached by (query, n). See videos_for: only a
    success is cached, so a transient failure gets retried, not repeated."""
    key = (query, n)
    if key in _book_cache:
        return _book_cache[key]
    result = learn.search_books(query, config.GOOGLE_BOOKS_API_KEY, n=n)
    if result[1] is None:
        _book_cache[key] = result
    return result
