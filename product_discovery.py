"""
Product Discovery Agent — pick the product that matches a segment's interest.
============================================================================
The product is NO LONGER hardcoded. It is retrieved by similarity to the
segment's interest.

INTERIM (now): products are sourced from the internet (the list below was pulled
from a live web search of Starbucks' current fall menu — see source_url on each)
and ranked by overlap with the segment interest.

PRODUCTION (target): replace `discover_candidates()` with the embedding catalog
matcher from the Product-Matching spike (hybrid retrieve+rank over your real
product-description table). The interface returns the same shape, so the rest of
the pipeline doesn't change.
"""
import re

# Web-sourced Starbucks fall products (from a live search; descriptions paraphrased).
# Sources: about.starbucks.com, today.com, axios.com, cozymeal.com (fall 2025 menu).
WEB_PRODUCTS = [
    {
        "product_id": "psl", "name": "Pumpkin Spice Latte", "flavor": "pumpkin spice",
        "tags": ["fall", "seasonal", "pumpkin", "hot", "ritual", "morning", "espresso"],
        "descriptors": "espresso and steamed milk with real pumpkin, cinnamon, nutmeg and clove, "
                       "topped with whipped cream and pumpkin pie spice, in a takeaway cup",
        "centrality": 1.0, "palette": ((0xC9, 0x8A, 0x5E), (0x3A, 0x24, 0x18)),
        "source_url": "https://about.starbucks.com/stories/2025/starbucks-reserve-unveils-fall-menu-with-pumpkin-spice-favorites-and-new-tiramisu-latte/",
    },
    {
        "product_id": "pumpkin_ccb", "name": "Pumpkin Cream Cold Brew", "flavor": "pumpkin cream",
        "tags": ["fall", "seasonal", "pumpkin", "cold", "afternoon", "coldbrew"],
        "descriptors": "smooth cold brew topped with pumpkin cream cold foam and a dusting of pumpkin spice, over ice",
        "centrality": 0.8, "palette": ((0xD8, 0xA8, 0x70), (0x2C, 0x1A, 0x10)),
        "source_url": "https://www.today.com/food/drinks/starbucks-apple-crisp-2025-rcna232129",
    },
    {
        "product_id": "apple_crisp", "name": "Iced Apple Crisp Oatmilk Shaken Espresso", "flavor": "apple crisp",
        "tags": ["fall", "seasonal", "apple", "cold", "oatmilk", "shaken"],
        "descriptors": "blonde espresso with notes of apple, cinnamon and brown sugar, shaken and topped with oatmilk, over ice",
        "centrality": 0.7, "palette": ((0xC9, 0x9A, 0x52), (0x33, 0x22, 0x12)),
        "source_url": "https://www.today.com/food/drinks/starbucks-apple-crisp-2025-rcna232129",
    },
    {
        "product_id": "pecan_latte", "name": "Pecan Crunch Oatmilk Latte", "flavor": "pecan crunch",
        "tags": ["fall", "seasonal", "pecan", "hot", "oatmilk", "morning"],
        "descriptors": "blonde espresso with oat milk, notes of pecan, brown butter and baking spices, topped with pecan crunch",
        "centrality": 0.6, "palette": ((0xC2, 0x96, 0x60), (0x2E, 0x1D, 0x12)),
        "source_url": "https://www.axios.com/2025/08/25/starbucks-pumpkin-spice-latte-2025-fall-menu-release",
    },
]


def _tokens(s):
    return set(re.findall(r"[a-z]+", s.lower()))


def discover_candidates(interest, brand="Starbucks", k=3):
    """Return products ranked by similarity to the segment interest (web-sourced for now)."""
    itok = _tokens(interest)
    scored = []
    for p in WEB_PRODUCTS:
        ptok = _tokens(p["name"] + " " + " ".join(p["tags"]) + " " + p["descriptors"])
        overlap = len(itok & ptok)
        sim = overlap / max(1, len(itok))
        scored.append((sim, overlap, p))
    # rank by interest similarity, breaking ties by how central the product is to the brand
    scored.sort(key=lambda x: (x[0], x[2]["centrality"]), reverse=True)
    out = []
    for sim, ov, p in scored[:k]:
        out.append({**p, "sim": round(sim, 2),
                    "why": f"web-sourced; matched {ov} interest cue(s) ['{interest}']"})
    return out


if __name__ == "__main__":
    for interest in ["fall seasonal ritual morning autumn", "cold afternoon refreshing", "apple cinnamon"]:
        top = discover_candidates(interest)[0]
        print(f"{interest:38s} -> {top['name']} (sim={top['sim']}, {top['source_url'].split('//')[1][:24]}…)")
