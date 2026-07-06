"""
make_demo_customers.py — synthetic customer database for the Ad Studio demo
===========================================================================
Generates demo-customers.csv (~2000 rows) the studio's CSV upload can segment.

Design: the population is drawn from 8 hand-designed ARCHETYPES (very different
ages / genders / cities / interests / spend / visit habits) plus 6% "wildcard"
rows of pure noise. Each archetype samples with jitter, so clusters are
discoverable but realistically fuzzy — the point is to exercise the studio's
k-means persona detection, not to hand it the answer.

Deterministic (seed 7): re-running reproduces the same file.
Columns: name, age, gender, city, interest, monthly_spend, visits_per_week
(the studio z-scores the numeric columns and one-hot-encodes
gender/city/interest for clustering; `name` is ignored).
"""

import csv
import random

random.seed(7)

# archetype: (share, age_range, genders(weighted), cities, interests, spend_range, visits_range)
ARCHETYPES = [
    # 1 · urban young women — specialty coffee as a ritual
    (0.16, (22, 32), [("Female", 0.86), ("Nonbinary", 0.08), ("Male", 0.06)],
     ["London", "Seattle", "Melbourne"], ["specialty coffee", "cozy rituals"], (38, 70), (4, 7)),
    # 2 · suburban men — home-office espresso upgraders
    (0.14, (35, 52), [("Male", 0.88), ("Female", 0.12)],
     ["Manchester", "Denver", "Stuttgart"], ["espresso gear", "home office"], (60, 120), (1, 3)),
    # 3 · students — iced drinks, study cafes
    (0.15, (18, 24), [("Female", 0.5), ("Male", 0.42), ("Nonbinary", 0.08)],
     ["Leeds", "Austin", "Toronto"], ["iced drinks", "study cafes"], (12, 30), (4, 7)),
    # 4 · retirees — tea and classic roast, weekday mornings
    (0.11, (60, 75), [("Female", 0.52), ("Male", 0.48)],
     ["Bath", "Portland", "Kyoto"], ["tea", "classic roast"], (18, 40), (2, 5)),
    # 5 · young professional men — cold brew + fitness
    (0.13, (25, 34), [("Male", 0.84), ("Nonbinary", 0.06), ("Female", 0.10)],
     ["New York", "Singapore", "Berlin"], ["cold brew", "fitness"], (45, 85), (3, 6)),
    # 6 · parents — decaf, pastries, weekend family treats
    (0.12, (30, 45), [("Female", 0.68), ("Male", 0.32)],
     ["Bristol", "Minneapolis", "Utrecht"], ["decaf", "weekend treats"], (30, 60), (1, 3)),
    # 7 · remote creatives — matcha, plant-based milks
    (0.10, (25, 40), [("Nonbinary", 0.34), ("Female", 0.4), ("Male", 0.26)],
     ["Lisbon", "Mexico City", "Bali"], ["matcha", "plant-based"], (28, 55), (3, 6)),
    # 8 · business travellers — espresso to go, loyalty points
    (0.09, (30, 55), [("Male", 0.6), ("Female", 0.4)],
     ["Dubai", "Chicago", "Frankfurt"], ["espresso to go", "loyalty offers"], (70, 140), (1, 4)),
]
WILDCARD = 0.06  # pure-noise rows: real databases always have them

ALL_CITIES = sorted({c for a in ARCHETYPES for c in a[3]})
ALL_INTERESTS = sorted({i for a in ARCHETYPES for i in a[4]})
FIRST = ["Alex", "Sam", "Jordan", "Riley", "Casey", "Maya", "Noah", "Ava", "Leo", "Iris",
         "Owen", "Zara", "Eli", "Nina", "Kai", "Ruth", "Hugo", "Lena", "Omar", "June"]
LAST = ["Kim", "Patel", "Garcia", "Chen", "Okafor", "Novak", "Silva", "Haas", "Ito", "Larsen",
        "Moreau", "Reyes", "Byrne", "Sato", "Ali", "Weber", "Costa", "Nash", "Vega", "Lund"]


def weighted(pairs):
    r, acc = random.random(), 0.0
    for value, w in pairs:
        acc += w
        if r <= acc:
            return value
    return pairs[-1][0]


def make_row(i, arch):
    if arch is None:  # wildcard noise
        age = random.randint(18, 75)
        gender = random.choice(["Female", "Male", "Nonbinary"])
        city = random.choice(ALL_CITIES)
        interest = random.choice(ALL_INTERESTS)
        spend = round(random.uniform(10, 140), 2)
        visits = random.randint(0, 7)
    else:
        _, (a0, a1), genders, cities, interests, (s0, s1), (v0, v1) = arch
        age = max(18, min(80, round(random.gauss((a0 + a1) / 2, (a1 - a0) / 4))))
        gender = weighted(genders)
        city = random.choice(cities)
        interest = random.choice(interests)
        spend = round(random.uniform(s0, s1) * random.uniform(0.85, 1.15), 2)
        visits = max(0, min(7, round(random.gauss((v0 + v1) / 2, 1))))
    name = f"{random.choice(FIRST)} {random.choice(LAST)}"
    return [name, age, gender, city, interest, spend, visits]


def main(n=2000, out="demo-customers.csv"):
    rows = []
    for i in range(n):
        r = random.random()
        if r < WILDCARD:
            rows.append(make_row(i, None))
        else:
            r = (r - WILDCARD) / (1 - WILDCARD)
            acc = 0.0
            arch = ARCHETYPES[-1]
            for a in ARCHETYPES:
                acc += a[0]
                if r <= acc:
                    arch = a
                    break
            rows.append(make_row(i, arch))
    random.shuffle(rows)
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["name", "age", "gender", "city", "interest", "monthly_spend", "visits_per_week"])
        w.writerows(rows)
    print(f"wrote {out}: {len(rows)} rows, {len(ARCHETYPES)} archetypes + {int(WILDCARD*100)}% noise")


if __name__ == "__main__":
    main()
