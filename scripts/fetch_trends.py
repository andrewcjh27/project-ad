"""
fetch_trends.py — build trends.json for the Ad Studio trend searcher
====================================================================
Runs in CI (see .github/workflows/trends.yml), NOT in the browser. That is the
whole point: server-side there is no CORS, so this can read the sources the
static page cannot — Google Trends and Reddit — on top of the ones the browser
can already reach (Apple's charts and Wikipedia most-read).

SUBJECTS, NOT JUST TITLES
-------------------------
Apple's charts can only ever emit songs, films and podcasts, so a feed built on
them alone reads as a list of people and movie titles — hard to build a brand ad
around. The fix is subject-scoped forums: Reddit is asked for food, fashion,
beauty, design, home, travel and fitness directly (see CATEGORY_SUBS), and the
open-ended sources (Google Trends, Wikipedia) are classified into the same
taxonomy. `category` is now a SUBJECT, not the name of the source it came from.

REGIONS
-------
Three sources take a region natively — Google Trends (`geo`), Apple (storefront)
and Wikipedia (language edition) — so each is fetched once per region in REGIONS
and every record carries the `region` it came from. Reddit's subject subs have no
geo dimension, so they are fetched once and marked GLOBAL; the UI says so rather
than implying a country's forums were read.

    {"version": 3, "generated": "<iso>", "items": [
       {"term", "keyword", "hashtag", "category", "formats", "rank", "region",
        "blurb", "source", "url", "volume", "when"} ...],
     "regions": [{"code", "label"} ...],
     "categories": [...],
     "sources": [{"id", "label", "ok", "count", "error"} ...]}

`keyword`, `hashtag` and `formats` are DERIVED from the trend's own text — they
are a starting point for the creative, not measured platform data. No free
keyless API exposes real Instagram/TikTok hashtag volume, so inventing a number
for them would be exactly the frozen-stand-in the project forbids; the UI labels
them as suggestions instead. `rank` and `volume`, where present, are real.

The keyword classifier is English-only, so titles from a non-English Wikipedia or
Google Trends region mostly land in the "Culture" catch-all. That is the honest
floor; the page's Gemini pass re-classifies in any language when a key is set.

Design notes
------------
* stdlib only (urllib + xml.etree) so CI needs no pip install.
* Every source is wrapped in try/except — one dead feed must never fail the run.
* The safety lists, KW_STOP, the format map, the category list and the region
  table are PORTS OF THE CLIENT'S COPIES and must stay in sync with
  ad-studio.html; scripts/check_safety_sync.py enforces that in CI.
* Deterministic ordering so an unchanged day produces an unchanged file and the
  workflow commits nothing.
"""

import json
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

UA = "ProjectAD-TrendBot/1.0 (+https://github.com/andrewcjh27/project-ad)"
TIMEOUT = 20
MAX_ITEMS = 40          # per source call, before merge
MAX_PER_REGION = 90     # keeps one busy region from crowding out the rest
POLITE_DELAY = 0.7      # seconds between calls — many small feeds, be a good citizen

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


# ── regions — keep in sync with ad-studio.html ────────────────────────────────
# `geo` = Google Trends code, `store` = Apple storefront, `wiki` = Wikipedia
# language edition. GLOBAL is deliberately absent: it is not a place, so it is
# rendered as "no region filter" rather than being faked with US data.
REGIONS = {
    "US": {"label": "United States", "geo": "US", "store": "us", "wiki": "en"},
    "GB": {"label": "United Kingdom", "geo": "GB", "store": "gb", "wiki": "en"},
    "KR": {"label": "South Korea", "geo": "KR", "store": "kr", "wiki": "ko"},
    "JP": {"label": "Japan", "geo": "JP", "store": "jp", "wiki": "ja"},
    "FR": {"label": "France", "geo": "FR", "store": "fr", "wiki": "fr"},
    "DE": {"label": "Germany", "geo": "DE", "store": "de", "wiki": "de"},
    "BR": {"label": "Brazil", "geo": "BR", "store": "br", "wiki": "pt"},
    "IN": {"label": "India", "geo": "IN", "store": "in", "wiki": "en"},
}
GLOBAL = "GLOBAL"   # region value for sources with no geo dimension (Reddit)

# ── subject taxonomy — keep in sync with ad-studio.html ───────────────────────
CATEGORIES = [
    "Food & Drink", "Fashion", "Beauty", "Colour & Design", "Home", "Travel",
    "Fitness", "Tech", "Gaming", "Music", "Film & TV", "Sport", "People", "Culture",
]
FALLBACK_CATEGORY = "Culture"

# Content formats to suggest per category. Short-form video first — that is what
# the searcher is feeding — with one non-video option so a static poster brief
# is still served.
FORMATS = {
    "Food & Drink": ["Reel", "TikTok", "Carousel"],
    "Fashion": ["Reel", "TikTok", "Lookbook"],
    "Beauty": ["Reel", "TikTok", "Tutorial"],
    "Colour & Design": ["Carousel", "Poster", "Reel"],
    "Home": ["Reel", "Carousel", "Poster"],
    "Travel": ["Reel", "Story", "Carousel"],
    "Fitness": ["Reel", "Shorts", "Carousel"],
    "Tech": ["Shorts", "Carousel", "Poster"],
    "Gaming": ["Shorts", "TikTok", "Poster"],
    "Music": ["Reel", "TikTok", "Shorts"],
    "Film & TV": ["Reel", "Shorts", "Poster"],
    "Sport": ["Reel", "Shorts", "Story"],
    "People": ["Reel", "TikTok", "Carousel"],
    "Culture": ["Reel", "TikTok", "Carousel"],
}
DEFAULT_FORMATS = ["Reel", "Carousel", "Story"]

# First match wins, so the specific patterns lead. English-only by design — see
# the module docstring; the LLM pass handles other languages.
CLASSIFIERS = [
    ("Food & Drink", r"\b(recipe|restaurant|chef|menu|coffee|caf[eé]|bakery|cook(ing|ed)?|dish|cuisine|"
                     r"snack|drink|cocktail|beer|wine|whisky|pizza|burger|ramen|kimchi|sushi|taco|"
                     r"dessert|chocolate|matcha|brunch|michelin)\b"),
    ("Beauty", r"\b(skincare|skin care|makeup|lipstick|mascara|serum|sunscreen|fragrance|perfume|"
               r"haircare|shampoo|beauty|cosmetic\w*|manicure|nail art)\b"),
    ("Fashion", r"\b(fashion|outfit|sneaker\w*|streetwear|runway|lookbook|handbag|denim|couture|"
                r"wardrobe|thrift\w*|capsule collection|met gala|fashion week)\b"),
    ("Colour & Design", r"\b(colou?r of the year|pantone|palette|typeface|typograph\w+|graphic design|"
                        r"branding|logo redesign|poster design|interior design|architect\w+)\b"),
    ("Home", r"\b(interior|furniture|home decor|apartment tour|kitchen remodel|renovation|ikea)\b"),
    ("Travel", r"\b(travel|flight|airline|hotel|itinerary|destination|tourism|resort|airbnb|backpack\w*)\b"),
    ("Fitness", r"\b(workout|marathon|gym|fitness|yoga|pilates|running|nutrition|protein|hyrox|crossfit)\b"),
    ("Sport", r"\b(football|soccer|nba|nfl|mlb|olympic\w*|world cup|tennis|golf|formula 1|f1|league|"
              r"premier league|champions league)\b"),
    ("Gaming", r"\b(gaming|nintendo|playstation|xbox|steam deck|esports|speedrun|dlc|roguelike)\b"),
    ("Tech", r"\b(iphone|android|chatgpt|openai|gadget|laptop|startup|software|robot\w*|semiconductor|"
             r"electric vehicle|smartphone)\b"),
    ("Music", r"\b(album|single|tour|concert|band|rapper|singer|song|billboard|k-?pop|setlist|grammy)\b"),
    ("Film & TV", r"\b(film|movie|series|season \d|episode|trailer|box office|netflix|drama|actor|"
                  r"actress|oscars|streaming)\b"),
]
COMPILED_CLASSIFIERS = [(cat, re.compile(pat, re.I)) for cat, pat in CLASSIFIERS]


def classify(text, default=FALLBACK_CATEGORY):
    """Deterministic subject classification. The floor, not the ceiling."""
    for cat, rx in COMPILED_CLASSIFIERS:
        if rx.search(text or ""):
            return cat
    return default


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
# A headline is not postable; a keyword is. See the module docstring on why these
# are labelled as suggestions in the UI.
KW_STOP = {
    "the", "a", "an", "and", "or", "but", "for", "with", "from", "that", "this", "these", "those",
    "into", "onto", "your", "you", "our", "their", "his", "her", "its", "it", "is", "are", "was",
    "were", "be", "been", "being", "has", "have", "had", "will", "just", "new", "now", "how", "why",
    "what", "when", "who", "all", "out", "off", "up", "down", "over", "after", "before", "about",
    "official", "video", "feat", "featuring", "remix", "version", "edition", "season", "episode",
}


def _best_proper_run(words):
    """Longest run of capitalised non-stopword words, earliest run winning ties.

    A title-initial "The" is kept: the real tag is #TheBear, not #Bear. Anywhere
    else "the" breaks the run, which is what stops "X and The Y" fusing.
    """
    proper, best = [], []
    for w in words:
        # A CAPITALISED stopword stays in the run: "New Balance" and "New York" are
        # brands, not a stopword followed by a word. Lowercase words still break it,
        # which is what stops "X and the Y" fusing.
        if re.match(r"^[A-Z][\w'&-]*$", w):
            proper.append(w)
            if len(proper) > len(best):
                best = proper[:]
        else:
            proper = []
    while best and best[-1].lower() in KW_STOP:   # "Stranger Things Season" -> "Stranger Things"
        best.pop()
    if not any(w.lower() not in KW_STOP for w in best):
        return []                                  # "The best kimchi…" must not become #The
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
    # "/" splits only when spaced: "Song / Artist" is two fields, "HUNTR/X" is a name.
    best, segments = [], [seg for seg in re.split(r"[—–|·,]+|\s+/\s+", s) if seg and seg.strip()]
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
    # Keep deliberate inner caps ("iPhone", "XCX", "ROSÉ"); title-case only words
    # that are entirely lowercase, so #iPhoneLeak does not become #IPhoneLeak.
    parts = [p if p != p.lower() else p[:1].upper() + p[1:] for p in parts]
    return "#" + "".join(parts)[:40]


def enrich(rec):
    """Attach keyword / hashtag / formats. One place, so every source matches."""
    cat = rec.get("category") or FALLBACK_CATEGORY
    rec["category"] = cat if cat in CATEGORIES else FALLBACK_CATEGORY
    rec.setdefault("region", GLOBAL)
    kw = rec.get("keyword") or to_keyword(rec.get("term", ""))
    rec["keyword"] = kw
    rec["hashtag"] = rec.get("hashtag") or to_hashtag(kw)
    rec["formats"] = rec.get("formats") or FORMATS.get(rec["category"], DEFAULT_FORMATS)
    return rec


def now_ms():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


# ── region-aware sources ──────────────────────────────────────────────────────
def src_google_trends(region):
    """Google Trends daily search trends RSS — already keyword-shaped (it IS the
    search query), regional by `geo`, and flatly unavailable to a browser."""
    geo = REGIONS[region]["geo"]
    root = ET.fromstring(get(f"https://trends.google.com/trending/rss?geo={geo}"))
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
            "category": classify(f"{title} {blurb}"),
            "region": region,
            "blurb": blurb,
            "source": "Google Trends",
            "url": (item.findtext("link") or "").strip(),
            "volume": volume or 1,
            "when": now_ms(),
        })
    return out[:MAX_ITEMS]


def _apple(region, kind, feed, media_type, category, label, limit=25):
    """Apple's marketing RSS: free, keyless, CORS-enabled, regional by storefront,
    and a genuine what-is-being-consumed-right-now signal. Chart position is real;
    the feed carries no play counts, so `volume` stays 0 and `rank` carries the
    meaning — fabricating a play count would be inventing a statistic."""
    store = REGIONS[region]["store"]
    url = f"https://rss.applemarketingtools.com/api/v2/{store}/{kind}/{feed}/{limit}/{media_type}.json"
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
            "region": region,
            "blurb": ", ".join(g.get("name", "") for g in (r.get("genres") or []) if g.get("name") != "Music")[:120],
            "source": label,
            "url": r.get("url", "") or "",
            "volume": 0,
            "rank": i + 1,
            "when": now_ms(),
        })
    return out


def src_apple_music(region):
    return _apple(region, "music", "most-played", "songs", "Music", "Apple Music")


def src_apple_movies(region):
    return _apple(region, "movies", "top-movies", "movies", "Film & TV", "Apple Movies")


def src_wikipedia(region):
    """Most-read from the region's own language edition."""
    lang = REGIONS[region]["wiki"]
    last = None
    for back in (1, 2):
        d = datetime.now(timezone.utc) - timedelta(days=back)
        url = f"https://{lang}.wikipedia.org/api/rest_v1/feed/featured/{d.year}/{d.month:02d}/{d.day:02d}"
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
            desc = clean(a.get("description") or (a.get("extract") or "").split(". ")[0])
            out.append({
                "term": term,
                "keyword": term,        # article titles are already noun-shaped
                "category": classify(f"{term} {desc}"),
                "region": region,
                "blurb": desc,
                "source": "Wikipedia",
                "url": ((a.get("content_urls", {}) or {}).get("desktop", {}) or {}).get("page", ""),
                "volume": int(a.get("views") or 0),
                "when": int(d.timestamp() * 1000),
            })
        if out:
            return out[:MAX_ITEMS]
    raise last or RuntimeError(f"no {lang} Wikipedia feed for the last 2 days")


REGION_SOURCES = [
    ("google_trends", "Google Trends", src_google_trends),
    ("apple_music", "Apple Music", src_apple_music),
    ("apple_movies", "Apple Movies", src_apple_movies),
    ("wikipedia", "Wikipedia", src_wikipedia),
]


# ── subject-scoped forums (global only — a subreddit has no geo) ──────────────
# THIS is what stops the feed being a list of people and film titles: the subject
# is chosen by which subs are asked, not inferred afterwards.
CATEGORY_SUBS = {
    "Food & Drink": "food+FoodPorn+recipes+Cooking+Coffee+cocktails",
    "Fashion": "streetwear+femalefashionadvice+malefashionadvice+fashion",
    "Beauty": "SkincareAddiction+MakeupAddiction+FragranceCirclejerk",
    "Colour & Design": "design+DesignPorn+graphic_design+InteriorDesign",
    "Home": "HomeDecorating+CozyPlaces+malelivingspace",
    "Travel": "travel+solotravel+backpacking",
    "Fitness": "Fitness+running+xxfitness",
    "Tech": "gadgets+technology",
    "Gaming": "gaming+pcgaming",
    "Music": "Music+popheads",
    "Film & TV": "movies+television+Letterboxd",
    "People": "popculturechat+entertainment",
}


def src_reddit_category(category):
    """Anonymous browser CORS is blocked here, but a server with a real
    User-Agent is fine. One call per subject, so the category is known, not guessed."""
    subs = CATEGORY_SUBS[category]
    j = get_json(f"https://www.reddit.com/r/{subs}/top.json?t=day&limit=25")
    out = []
    for c in j.get("data", {}).get("children", []):
        d = c.get("data", {})
        if d.get("over_18") or d.get("stickied"):
            continue
        title = clean(d.get("title", ""), 140)
        if not title:
            continue
        out.append({
            "term": title,
            "category": category,
            "region": GLOBAL,
            "blurb": "r/" + (d.get("subreddit", "") or ""),
            "source": "Reddit",
            "url": "https://www.reddit.com" + d.get("permalink", ""),
            "volume": int(d.get("score") or 0),
            "when": int(float(d.get("created_utc") or 0) * 1000),
        })
    return out[:MAX_ITEMS]


def main(out_path="trends.json"):
    items, meta = [], []

    def record(sid, label, fn):
        nonlocal items
        try:
            got = fn()
            items += got
            meta.append({"id": sid, "label": label, "ok": True, "count": len(got), "error": ""})
            print(f"  {label:<28} {len(got):>3} items")
        except Exception as e:  # noqa: BLE001 — one bad feed must not fail the run
            meta.append({"id": sid, "label": label, "ok": False, "count": 0, "error": str(e)[:200]})
            print(f"  {label:<28}  -- failed: {e}", file=sys.stderr)
        time.sleep(POLITE_DELAY)

    for region in REGIONS:
        for sid, label, fn in REGION_SOURCES:
            record(f"{sid}:{region}", f"{label} ({region})", lambda fn=fn, r=region: fn(r))
    for category in CATEGORY_SUBS:
        record(f"reddit:{category}", f"Reddit ({category})", lambda c=category: src_reddit_category(c))

    before = len(items)
    items = [enrich(r) for r in items if r.get("term") and is_ad_safe(r)]

    # Dedupe on (region, keyword): the same artist charting in two countries is two
    # regional trends, but three posts about them in one region are one trend.
    seen, deduped = set(), []
    for r in items:
        k = (r["region"], (r.get("keyword") or r["term"]).strip().lower())
        if k in seen:
            continue
        seen.add(k)
        deduped.append(r)

    # Cap per region so one busy country cannot crowd out the others.
    per_region, capped = {}, []
    for r in sorted(deduped, key=lambda r: (r["region"], r["source"], r.get("rank") or 0,
                                            -int(r.get("volume") or 0), r["term"])):
        n = per_region.get(r["region"], 0)
        if n >= MAX_PER_REGION:
            continue
        per_region[r["region"]] = n + 1
        capped.append(r)

    payload = {
        "version": 3,
        "generated": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "items": capped,
        "regions": [{"code": c, "label": v["label"]} for c, v in REGIONS.items()],
        "categories": CATEGORIES,
        "sources": meta,
        "filtered": before - len(capped),
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")

    ok = sum(1 for m in meta if m["ok"])
    by_cat = {}
    for r in capped:
        by_cat[r["category"]] = by_cat.get(r["category"], 0) + 1
    print(f"\nwrote {out_path}: {len(capped)} items from {ok}/{len(meta)} source calls "
          f"({before - len(capped)} filtered/deduped/capped)")
    print("  regions   :", ", ".join(f"{k}={v}" for k, v in sorted(per_region.items())))
    print("  categories:", ", ".join(f"{k}={v}" for k, v in sorted(by_cat.items())))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
