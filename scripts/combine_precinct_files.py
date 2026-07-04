#!/usr/bin/env python3
"""
Combine per-county precinct CSV files into a single statewide precinct file.

Looks in <year>/counties/ for files matching <election>__*__precinct.csv and
concatenates them into <year>/<election>__precinct.csv.

Usage:
    python scripts/combine_precinct_files.py 20200602__sd__primary
"""
import argparse
import glob
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(
        description="Combine per-county precinct CSV files into one statewide precinct file."
    )
    parser.add_argument("election", help="Election id, e.g. 20200602__sd__primary")
    args = parser.parse_args()

    year = args.election[:4]
    year_dir = REPO / year
    if not year_dir.is_dir():
        sys.exit(f"ERROR: no such year folder '{year_dir}'")

    pattern = str(year_dir / "counties" / f"{args.election}__*__precinct.csv")
    county_files = sorted(glob.glob(pattern))
    if not county_files:
        sys.exit(f"ERROR: no county precinct files found matching '{pattern}'")

    frames = [pd.read_csv(f) for f in county_files]
    combined = pd.concat(frames, ignore_index=True)

    out_path = year_dir / f"{args.election}__precinct.csv"
    combined.to_csv(out_path, index=False)
    print(f"Combined {len(county_files)} county files into {out_path} ({len(combined)} rows)")


if __name__ == "__main__":
    main()
