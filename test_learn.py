"""Checks the parsing and the failure paths. No network needed."""

from learn import (parse_books, parse_videos, search_books, search_videos,
                   youtube_search_link)

# a normal YouTube response, plus two rows the real API does send:
# a channel result with no videoId, and an item missing channelTitle
YT = {"items": [
    {"id": {"kind": "youtube#video", "videoId": "X48VuDVv0do"},
     "snippet": {"title": "Kubernetes Tutorial for Beginners",
                 "channelTitle": "TechWorld with Nana"}},
    {"id": {"kind": "youtube#channel", "channelId": "UC123"},
     "snippet": {"title": "Some Channel", "channelTitle": "Some Channel"}},
    {"id": {"kind": "youtube#video", "videoId": "abc123"},
     "snippet": {"title": "K8s in 10 minutes"}},
]}

vids = parse_videos(YT)
assert len(vids) == 2, f"channel result should be dropped, got {len(vids)}"
assert vids[0]["url"] == "https://www.youtube.com/watch?v=X48VuDVv0do"
assert vids[1]["channel"] == "unknown channel", "missing channel must not crash"
assert parse_videos({}) == [], "empty payload must give an empty list"
print("parse_videos ok")

# a normal book, plus one with no authors, no description and an http thumbnail
BK = {"items": [
    {"volumeInfo": {"title": "Kubernetes: Up and Running",
                    "authors": ["Brendan Burns", "Joe Beda"],
                    "publishedDate": "2019-10-07",
                    "description": "How to run containers at scale.",
                    "imageLinks": {"thumbnail": "http://books.google.com/x.jpg"},
                    "infoLink": "https://books.google.com/y"}},
    {"volumeInfo": {"title": "Bare Minimum Book"}},
    {"saleInfo": {}},
]}

books = parse_books(BK)
assert len(books) == 3
assert books[0]["authors"] == "Brendan Burns, Joe Beda"
assert books[0]["year"] == "2019", books[0]["year"]
assert books[0]["thumbnail"].startswith("https://"), "http thumbnail not upgraded"
assert books[1]["authors"] == "unknown author"
assert books[1]["blurb"] == "" and books[1]["thumbnail"] == ""
assert books[2]["title"] == "untitled", "an item with no volumeInfo must not crash"
print("parse_books ok")

assert youtube_search_link("Agile / Scrum tutorial") == (
    "https://www.youtube.com/results?search_query=Agile+%2F+Scrum+tutorial")
print("youtube_search_link ok, slashes and spaces escaped")

# no key must not attempt a request
assert search_videos("anything", "") == ([], "no API key set")
print("missing key handled without a call")

# this sandbox cannot reach googleapis.com, so both calls fail for real.
# The proxy blocks with a 403 rather than dropping the connection, so either
# the HTTP branch or the RequestException branch may fire. Both must return an
# empty list and a readable reason, and neither may raise.
vids, err = search_videos("kubernetes", "fake-key")
assert vids == [] and err, (vids, err)
print("youtube failure:", err)
books, err = search_books("kubernetes")
assert books == [] and err, (books, err)
print("books failure:", err)
print("network failure returns an empty list and a reason, no traceback")

print("\nall checks passed")

# added after a real 429 from keyless Google Books
from learn import books_search_link
assert books_search_link("C++ programming") == (
    "https://www.google.com/search?tbm=bks&q=C%2B%2B+programming")
books, err = search_books("kubernetes", "fake-key")
assert books == [] and err, (books, err)
print("books link and keyed-call failure path ok:", err)
