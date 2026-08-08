"""
check_safety_sync.py — fail the build if the two brand-safety blocklists diverge
===============================================================================
The trend searcher's hard safety rule exists TWICE by necessity: once in
ad-studio.html (TREND_BLOCK / TREND_ALLOW, applied in the browser) and once in
scripts/fetch_trends.py (BLOCK / ALLOW, applied in CI). They cannot share a file
— one is JavaScript shipped to a static page, the other is Python run on a
runner — so the next best thing is to make drift LOUD.

Drift matters: if CI's list is the laxer of the two, trends.json ships topics the
page would have refused, and they reach a user's brief. Per CLAUDE.md brand hard
rules are deterministic, so a silent divergence is a correctness bug, not a nit.

Compares the alternations as SETS, because two equivalent lists are not
byte-identical:
  * the JS list happens to name `shooting` twice,
  * the Python source is an implicitly-concatenated raw string, so the literal
    text carries `r"` prefixes and newlines that are not part of the pattern.
Exits 1 on any difference, printing exactly which terms are unique to which side.
"""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
HTML = ROOT / "ad-studio.html"
PY = ROOT / "scripts" / "fetch_trends.py"


def alternation(pattern: str) -> set:
    """Pull the `\\b( a | b | c )\\b` alternation out of a regex body."""
    m = re.search(r"\\b\((.*?)\)\\b", pattern, re.S)
    if not m:
        raise SystemExit("could not find a \\b(...)\\b alternation in:\n" + pattern[:200])
    return {a.strip() for a in m.group(1).split("|") if a.strip()}


def from_js(name: str) -> set:
    src = HTML.read_text(encoding="utf-8")
    m = re.search(rf"const {name}\s*=\s*\n?\s*/(.*?)/i;", src, re.S)
    if not m:
        raise SystemExit(f"{name} not found in {HTML.name}")
    return alternation(m.group(1))


def from_py(name: str) -> set:
    src = PY.read_text(encoding="utf-8")
    m = re.search(rf"^{name} = re\.compile\(\s*(.*?),\s*re\.I,?\s*\)", src, re.S | re.M)
    if not m:
        raise SystemExit(f"{name} not found in {PY.name}")
    # Rebuild the pattern from the implicitly-concatenated raw string literals.
    body = "".join(re.findall(r'r?"([^"]*)"', m.group(1)))
    return alternation(body)


def compare(label: str, js: set, py: set) -> bool:
    if js == py:
        print(f"  OK   {label}: {len(js)} terms, in sync")
        return True
    print(f"  DRIFT {label}:")
    for t in sorted(js - py):
        print(f"         only in ad-studio.html : {t}")
    for t in sorted(py - js):
        print(f"         only in fetch_trends.py: {t}")
    return False


def main() -> int:
    print("brand-safety blocklist sync check")
    ok = compare("BLOCK", from_js("TREND_BLOCK"), from_py("BLOCK"))
    ok &= compare("ALLOW", from_js("TREND_ALLOW"), from_py("ALLOW"))
    if not ok:
        print(
            "\nThe browser and CI safety rules disagree. Update BOTH "
            "(ad-studio.html TREND_BLOCK/TREND_ALLOW and scripts/fetch_trends.py "
            "BLOCK/ALLOW) so the published feed can never be laxer than the page.",
            file=sys.stderr,
        )
        return 1
    print("in sync — the published feed cannot be laxer than the page.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
