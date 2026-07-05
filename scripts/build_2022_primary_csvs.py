#!/usr/bin/env python3
"""Turn the validated vision-LLM contest extractions from
scripts/parse_2022_primary_precinct.py (cached as <Source>_contests.json)
into the final per-county precinct CSVs in 2022/counties/, matching this
repo's 2022-general naming/office conventions.

Where a (county, office, district) has more than one contributing page --
either because the source PDF genuinely repeats a small county's results on
a summary page and again on individual pages, or because a page was
misread -- this uses 2022/20220607__sd__primary__county.csv (the official
state canvass, built by scripts/parse_2022_primary_county.py) as ground
truth: it tries every combination of the contributing pages and keeps
whichever one sums to exactly the county file's numbers. That one check
handles three distinct failure modes seen in this dataset: a duplicated
page counted twice, a hallucinated page with fabricated county/precinct
data, and a misread provisional-ballot recording form mistaken for an
aggregate results table -- in each case the "bad" contribution simply
doesn't add up to the certified county total, so it's dropped.

Usage:
    python scripts/build_2022_primary_csvs.py
"""
import csv
import json
import re
from collections import defaultdict
from itertools import combinations
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CACHE = Path.home() / "sd_cache" / "2022_primary"
OUTDIR = REPO / "2022/counties"
COUNTY_CSV = REPO / "2022/20220607__sd__primary__county.csv"
ELECTION = "20220607__sd__primary"
SOURCES = ["AuroraClark", "ClayFaulk", "GrantLyman", "MarshallZiebach"]

PARTY_MAP = {"REP": "REP", "Republican": "REP", "DEM": "DEM", "Democratic": "DEM",
             "Nonpartisan": "", "NON": "", "": ""}

# (source, page) pairs confirmed (by looking at the actual page image) to be
# something other than an aggregate precinct results table, that nonetheless
# produced a self-consistent-looking response -- so colsum_ok() alone can't
# catch them. ClayFaulk page 25 is a provisional/challenged-ballot recording
# form (one row per office for a single physical ballot, "1"/"One" throughout)
# that got misread as if it were Custer County's regular results table.
KNOWN_BAD_PAGES = {("ClayFaulk", 25)}

CONST_AMEND_C = ("Constitutional Amendment C: A Constitutional Amendment Requiring "
                 "Three-Fifths Vote for Approval of Ballot Measures Imposing Taxes "
                 "or Fees or Obligating over $10 Million")


def colsum_ok(c):
    ncand = len(c["candidates"])
    total = c.get("total")
    colsum = [0] * ncand
    for vals in c["precincts"].values():
        if not isinstance(vals, list) or len(vals) != ncand:
            return False
        for idx in range(ncand):
            if isinstance(vals[idx], (int, float)):
                colsum[idx] += vals[idx]
    return isinstance(total, list) and len(total) == ncand and all(
        total[idx] == colsum[idx] for idx in range(ncand))


def looks_like_provisional_ballot_form(c):
    """A single provisional/challenged-ballot recording page (one row per
    office for one physical ballot) can slip past colsum_ok because it's
    internally self-consistent -- every recorded vote is exactly 1. A real
    aggregate contest essentially never has *every* precinct-candidate cell
    equal to 1, so this fingerprint reliably flags that misread page type
    regardless of what office text it ended up labeled with."""
    vals = [v for row in c["precincts"].values() if isinstance(row, list) for v in row if v is not None]
    return len(vals) >= 2 and all(v == 1 for v in vals)


def normalize_office(text):
    t = text.strip()
    if t == "United States Senator":
        return "U.S. Senate", ""
    if t == "United States Representative":
        return "U.S. House", "1"
    if t == "Governor":
        return "Governor", ""
    m = re.match(r'^State Senator District (\w+)$', t)
    if m:
        d = m.group(1)
        return "State Senate", (str(int(d)) if d.isdigit() else d)
    m = re.match(r'^State Representative District (\w+)$', t)
    if m:
        d = m.group(1)
        return "State House", (str(int(d)) if d.isdigit() else d)
    if t.startswith("Constitutional Amendment C"):
        return CONST_AMEND_C, ""
    return t, ""  # local/other race -- kept as-is


def normalize_precinct(p):
    p = re.sub(r'^Precinct[\s\-_]*', '', p, flags=re.I).strip()
    return p or "?"


def norm_candidate(name):
    return re.sub(r'[.\s]+', ' ', name or '').strip().lower()


def slug(c):
    return c.lower().replace(' ', '_')


def load_county_truth():
    """(county, office, district) -> {norm_candidate: votes}"""
    truth = defaultdict(dict)
    with open(COUNTY_CSV) as f:
        for r in csv.DictReader(f):
            key = (r["county"], r["office"], r["district"])
            truth[key][norm_candidate(r["candidate"])] = int(r["votes"])
    return truth


def summed_votes(entries):
    """entries: contest dicts sharing a key. -> {norm_candidate: total_votes}"""
    totals = defaultdict(int)
    for e in entries:
        for vals in e["precincts"].values():
            for idx, cand in enumerate(e["candidates"]):
                v = vals[idx] if idx < len(vals) else None
                if v is not None:
                    totals[norm_candidate(cand)] += v
    return dict(totals)


def matches_truth(entries, truth):
    summed = summed_votes(entries)
    return set(summed) == set(truth) and all(summed[k] == truth[k] for k in truth)


def resolve_against_truth(group, truth):
    """Try every combination of contributing pages, largest first, and keep
    the first (most complete) one whose total matches the county file
    exactly. Returns (kept_entries, note) or (None, note) if none match."""
    for r in range(len(group), 0, -1):
        for subset in combinations(group, r):
            if matches_truth(subset, truth):
                dropped = [e for e in group if e not in subset]
                note = None
                if dropped:
                    note = f"kept {len(subset)}/{len(group)} contributing page(s), " \
                            f"dropped {[(e['source'], e['page']) for e in dropped]}"
                return list(subset), note
    return None, f"no combination of {[(e['source'], e['page']) for e in group]} matches county total"


def resolve_without_truth(group):
    """No county-file entry for this (local) contest -- fall back to
    signature/overlap-based de-dup, using normalized precinct names so a
    precinct that's merely labeled differently between two pages
    ('Foo Township' vs 'County Foo Township') is still recognized as the
    same precinct rather than silently double-counted."""
    seen_sigs = set()
    uniq = []
    for c in group:
        sig = json.dumps([c["candidates"], c["precincts"], c["total"]], sort_keys=True)
        if sig not in seen_sigs:
            seen_sigs.add(sig)
            uniq.append(c)
    if len(uniq) == 1:
        return uniq, None
    precinct_sets = [{normalize_precinct(p) for p in c["precincts"]} for c in uniq]
    overlap = any(precinct_sets[i] & precinct_sets[j]
                  for i in range(len(precinct_sets)) for j in range(i + 1, len(precinct_sets)))
    if overlap:
        return None, f"conflicting duplicates, no county total to arbitrate: " \
                      f"{[(c['source'], c['page']) for c in uniq]}"
    return uniq, None


def main():
    truth = load_county_truth()

    all_contests = []
    for src in SOURCES:
        path = CACHE / f"{src}_contests.json"
        if not path.exists():
            print(f"WARNING: missing {path}, skipping")
            continue
        for c in json.load(open(path)):
            if (src, c.get("page")) in KNOWN_BAD_PAGES:
                continue
            if colsum_ok(c) and not looks_like_provisional_ballot_form(c):
                c["source"] = src
                all_contests.append(c)

    by_key = defaultdict(list)
    for c in all_contests:
        office, district = normalize_office(c["office"])
        by_key[(c["county"], office, district)].append(c)

    kept = []
    dropped_notes = []
    for key, group in by_key.items():
        county, office, district = key
        t = truth.get(key)
        if t is not None:
            resolved, note = resolve_against_truth(group, t)
        else:
            resolved, note = resolve_without_truth(group)
        if note:
            dropped_notes.append((key, note))
        if resolved:
            kept.append((key, resolved))

    out_by_county = defaultdict(list)
    for (county, office, district), entries in kept:
        for c in entries:
            party = PARTY_MAP.get(c.get("party"), c.get("party") or "")
            for prec, vals in c["precincts"].items():
                prec_norm = normalize_precinct(prec)
                for idx, cand in enumerate(c["candidates"]):
                    v = vals[idx] if idx < len(vals) else None
                    if v is None:
                        continue
                    out_by_county[county].append(
                        [county, prec_norm, office, district, cand, party, v])

    OUTDIR.mkdir(exist_ok=True)
    # Start from a clean slate -- a county that had output on a previous run
    # but has none now (e.g. its only source page turned out to be bad and
    # got dropped) should not leave a stale file behind.
    for f in OUTDIR.glob(f"{ELECTION}__*__precinct.csv"):
        f.unlink()
    for county, rows in out_by_county.items():
        with open(OUTDIR / f"{ELECTION}__{slug(county)}__precinct.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["county", "precinct", "office", "district", "candidate", "party", "votes"])
            w.writerows(rows)

    print(f"validated (self-consistent) contests: {len(all_contests)}")
    print(f"(county, office, district) groups: {len(by_key)}")
    print(f"groups kept: {len(kept)}")
    print(f"groups dropped or trimmed: {len(dropped_notes)}")
    for key, note in dropped_notes:
        print("  ", key, "--", note)
    print(f"counties written: {len(out_by_county)}")
    print(f"total rows: {sum(len(v) for v in out_by_county.values())}")


if __name__ == "__main__":
    main()
