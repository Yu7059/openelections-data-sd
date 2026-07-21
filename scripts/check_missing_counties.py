"""
Checks precinct files against a county file and reports any counties
in the county file that are missing from the precinct results.

Usage:
    # Single statewide precinct file:
    python scripts/check_missing_counties.py 2020/20201103__sd__general__county.csv \
        2020/20201103__sd__general__precinct.csv

    # Directory of individual county precinct files:
    python scripts/check_missing_counties.py 2024/20240604__sd__primary__county.csv \
        2024/counties/20240604__sd__primary__*__precinct.csv
"""

import argparse
import glob
import sys
import warnings
warnings.filterwarnings('ignore')

import pandas as pd


def load_precinct_data(paths):
    """Load one or more precinct CSV files and return a combined DataFrame."""
    frames = []
    for path in paths:
        expanded = glob.glob(path)
        if not expanded:
            print(f"WARNING: no files matched '{path}'", file=sys.stderr)
            continue
        for f in expanded:
            frames.append(pd.read_csv(f))
    if not frames:
        sys.exit("ERROR: no precinct files could be loaded.")
    return pd.concat(frames, ignore_index=True)


def main():
    parser = argparse.ArgumentParser(
        description="Report counties missing from precinct results."
    )
    parser.add_argument("county_file", help="Path to the county-level CSV file.")
    parser.add_argument(
        "precinct_files",
        nargs="+",
        help="Path(s) to precinct CSV file(s). Glob patterns are supported.",
    )
    args = parser.parse_args()

    county_df = pd.read_csv(args.county_file)
    if "county" not in county_df.columns:
        sys.exit("ERROR: county file must have a 'county' column.")

    precinct_df = load_precinct_data(args.precinct_files)
    if "county" not in precinct_df.columns:
        sys.exit("ERROR: precinct file(s) must have a 'county' column.")

    county_names = set(county_df["county"].dropna().unique())
    precinct_names = set(precinct_df["county"].dropna().unique())

    missing = sorted(county_names - precinct_names)
    extra = sorted(precinct_names - county_names)

    print(f"Counties in county file:   {len(county_names)}")
    print(f"Counties in precinct data: {len(precinct_names)}")
    print()

    if missing:
        print(f"Missing from precinct data ({len(missing)}):")
        for name in missing:
            print(f"  {name}")
    else:
        print("No counties missing from precinct data.")

    if extra:
        print()
        print(f"In precinct data but not county file ({len(extra)}):")
        for name in extra:
            print(f"  {name}")


if __name__ == "__main__":
    main()
