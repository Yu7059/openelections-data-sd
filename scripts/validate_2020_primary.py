#!/usr/bin/env python3
"""Cross-check the 2020 SD primary county-level canvass
(2020/20200602__sd__primary__county.csv, built by
scripts/parse_2020_primary_county.py from the official state canvass PDF)
against the precinct-level results (2020/20200602__sd__primary__precinct.csv,
built from scripts/parse_2020_primary_precinct.py's per-county output via
scripts/combine_precinct_files.py).

Reports two kinds of problems:
- MISSES: a (county, office, district) the county file has data for, but
  that's entirely absent from the precinct-level file (e.g. Douglas and
  Lincoln, which aren't in the precinct source PDFs at all).
- DISCREPANCIES: a (county, office, district, candidate) present in both,
  where summing the precinct-level votes doesn't match the county file's
  reported total for that candidate.

Usage:
    python scripts/validate_2020_primary.py
"""
import csv
import re
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
COUNTY_CSV = REPO / "2020/20200602__sd__primary__county.csv"
PRECINCT_CSV = REPO / "2020/20200602__sd__primary__precinct.csv"
OUT_CSV = REPO / "2020/discrepancies_2020_primary.csv"


def norm_candidate(name):
    """Loosen candidate-name matching across the two independently-extracted
    files (periods, extra whitespace, and case shouldn't cause a false
    mismatch -- e.g. 'Paul R Miskimins' vs 'Paul R. Miskimins')."""
    return re.sub(r'[.\s]+', ' ', name or '').strip().lower()


def load_county(path):
    """(county, office, district) -> {norm_candidate: (orig_candidate, party, votes)}"""
    data = defaultdict(dict)
    with open(path) as f:
        for r in csv.DictReader(f):
            key = (r["county"], r["office"], r["district"])
            data[key][norm_candidate(r["candidate"])] = (r["candidate"], r["party"], int(r["votes"]))
    return data


def load_precinct(path):
    """(county, office, district) -> {norm_candidate: (orig_candidate, party, summed_votes)}"""
    data = defaultdict(lambda: defaultdict(lambda: [None, None, 0]))
    with open(path) as f:
        for r in csv.DictReader(f):
            key = (r["county"], r["office"], r["district"])
            nc = norm_candidate(r["candidate"])
            v = r["votes"].strip()
            entry = data[key][nc]
            entry[0] = r["candidate"]
            entry[1] = r["party"]
            entry[2] += int(v) if v else 0
    return data


def main():
    county = load_county(COUNTY_CSV)
    precinct = load_precinct(PRECINCT_CSV)

    misses = []
    discrepancies = []

    for key in sorted(county):
        county_name, office, district = key
        c_cands = county[key]
        p_cands = precinct.get(key)
        if p_cands is None:
            for nc, (cand, party, votes) in c_cands.items():
                misses.append([county_name, office, district, cand, party, votes, ""])
            continue
        for nc, (cand, party, c_votes) in c_cands.items():
            if nc not in p_cands:
                discrepancies.append([county_name, office, district, cand, party,
                                       c_votes, "", c_votes])
                continue
            _, _, p_votes = p_cands[nc]
            if c_votes != p_votes:
                discrepancies.append([county_name, office, district, cand, party,
                                       c_votes, p_votes, c_votes - p_votes])

    with open(OUT_CSV, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["county", "office", "district", "candidate", "party",
                    "county_votes", "precinct_votes", "diff"])
        w.writerows(discrepancies)

    contest_keys = sorted(county)
    missed_contests = sorted({(c, o, d) for c, o, d, *_ in misses})
    print(f"contests in county file: {len(contest_keys)}")
    print(f"contests entirely missing from precinct file: {len(missed_contests)}")
    for c, o, d in missed_contests:
        print(f"   MISS  {c} / {o} / {d}")
    print(f"\ncandidate-level discrepancies (present in both, vote counts differ): {len(discrepancies)}")
    for row in discrepancies:
        print("   DIFF ", row)
    print(f"\n-> {OUT_CSV}")


if __name__ == "__main__":
    main()
