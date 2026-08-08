"""
fetch_trends.py — build trends.json for the Ad Studio trend searcher
====================================================================
Runs in CI (see .github/workflows/trends.yml), NOT in the browser. That is the
whole point: server-side there is no CORS, so this can read the sources the
static page cannot — Google Trends and Reddit — on top of the ones the browser
can already reach (Apple's charts and Wikipedia most-read).

MEDIA-FIRST, KEYWORD-FIRST
--------------------------
The searcher is for building *social* creative, so the sources are what culture
is playing/watching/posting — music, film, TV, podcasts and pop-culture forums —
not general or tech news. Google News and Hacker News were dropped for exactly
that reason: front-page news is the wrong raw material for a brand Reel.

Every record also carries a short `keyword` and a `hashtag`, because a
sentence-long headline is not something a brand can build a post around.

    {"version": 2, "generated": "<iso>", "items": [
       {"term", "keyword", "hashtag", "category", "formats", "rank",
        "blurb", "source", "url", "volume", "when"} ...],
     "sources": [{"id", "label", "ok", "count", "error"} ...]}

`keyword`, `hashtag` and `formats` are DERIVED from the trend's own text — they
are a starting point for the creative, not measured platform data. No free
keyless API exposes real Instagram/TikTok hashtag volume, so inventing a number
for them would be exactly the frozen-stand-in the project forbids; the UI labels
them as suggestions instead. `rank` and `volume`, where present, are real.

Design notes
------------
* stdlib only (urllib + xml.etree) so CI needs no pip install.
* Every source is wrapped in try/except — one dead feed must never fail the run.
* The brand-safety blocklist is a PORT OF THE CLIENT'S RULE and must stay in
  sync with TREND_BLOCK / TREND_ALLOW in ad-studio.html; scripts/check_safety_sync.py
  enforces that in CI. The page re-applies its own filter to whatever it loads,
  so this is defence in depth, not a single point of trust.
* Deterministic ordering (source, then volume) so an unchanged day produces an
  unchanged file and the workflow commits nothing.
"""

import json
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

UA = "ProjectAD-TrendBot/1.0 (+https://github.com/andrewcjh27/project-ad)"
TIMEOUT = 20
MAX_ITEMS = 60          # per source, before merge
MAX_TOTAL = 120         # written to trends.json

# ── brand safety — keep in sync with ad-studio.html ───────────────────────────
BLOCK = re.compile(
    r"\b(died?|death|deaths|dead|obituary|killed|kills|killing|murder|shooting|shooter|stabb\w*|"
    r"assault|rape|terror\w*|bomb\w*|war|invasion|troops|massacre|genocide|hostage|crash|earthquake|"
    r"hurricane|wildfire|flood|famine|outbreak|pandemic|virus|cancer|overdose|suicide|arrest\w*|"
    r"indict\w*|lawsuit|convicted|fraud|scandal|abuse|election|senate|parliament|president|"
    r"prime minister|congress|republican|democrat|verdict|trial)\b",
    re.I,
)
ALLOW = re.compile(
    r"\b(deadpool|god of war|call of duty|warframe|warhammer|star wars|the crown|house of cards|"
    r"killers of the flower moon|murder on the orient express|only murders)\b",
    re.I,
)
# Wikipedia structural pages that always top the chart but are not trends.
WIKI_NOISE = re.compile(r"^(main page|special:|wikipedia:|portal:|category:|help:|talk:|list of |deaths in )", re.I)


def is_ad_safe(rec):
    hay = f"{rec.get('term','')} {rec.get('blurb','')}"
    return bool(ALLOW.search(hay)) or not BLOCK.search(hay)


def get(url, accept=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **({"Accept": accept} if accept else {})})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read()


def get_json(url):
    return json.loads(get(url, "application/json"))


def clean(s, limit=180):
    s = re.sub(r"<[^>]+>", " ", s or "")          # strip any markup in RSS blurbs
    s = re.sub(r"\s+", " ", s).strip()
    return s[:limit]


# ── keyword / hashtag / format derivation — keep in sync with ad-studio.html ───
# Short connective words that must never survive into a keyword or a hashtag.
KW_STOP = {
    "the", "a", "an", "and", "or", "but", "for", "with", "from", "that", "this", "these", "those",
    "into", "onto", "your", "you", "our", "their", "his", "her", "its", "it", "is", "are", "was",
    "were", "be", "been", "being", "has", "have", "had", "will", "just", "new", "now", "how", "why",
    "what", "when", "who", "all", "out", "off", "up", "down", "over", "after", "before", "about",
    "official", "video", "feat", "featuring", "remix", "version", "edition", "season", "episode",
}

# Content formats to suggest per category. Short-form video first — that is what
# the searcher is feeding — with one non-video option so a static poster brief
# is still served.
FORMATS = {
    "Music": ["Reel", "TikTok", "Shorts"],
    "Film & TV": ["Reel", "Shorts", "Poster"],
    "Podcast": ["Audiogram", "Shorts", "Carousel"],
    "Gaming": ["Shorts", "TikTok", "Poster"],
    "Culture": ["Reel", "TikTok", "Carousel"],
    "Search": ["Reel", "Carousel", "Story"],
}
DEFAULT_FORMATS = ["Reel", "Carousel", "Story"]


def _best_proper_run(words):
    """Longest run of capitalised non-stopword words, earliest run winning ties.

    A title-initial "The" is kept: the real tag is #TheBear, not #Bear. Anywhere
    else "the" breaks the run, which is what stops "X and The Y" fusing.
    """
    proper, best = [], []
    for i, w in enumerate(words):
        keep_article = i == 0 and w.lower() == "the"
        if re.match(r"^[A-Z][\w'&-]*$", w) and (keep_article or w.lower() not in KW_STOP):
            proper.append(w)
            if len(proper) > len(best):
                best = proper[:]
        else:
            proper = []
    return best


def to_keyword(text, limit=3):
    """Reduce a title to the 1-3 words someone would actually search or tag.

    Prefers a run of capitalised words (a proper noun — the artist, the show,
    the game), because that is what becomes the hashtag. Falls back to the first
    few content words so nothing is ever left without a keyword.
    """
    s = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", text or "")      # drop "(feat. …)", "[Official]"
    s = re.sub(r"\s+-\s+[^-]{2,40}$", "", s)                   # drop " - Publisher"
    head = s.split(":")[0]
    s = head if len(head) > 8 else s                           # keep short titles whole ("Dune: Part Two")

    # Split on dash/pipe/comma separators FIRST. Without this, "Song — Artist"
    # reads as one capitalised run and yields the nonsense "Song Artist".
    best, segments = [], [seg for seg in re.split(r"[—–|·,/]+", s) if seg.strip()]
    for seg in segments:
        words = [w for w in re.split(r"\s+", re.sub(r"[^\w\s'&-]", " ", seg)) if w]
        run = _best_proper_run(words)
        if len(run) > len(best):
            best = run
    if best:
        return " ".join(best[:limit]).strip()

    flat = re.sub(r"[^\w\s'&-]", " ", s)
    words = [w for w in re.split(r"\s+", flat) if w and w.lower() not in KW_STOP and len(w) > 2]
    return " ".join(words[:limit]).strip() or clean(text, 40)


def to_hashtag(keyword):
    """#CamelCase from a keyword. Suggested, not measured — see module docstring."""
    parts = [p for p in re.split(r"[^\w]+", keyword or "") if p]
    if not parts:
        return ""
    return "#" + "".join(p[:1].upper() + p[1:] for p in parts)[:40]


def enrich(rec):
    """Attach keyword / hashtag / formats. One place, so every source matches."""
    rec.setdefault("category", "")
    kw = rec.get("keyword") or to_keyword(rec.get("term", ""))
    rec["keyword"] = kw
    rec["hashtag"] = rec.get("hashtag") or to_hashtag(kw)
    rec["formats"] = rec.get("formats") or FORMATS.get(rec["category"], DEFAULT_FORMATS)
    return rec


# ── sources the BROWSER CANNOT reach (no CORS) — the reason this script exists ──
def src_google_trends(geo="US"):
    """Google Trends daily search trends RSS — already keyword-shaped (it IS the
    search query), and flatly unavailable to a browser."""
    xml = get(f"https://trends.google.com/trending/rss?geo={geo}")
    root = ET.fromstring(xml)
    ns = {"ht": "https://trends.google.com/trending/rss"}
    out = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        traffic = item.findtext("ht:approx_traffic", default="", namespaces=ns) or ""
        volume = int(re.sub(r"[^0-9]", "", traffic) or 0)
        news = item.find("ht:news_item", ns)
        blurb = clean(news.findtext("ht:news_item_title", default="", namespaces=ns)) if news is not None else ""
        out.append({
            "term": title,
            "keyword": title,           # the query itself is the keyword
            "category": "Search",
            "blurb": blurb,
            "source": "Google Trends",
            "url": (item.findtext("link") or "").strip(),
            "volume": volume or 1,
            "when": int(datetime.now(timezone.utc).timestamp() * 1000),
        })
    return out[:MAX_ITEMS]


# Pop-culture and media forums rather than r/all. r/all is dominated by news and
# politics, which the safety filter then throws away — this asks for the right
# material in the first place instead of filtering the wrong material afterwards.
MEDIA_SUBS = "popculturechat+Music+movies+television+popheads+letterboxd+BoxOffice+gaming"


def src_reddit():
    """Anonymous browser CORS is blocked here, but a server with a real
    User-Agent is fine."""
    j = get_json(f"https://www.reddit.com/r/{MEDIA_SUBS}/top.json?t=day&limit=60")
    sub_cat = {
        "music": "Music", "popheads": "Music",
        "movies": "Film & TV", "television": "Film & TV", "letterboxd": "Film & TV", "boxoffice": "Film & TV",
        "gaming": "Gaming",
    }
    out = []
    for c in j.get("data", {}).get("children", []):
        d = c.get("data", {})
        if d.get("over_18") or d.get("stickied"):
            continue
        title = clean(d.get("title", ""), 140)
        if not title:
            continue
        sub = d.get("subreddit", "") or ""
        out.append({
            "term": title,
            "category": sub_cat.get(sub.lower(), "Culture"),
            "blurb": "r/" + sub,
            "source": "Reddit",
            "url": "https://www.reddit.com" + d.get("permalink", ""),
            "volume": int(d.get("score") or 0),
            "when": int(float(d.get("created_utc") or 0) * 1000),
        })
    return out[:MAX_ITEMS]


# ── media charts (also CORS-enabled, so the browser tier can use them too) ─────
def _apple(kind, feed, media_type, category, label, limit=25):
    """Apple's marketing RSS: free, keyless, CORS-enabled, and a genuine
    what-is-being-consumed-right-now signal. Chart position is real; there are no
    play counts in this feed, so `volume` stays 0 and `rank` carries the meaning."""
    url = f"https://rss.applemarketingtools.com/api/v2/us/{kind}/{feed}/{limit}/{media_type}.json"
    results = (get_json(url).get("feed", {}) or {}).get("results", []) or []
    # `i` counts every row, so a skipped malformed entry leaves a gap rather than
    # renumbering the chart — the position stays the real one.
    out = []
    for i, r in enumerate(results):
        name = clean(r.get("name", ""), 120)
        if not name:
            continue
        artist = clean(r.get("artistName", ""), 80)
        # For music the artist is the durable cultural handle (#TaylorSwift outlives
        # any one single); for film/podcasts the title itself is the handle.
        keyword = to_keyword(artist if category == "Music" and artist else name)
        out.append({
            "term": f"{name} — {artist}" if artist else name,
            "keyword": keyword,
            "category": category,
            "blurb": ", ".join(g.get("name", "") for g in (r.get("genres") or []) if g.get("name") != "Music")[:120],
            "source": label,
            "url": r.get("url", "") or "",
            "volume": 0,
            "rank": i + 1,
            "when": int(datetime.now(timezone.utc).timestamp() * 1000),
        })
    return out


def src_apple_music():
    return _apple("music", "most-played", "songs", "Music", "Apple Music")


def src_apple_movies():
    return _apple("movies", "top-movies", "movies", "Film & TV", "Apple Movies")


def src_apple_podcasts():
    return _apple("podcasts", "top", "podcasts", "Podcast", "Apple Podcasts")


# ── broad culture backstop (browser can also reach this one) ───────────────────
def src_wikipedia():
    last = None
    for back in (1, 2):
        d = datetime.now(timezone.utc) - timedelta(days=back)
        url = f"https://en.wikipedia.org/api/rest_v1/feed/featured/{d.year}/{d.month:02d}/{d.day:02d}"
        try:
            arts = get_json(url).get("mostread", {}).get("articles", [])
        except Exception as e:  # noqa: BLE001
            last = e
            continue
        out = []
        for a in arts:
            term = (a.get("titles", {}) or {}).get("normalized") or (a.get("title") or "").replace("_", " ")
            if not term or WIKI_NOISE.match(term):
                continue
            out.append({
                "term": term,
                "keyword": term,        # article titles are already noun-shaped
                "category": "Culture",
                "blurb": clean(a.get("description") or (a.get("extract") or "").split(". ")[0]),
                "source": "Wikipedia",
                "url": ((a.get("content_urls", {}) or {}).get("desktop", {}) or {}).get("page", ""),
                "volume": int(a.get("views") or 0),
                "when": int(d.timestamp() * 1000),
            })
        if out:
            return out[:MAX_ITEMS]
    raise last or RuntimeError("no Wikipedia feed for the last 2 days")


SOURCES = [
    ("google_trends", "Google Trends", src_google_trends),
    ("apple_music", "Apple Music", src_apple_music),
    ("apple_movies", "Apple Movies", src_apple_movies),
    ("apple_podcasts", "Apple Podcasts", src_apple_podcasts),
    ("reddit", "Reddit", src_reddit),
    ("wikipedia", "Wikipedia", src_wikipedia),
]


def main(out_path="trends.json"):
    items, meta = [], []
    for sid, label, fn in SOURCES:
        try:
            got = fn()
            items += got
            meta.append({"id": sid, "label": label, "ok": True, "count": len(got), "error": ""})
            print(f"  {label:<15} {len(got):>3} items")
        except Exception as e:  # noqa: BLE001  — one bad feed must not fail the run
            meta.append({"id": sid, "label": label, "ok": False, "count": 0, "error": str(e)[:200]})
            print(f"  {label:<15}  -- failed: {e}", file=sys.stderr)

    before = len(items)
    items = [enrich(r) for r in items if r.get("term") and is_ad_safe(r)]
    # Dedupe on the KEYWORD, not the headline: three posts about the same artist
    # are one trend, and keeping all three would crowd everything else off the page.
    seen, deduped = set(), []
    for r in items:
        k = (r.get("keyword") or r["term"]).strip().lower()
        if k in seen:
            continue
        seen.add(k)
        deduped.append(r)

    # Deterministic order (source, then volume/rank) so an unchanged day yields an
    # unchanged file — the workflow then commits nothing. The page re-ranks anyway.
    deduped.sort(key=lambda r: (r["source"], r.get("rank") or 0, -int(r.get("volume") or 0), r["term"]))
    deduped = deduped[:MAX_TOTAL]

    payload = {
        "version": 2,
        "generated": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "items": deduped,
        "sources": meta,
        "filtered": before - len(deduped),
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    ok = sum(1 for m in meta if m["ok"])
    print(f"wrote {out_path}: {len(deduped)} items from {ok}/{len(SOURCES)} sources "
          f"({before - len(deduped)} filtered/deduped)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
