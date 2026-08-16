"""
check_safety_sync.py — fail the build if the browser and CI copies diverge
=========================================================================
Parts of the trend searcher exist TWICE by necessity: once in ad-studio.html
(applied in the browser) and once in scripts/fetch_trends.py (applied in CI).
They cannot share a file — one is JavaScript shipped to a static page, the other
is Python run on a runner — so the next best thing is to make drift LOUD.

Three things are compared:

1. TREND_BLOCK / TREND_ALLOW  vs  BLOCK / ALLOW   (brand safety)
   Drift matters most here: if CI's list is the laxer of the two, trends.json
   ships topics the page would have refused, and they reach a user's brief. Per
   CLAUDE.md brand hard rules are deterministic, so a silent divergence is a
   correctness bug, not a nit.

2. KW_STOP                                        (keyword derivation)
   A word that stops a keyword in one copy but not the other makes the SAME
   trend produce a different hashtag depending on which tier served it — the
   published feed and a browser refresh would disagree on the deliverable.

3. TREND_FORMATS / DEFAULT_FORMATS  vs  FORMATS / DEFAULT_FORMATS
   Same reason: the suggested formats are user-visible output.

4. CATEGORIES, REGIONS, CLASSIFIERS                (subjects and regions)
   The subject chips are built from the client's CATEGORIES but the feed is
   bucketed by CI's; a category in one and not the other is either a chip that
   can never fill or items that fall into a bucket with no chip. REGIONS must
   agree on the Google `geo`, the Apple storefront and the Wikipedia language, or
   picking Korea would read a different country depending on the tier. And the
   CLASSIFIERS decide which bucket an item lands in — drift there silently
   re-files trends.

The alternations and word lists are compared as SETS, because two equivalent
lists are not byte-identical:
  * the JS block list happens to name `shooting` twice,
  * the Python source is an implicitly-concatenated raw string, so the literal
    text carries `r"` prefixes and newlines that are not part of the pattern.
Exits 1 on any difference, printing exactly what is unique to which side.
"""

import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
HTML = ROOT / "ad-studio.html"
PY = ROOT / "scripts" / "fetch_trends.py"


# ── brand-safety regexes ──────────────────────────────────────────────────────
def alternation(pattern: str) -> set:
    """Pull the `\\b( a | b | c )\\b` alternation out of a regex body."""
    m = re.search(r"\\b\((.*?)\)\\b", pattern, re.S)
    if not m:
        raise SystemExit("could not find a \\b(...)\\b alternation in:\n" + pattern[:200])
    return {a.strip() for a in m.group(1).split("|") if a.strip()}


def from_js(name: str) -> set:
    m = re.search(rf"const {name}\s*=\s*\n?\s*/(.*?)/i;", HTML.read_text(encoding="utf-8"), re.S)
    if not m:
        raise SystemExit(f"{name} not found in {HTML.name}")
    return alternation(m.group(1))


def from_py(name: str) -> set:
    m = re.search(
        rf"^{name} = re\.compile\(\s*(.*?),\s*re\.I,?\s*\)", PY.read_text(encoding="utf-8"), re.S | re.M
    )
    if not m:
        raise SystemExit(f"{name} not found in {PY.name}")
    # Rebuild the pattern from the implicitly-concatenated raw string literals.
    body = "".join(re.findall(r'r?"([^"]*)"', m.group(1)))
    return alternation(body)


# ── keyword stopwords ─────────────────────────────────────────────────────────
def kwstop_js() -> set:
    """`new Set(("a b " + "c d").split(" "))` — join the literals, then split."""
    src = HTML.read_text(encoding="utf-8")
    m = re.search(r"const KW_STOP\s*=\s*new Set\(\s*(.*?)\.split\(", src, re.S)
    if not m:
        raise SystemExit("KW_STOP not found in " + HTML.name)
    return {w for w in "".join(re.findall(r'"([^"]*)"', m.group(1))).split() if w}


def kwstop_py() -> set:
    src = PY.read_text(encoding="utf-8")
    m = re.search(r"^KW_STOP = \{(.*?)\n\}", src, re.S | re.M)
    if not m:
        raise SystemExit("KW_STOP not found in " + PY.name)
    return {w for w in re.findall(r'"([^"]*)"', m.group(1)) if w}


# ── format maps ───────────────────────────────────────────────────────────────
def _format_entries(body: str) -> dict:
    """Parse `Key: ["a","b"]` / `"Key": ["a","b"]` pairs into a dict."""
    out = {}
    for key_q, key_bare, vals in re.findall(r'(?:"([^"]+)"|([A-Za-z_]\w*))\s*:\s*\[([^\]]*)\]', body):
        out[key_q or key_bare] = tuple(re.findall(r'"([^"]*)"', vals))
    return out


def formats_js() -> tuple:
    src = HTML.read_text(encoding="utf-8")
    m = re.search(r"const TREND_FORMATS\s*=\s*\{(.*?)\n      \};", src, re.S)
    d = re.search(r"const DEFAULT_FORMATS\s*=\s*\[([^\]]*)\]", src)
    if not m or not d:
        raise SystemExit("TREND_FORMATS/DEFAULT_FORMATS not found in " + HTML.name)
    return _format_entries(m.group(1)), tuple(re.findall(r'"([^"]*)"', d.group(1)))


def formats_py() -> tuple:
    src = PY.read_text(encoding="utf-8")
    m = re.search(r"^FORMATS = \{(.*?)\n\}", src, re.S | re.M)
    d = re.search(r"^DEFAULT_FORMATS = (\[[^\]]*\])", src, re.M)
    if not m or not d:
        raise SystemExit("FORMATS/DEFAULT_FORMATS not found in " + PY.name)
    return _format_entries(m.group(1)), tuple(ast.literal_eval(d.group(1)))


# ── categories, regions, classifiers ──────────────────────────────────────────
def _js_unescape(t: str) -> str:
    r"""JS sources spell non-ASCII as \uXXXX; Python spells it literally."""
    return re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), t)


def categories_js() -> tuple:
    m = re.search(r"const CATEGORIES\s*=\s*\[(.*?)\];", HTML.read_text(encoding="utf-8"), re.S)
    if not m:
        raise SystemExit("CATEGORIES not found in " + HTML.name)
    return tuple(re.findall(r'"([^"]*)"', m.group(1)))


def categories_py() -> tuple:
    m = re.search(r"^CATEGORIES = \[(.*?)\n\]", PY.read_text(encoding="utf-8"), re.S | re.M)
    if not m:
        raise SystemExit("CATEGORIES not found in " + PY.name)
    return tuple(re.findall(r'"([^"]*)"', m.group(1)))


def regions_js() -> dict:
    m = re.search(r"const REGIONS\s*=\s*\{(.*?)\n      \};", HTML.read_text(encoding="utf-8"), re.S)
    if not m:
        raise SystemExit("REGIONS not found in " + HTML.name)
    out = {}
    for code, body in re.findall(r'(\w+):\s*\{([^}]*)\}', m.group(1)):
        f = dict(re.findall(r'(\w+):\s*"([^"]*)"', body))
        out[code] = (f.get("label", ""), f.get("geo", ""), f.get("store", ""), f.get("wiki", ""))
    return out


def regions_py() -> dict:
    m = re.search(r"^REGIONS = \{(.*?)\n\}", PY.read_text(encoding="utf-8"), re.S | re.M)
    if not m:
        raise SystemExit("REGIONS not found in " + PY.name)
    out = {}
    for code, body in re.findall(r'"(\w+)":\s*\{([^}]*)\}', m.group(1)):
        f = dict(re.findall(r'"(\w+)":\s*"([^"]*)"', body))
        out[code] = (f.get("label", ""), f.get("geo", ""), f.get("store", ""), f.get("wiki", ""))
    return out


def classifiers_js() -> tuple:
    m = re.search(r"const CLASSIFIERS\s*=\s*\[(.*?)\n      \];", HTML.read_text(encoding="utf-8"), re.S)
    if not m:
        raise SystemExit("CLASSIFIERS not found in " + HTML.name)
    return tuple(
        (cat, _js_unescape(pat))
        for cat, pat in re.findall(r'\["([^"]+)",\s*/(.*?)/i\]', m.group(1), re.S)
    )


def classifiers_py() -> tuple:
    m = re.search(r"^CLASSIFIERS = \[(.*?)\n\]", PY.read_text(encoding="utf-8"), re.S | re.M)
    if not m:
        raise SystemExit("CLASSIFIERS not found in " + PY.name)
    out = []
    # ("Cat", r"..." r"...") — the pattern is implicitly concatenated across lines.
    for cat, body in re.findall(r'\("([^"]+)",\s*((?:\s*r"[^"]*")+)\)', m.group(1), re.S):
        out.append((cat, "".join(re.findall(r'r"([^"]*)"', body))))
    return tuple(out)


# ── reporting ─────────────────────────────────────────────────────────────────
def compare_sets(label: str, js: set, py: set) -> bool:
    if js == py:
        print(f"  OK    {label}: {len(js)} terms, in sync")
        return True
    print(f"  DRIFT {label}:")
    for t in sorted(js - py):
        print(f"         only in ad-studio.html : {t}")
    for t in sorted(py - js):
        print(f"         only in fetch_trends.py: {t}")
    return False


def compare_seq(label: str, js, py) -> bool:
    """Order matters here: CLASSIFIERS are first-match-wins, so a reordering
    changes which bucket an item lands in even with identical members."""
    if tuple(js) == tuple(py):
        print(f"  OK    {label}: {len(js)} entries, in sync")
        return True
    print(f"  DRIFT {label}:")
    for i in range(max(len(js), len(py))):
        a = js[i] if i < len(js) else None
        b = py[i] if i < len(py) else None
        if a != b:
            print(f"         [{i}] ad-studio.html={a!r}")
            print(f"             fetch_trends.py={b!r}")
    return False


def compare_maps(label: str, js: dict, py: dict) -> bool:
    if js == py:
        print(f"  OK    {label}: {len(js)} categories, in sync")
        return True
    print(f"  DRIFT {label}:")
    for k in sorted(set(js) | set(py)):
        if js.get(k) != py.get(k):
            print(f"         {k}: ad-studio.html={list(js.get(k, []))} fetch_trends.py={list(py.get(k, []))}")
    return False


def main() -> int:
    print("browser / CI parity check")
    ok = compare_sets("BLOCK", from_js("TREND_BLOCK"), from_py("BLOCK"))
    ok &= compare_sets("ALLOW", from_js("TREND_ALLOW"), from_py("ALLOW"))
    ok &= compare_sets("KW_STOP", kwstop_js(), kwstop_py())
    js_fmt, js_def = formats_js()
    py_fmt, py_def = formats_py()
    ok &= compare_maps("FORMATS", js_fmt, py_fmt)
    ok &= compare_sets("DEFAULT_FORMATS", set(js_def), set(py_def))
    ok &= compare_seq("CATEGORIES", categories_js(), categories_py())
    ok &= compare_maps("REGIONS", regions_js(), regions_py())
    ok &= compare_seq("CLASSIFIERS", classifiers_js(), classifiers_py())
    if not ok:
        print(
            "\nThe browser and CI copies disagree. Update BOTH ad-studio.html and "
            "scripts/fetch_trends.py so the published feed can never be laxer than "
            "the page, nor derive a different hashtag for the same trend.",
            file=sys.stderr,
        )
        return 1
    print("in sync — the published feed matches what the page would compute itself.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
