#!/usr/bin/env python3
"""Fold scripts/parse_2022_precinct.py's staged output into the committed 2022 files:
- copy each staged per-county precinct CSV into 2022/counties/, overwriting the old
  (geometry-parsed) version -- except for any (office,district) contest that isn't
  present at all in the new digital-table parse (a handful of Minnehaha legislative
  races are simply absent from the digital PDF, not a parsing failure; they were
  originally filled in from the scanned regional PDF via parse_2022_mz.py), which is
  carried over unchanged from the old committed file. Yankton isn't in the digital
  PDF at all, so it's simply absent from staging and its existing committed file is
  left untouched.
- append local-office county totals (scripts/parse_2022_precinct.py validates these
  against each page's Total row before staging them) to the county-level CSV, which
  previously only had the ~17 statewide/legislative/judicial offices.
"""
import csv, shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STAGING = Path("/tmp/sd_2022_precinct_staging")
COUNTIES_DIR = REPO / "2022/counties"
COUNTY_CSV = REPO / "2022/20221108__sd__general__county.csv"

copied = 0
for f in sorted(STAGING.glob("20221108__sd__general__*__precinct.csv")):
    old_path = COUNTIES_DIR / f.name
    with open(f, newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        new_rows = list(reader)
    new_keys = {(r[2], r[3]) for r in new_rows}  # (office, district)
    fallback_rows = []
    if old_path.exists():
        with open(old_path, newline="") as fh:
            old_reader = csv.reader(fh)
            next(old_reader)
            fallback_rows = [r for r in old_reader if (r[2], r[3]) not in new_keys]
    if fallback_rows:
        missing = sorted({(o, d) for _, _, o, d, *_ in fallback_rows})
        print(f"  {f.name}: carrying over {len(fallback_rows)} rows for contests absent "
              f"from the digital parse: {missing}")
    with open(old_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(new_rows)
        w.writerows(fallback_rows)
    copied += 1
print(f"copied {copied} county precinct files into {COUNTIES_DIR}")

with open(COUNTY_CSV, newline="") as fh:
    reader = csv.reader(fh)
    header = next(reader)
    rows = list(reader)

with open(STAGING / "county_local_extra.csv", newline="") as fh:
    extra_reader = csv.reader(fh)
    next(extra_reader)  # header: county,office,district,party,candidate,votes
    extra_rows = list(extra_reader)

with open(COUNTY_CSV, "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(header)
    w.writerows(rows)
    w.writerows(extra_rows)
print(f"appended {len(extra_rows)} local-office rows to {COUNTY_CSV}")
