"""Fetch learning material for a skill or a job role from two public APIs.

Kept free of Streamlit on purpose, so it can be run and checked from the
terminal without launching a browser. The app wraps these in st.cache_data,
because Streamlit reruns the whole script on every click and an uncached call
here would spend real API quota every time a slider moves.

Both functions return (results, error). An empty list with an error string is
different from an empty list with no error: the first means the call failed,
the second means the API answered and had nothing. The app says which.
"""

import time
from urllib.parse import quote_plus

import requests

YOUTUBE_URL = "https://www.googleapis.com/youtube/v3/search"
BOOKS_URL = "https://www.googleapis.com/books/v1/volumes"
TIMEOUT = 8
RETRIES = 2            # extra attempts after the first, for 5xx only
BACKOFF = 0.6           # seconds, multiplied by attempt number


def _get(url, params):
    """GET with a short retry for a 5xx.

    Google's own APIs answer with a transient 503 ("backendFailed") often
    enough that a first failure should not be treated as final: a 4xx means
    the request itself is wrong (bad key, bad quota) and retrying changes
    nothing, but a 5xx means Google's side had a hiccup, and it usually
    clears within a second or two.
    """
    last = None
    for attempt in range(RETRIES + 1):
        try:
            last = requests.get(url, params=params, timeout=TIMEOUT)
        except requests.RequestException as e:
            return None, e
        if last.status_code < 500 or attempt == RETRIES:
            return last, None
        time.sleep(BACKOFF * (attempt + 1))
    return last, None


def youtube_search_link(query):
    """A plain YouTube search page. No key, no quota, never empty."""
    return "https://www.youtube.com/results?search_query=" + quote_plus(query)


def search_videos(query, api_key, n=3):
    """Return (videos, error). Each video is title, channel, url.

    videoEmbeddable=true matters: some videos forbid playback outside YouTube
    and st.video would show an empty box for those.
    """
    if not api_key:
        return [], "no API key set"

    params = {"key": api_key, "q": query, "part": "snippet", "type": "video",
              "maxResults": n, "videoEmbeddable": "true",
              "relevanceLanguage": "en", "safeSearch": "moderate"}
    r, err = _get(YOUTUBE_URL, params)
    if err:
        return [], f"could not reach YouTube: {err}"

    if r.status_code != 200:
        # YouTube names the cause in the body. quotaExceeded and keyInvalid are
        # both 403 but need different fixes, so pass the reason through instead
        # of guessing from the status code.
        try:
            reason = r.json()["error"]["errors"][0]["reason"]
        except (ValueError, KeyError, IndexError):
            reason = "no reason given"
        return [], f"YouTube returned HTTP {r.status_code}: {reason}"

    return parse_videos(r.json()), None


def parse_videos(payload):
    """Pull the fields we show out of a YouTube response.

    Split out from the request so it can be tested against a saved response
    with no network. Every field is read with .get, because the API omits keys
    rather than sending nulls and a missing channel title should not crash a page.
    """
    out = []
    for item in payload.get("items", []):
        vid = item.get("id", {}).get("videoId")
        if not vid:
            continue
        snip = item.get("snippet", {})
        out.append({"title": snip.get("title", "untitled"),
                    "channel": snip.get("channelTitle", "unknown channel"),
                    "url": f"https://www.youtube.com/watch?v={vid}"})
    return out


def books_search_link(query):
    """A plain Google Books search page. No key, no quota, never empty."""
    return "https://www.google.com/search?tbm=bks&q=" + quote_plus(query)


def search_books(query, api_key="", n=3):
    """Return (books, error).

    Google Books answers without a key, but that quota is shared by everyone
    on your IP address and returns 429 almost immediately. Sending the key
    moves the quota onto your own project.

    printType=books drops magazines, which otherwise fill the results for
    broad queries like "cloud computing".
    """
    # country is not optional in practice. Google Books serves a per-country
    # catalogue and refuses the request with 403 "forbidden" when it cannot
    # work out where you are, which is what happens from outside the US.
    params = {"q": query, "maxResults": n, "printType": "books",
              "langRestrict": "en", "country": "US"}
    if api_key:
        params["key"] = api_key
    r, err = _get(BOOKS_URL, params)
    if err:
        return [], f"could not reach Google Books: {err}"

    if r.status_code == 429:
        return [], ("Google Books rate limit hit. Enable the Books API in your "
                    "Google Cloud project so the key counts, then pass it in.")
    if r.status_code != 200:
        # same trick as YouTube: the body names the cause. accessNotConfigured
        # means the Books API is not switched on for this project.
        try:
            err = r.json()["error"]
            reason = err.get("errors", [{}])[0].get("reason", "")
            # the short reason is often just "forbidden", which says nothing.
            # the message field is where Google explains itself.
            detail = " ".join(x for x in (reason, err.get("message", "")) if x)
        except (ValueError, KeyError, IndexError):
            detail = "no reason given"
        return [], f"Google Books returned HTTP {r.status_code}: {detail}"

    return parse_books(r.json()), None


def parse_books(payload):
    """Pull the fields we show out of a Google Books response."""
    out = []
    for item in payload.get("items", []):
        info = item.get("volumeInfo", {})
        thumb = info.get("imageLinks", {}).get("thumbnail", "")
        out.append({
            "title": info.get("title", "untitled"),
            "authors": ", ".join(info.get("authors", [])) or "unknown author",
            "year": str(info.get("publishedDate", ""))[:4],
            "blurb": info.get("description", "") or "",
            # the API hands back http, which browsers block on an https page
            "thumbnail": thumb.replace("http://", "https://"),
            "url": info.get("infoLink", ""),
        })
    return out


if __name__ == "__main__":
    import sys

    term = sys.argv[1] if len(sys.argv) > 1 else "Kubernetes"
    key = sys.argv[2] if len(sys.argv) > 2 else ""

    print(f"--- videos for '{term} tutorial' ---")
    vids, err = search_videos(f"{term} tutorial", key)
    print("error:", err) if err else None
    for v in vids:
        print(f"  {v['title']}  ({v['channel']})")
        print(f"    {v['url']}")
    print("  fallback link:", youtube_search_link(f"{term} tutorial"))

    print(f"\n--- books for '{term}' ---")
    books, err = search_books(term, key)
    print("error:", err) if err else None
    for b in books:
        print(f"  {b['title']} - {b['authors']} ({b['year']})")
    print("  fallback link:", books_search_link(term))
