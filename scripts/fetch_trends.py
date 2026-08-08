"""
fetch_trends.py — build trends.json for the Ad Studio trend searcher
====================================================================
Runs in CI (see .github/workflows/trends.yml), NOT in the browser. That is the
whole point: server-side there is no CORS, so this can read the sources the
static page cannot — Google Trends, Google News and Reddit — on top of the two
the browser can already reach (Wikipedia most-read, Hacker News).

Output is the SAME record shape ad-studio.html uses, so the page consumes it
with no client change (tier 1 of its three-tier loader):

    {"version": 1, "generated": "<iso>", "items": [
       {"term", "blurb", "source", "url", "volume", "when"} ...],
     "sources": [{"id", "label", "ok", "count", "error"} ...]}

Design notes
------------
* stdlib only (urllib + xml.etree) so CI needs no pip install.
* Every source is wrapped in try/except — one dead feed must never fail the run.
* The brand-safety blocklist is a PORT OF THE CLIENT'S RULE and must stay in
  sync with TREND_BLOCK / TREND_ALLOW in ad-studio.html. The page re-applies its
  own filter to whatever it loads, so this is defence in depth, not a single
  point of trust.
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


# ── sources the BROWSER CANNOT reach (no CORS) — the reason this script exists ──
def src_google_trends(geo="US"):
    """Google Trends daily search trends RSS — the closest thing to a real
    'what is spiking right now' signal, and flatly unavailable to a browser."""
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
            "blurb": blurb,
            "source": "Google Trends",
            "url": (item.findtext("link") or "").strip(),
            "volume": volume or 1,
            "when": int(datetime.now(timezone.utc).timestamp() * 1000),
        })
    return out[:MAX_ITEMS]


def src_google_news():
    xml = get("https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en")
    root = ET.fromstring(xml)
    out = []
    for i, item in enumerate(root.iter("item")):
        title = clean(item.findtext("title") or "", 140)
        if not title:
            continue
        # Google News titles end with " - Publisher"; drop it, it is not part of the topic.
        title = re.sub(r"\s+-\s+[^-]{2,40}$", "", title)
        out.append({
            "term": title,
            "blurb": clean(item.findtext("description") or "", 160),
            "source": "Google News",
            "url": (item.findtext("link") or "").strip(),
            "volume": max(1, 100 - i),          # feed order is the only ranking signal
            "when": int(datetime.now(timezone.utc).timestamp() * 1000),
        })
    return out[:MAX_ITEMS]


def src_reddit():
    """Anonymous browser CORS is blocked here, but a server with a real
    User-Agent is fine."""
    j = get_json("https://www.reddit.com/r/all/top.json?t=day&limit=50")
    out = []
    for c in j.get("data", {}).get("children", []):
        d = c.get("data", {})
        if d.get("over_18"):
            continue
        title = clean(d.get("title", ""), 140)
        if not title:
            continue
        out.append({
            "term": title,
            "blurb": "r/" + d.get("subreddit", ""),
            "source": "Reddit",
            "url": "https://www.reddit.com" + d.get("permalink", ""),
            "volume": int(d.get("score") or 0),
            "when": int(float(d.get("created_utc") or 0) * 1000),
        })
    return out[:MAX_ITEMS]


# ── the two the browser can also do; kept here so trends.json is complete ──────
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
                "blurb": clean(a.get("description") or (a.get("extract") or "").split(". ")[0]),
                "source": "Wikipedia",
                "url": ((a.get("content_urls", {}) or {}).get("desktop", {}) or {}).get("page", ""),
                "volume": int(a.get("views") or 0),
                "when": int(d.timestamp() * 1000),
            })
        if out:
            return out[:MAX_ITEMS]
    raise last or RuntimeError("no Wikipedia feed for the last 2 days")


def src_hackernews():
    j = get_json("https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=30")
    out = []
    for h in j.get("hits", []):
        term = re.sub(r"^(show|ask)\s+hn:\s*", "", h.get("title") or "", flags=re.I).strip()
        if not term:
            continue
        url = h.get("url") or ""
        out.append({
            "term": term,
            "blurb": "",
            "source": "Hacker News",
            "url": url if url.startswith("http") else f"https://news.ycombinator.com/item?id={h.get('objectID')}",
            "volume": int(h.get("points") or 0),
            "when": int(datetime.now(timezone.utc).timestamp() * 1000),
        })
    return out[:MAX_ITEMS]


SOURCES = [
    ("google_trends", "Google Trends", src_google_trends),
    ("google_news", "Google News", src_google_news),
    ("reddit", "Reddit", src_reddit),
    ("wikipedia", "Wikipedia", src_wikipedia),
    ("hackernews", "Hacker News", src_hackernews),
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
    items = [r for r in items if r.get("term") and is_ad_safe(r)]
    seen, deduped = set(), []
    for r in items:
        k = r["term"].strip().lower()
        if k in seen:
            continue
        seen.add(k)
        deduped.append(r)

    # Deterministic order (source, then volume desc) so an unchanged day yields an
    # unchanged file — the workflow then commits nothing. The page re-ranks anyway.
    deduped.sort(key=lambda r: (r["source"], -int(r.get("volume") or 0), r["term"]))
    deduped = deduped[:MAX_TOTAL]

    payload = {
        "version": 1,
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
