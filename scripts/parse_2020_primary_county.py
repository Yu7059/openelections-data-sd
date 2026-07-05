#!/usr/bin/env python3
"""Parse the SD 2020 primary STATE canvass report/certificate
(2020/sources/2020PrimaryStateCanvassReportandCertificate.pdf) into a
county-level results CSV. This is a clean digital PDF (not scanned) with
real table grids, so -- unlike the 2022 primary sources -- no vision-LLM
pass is needed; pdfplumber's own table extraction is reliable here. Layout
differs from the precinct-level 2020 primary PDFs in one way: several
contests are stacked on the same page (one pdfplumber table per contest)
rather than one contest per page, since counties-as-rows is much more
compact than precincts-as-rows.

Usage:
    python scripts/parse_2020_primary_county.py
"""
import csv
import re
from collections import defaultdict
from pathlib import Path

import pdfplumber

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "2020/sources/2020PrimaryStateCanvassReportandCertificate.pdf"
OUT_CSV = REPO / "2020/20200602__sd__primary__county.csv"

COUNTIES = {c.lower(): c for c in [
 "Aurora","Beadle","Bennett","Bon Homme","Brookings","Brown","Brule","Buffalo","Butte",
 "Campbell","Charles Mix","Clark","Clay","Codington","Corson","Custer","Davison","Day",
 "Deuel","Dewey","Douglas","Edmunds","Fall River","Faulk","Grant","Gregory","Haakon",
 "Hamlin","Hand","Hanson","Harding","Hughes","Hutchinson","Hyde","Jackson","Jerauld",
 "Jones","Kingsbury","Lake","Lawrence","Lincoln","Lyman","Marshall","McCook","McPherson",
 "Meade","Mellette","Miner","Minnehaha","Moody","Oglala Lakota","Pennington","Perkins",
 "Potter","Roberts","Sanborn","Spink","Stanley","Sully","Todd","Tripp","Turner","Union",
 "Walworth","Yankton","Ziebach"]}

PARTY_MAP = {"Republican": "REP", "Democratic": "DEM", "Nonpartisan": ""}
INT_RE = re.compile(r'^[\d,]+$')


def clean(text):
    return re.sub(r'\s+', ' ', (text or '').replace('\n', ' ')).strip()


def join_name_lines(text):
    if not text:
        return ''
    parts = text.split('\n')
    out = parts[0]
    for p in parts[1:]:
        if re.search(r'\w-$', out) or re.match(r'^-\S', p):
            out += p
        else:
            out += ' ' + p
    return re.sub(r'\s+', ' ', out).strip()


def normalize_office(text):
    t = clean(text)
    if t == "President":
        return "President", ""
    if t == "United States Senator":
        return "U.S. Senate", ""
    if t == "United States Representative":
        return "U.S. Representative", "1"
    m = re.match(r'^State Senator District (\w+)$', t)
    if m:
        d = m.group(1)
        return "State Senate", (str(int(d)) if d.isdigit() else d)
    m = re.match(r'^State Representative District (\w+)$', t)
    if m:
        d = m.group(1)
        return "State Representative", (str(int(d)) if d.isdigit() else d)
    return t, ""  # local/other race -- kept as-is, not dropped


def find_header(table):
    for i, row in enumerate(table):
        for j, cell in enumerate(row):
            if cell and cell.strip() == 'County':
                return i, j
    return None, None


def forward_fill(row):
    out = list(row)
    for k in range(1, len(out)):
        if not out[k]:
            out[k] = out[k - 1]
    return out


def parse_table(table):
    """Return a list of (office, district, party, candidate, county, votes)
    rows for one contest's table, or [] if the table isn't a results table
    or fails its own Total-row self-check."""
    hi, hj = find_header(table)
    if hi is None or hi + 2 >= len(table):
        return []

    office_row = forward_fill(table[hi][hj:])
    party_row = forward_fill(table[hi + 1][hj:]) if hi + 1 < len(table) else []
    cand_row = table[hi + 2][hj:] if hi + 2 < len(table) else []

    office, district = normalize_office(office_row[1]) if len(office_row) > 1 else (None, None)
    if not office:
        return []

    cols = []  # (col_idx, party, candidate)
    for k in range(1, len(cand_row)):
        raw_cand = cand_row[k] if k < len(cand_row) else ''
        cname = join_name_lines(raw_cand)
        if not cname:
            continue
        raw_party = party_row[k] if k < len(party_row) else ''
        party = PARTY_MAP.get(clean(raw_party), clean(raw_party))
        cols.append((k, party, cname))

    county_rows = []  # (county, {col_idx: votes})
    total_vals = None
    for raw in table[hi + 3:]:
        row = raw[hj:]
        name = row[0] if row else None
        if not name or not name.strip():
            continue
        name = name.strip()
        if name == 'Total':
            total_vals = row
            continue
        county = COUNTIES.get(name.lower())
        if not county:
            continue
        vals = {}
        for k in range(1, len(row)):
            v = row[k]
            if v and INT_RE.match(v.strip()):
                vals[k] = int(v.replace(',', ''))
        county_rows.append((county, vals))

    ncand = len(cols)
    colsum = [0] * ncand
    for _, vals in county_rows:
        for idx, (k, _, _) in enumerate(cols):
            if k in vals:
                colsum[idx] += vals[k]
    total = []
    if total_vals is not None:
        for k, _, _ in cols:
            v = total_vals[k] if k < len(total_vals) else None
            total.append(int(v.replace(',', '')) if v and INT_RE.match(v.strip()) else None)
    valid = total and len(total) == ncand and all(total[idx] == colsum[idx] for idx in range(ncand))
    if not valid:
        print(f"   MISMATCH {office} {district}: colsum {colsum} total {total}")
        return []

    out = []
    for county, vals in county_rows:
        for idx, (k, party, cname) in enumerate(cols):
            v = vals.get(k)
            if v is None:
                continue
            out.append([county, office, district, party, cname, v])
    return out


def main():
    rows = []
    contests_ok = 0
    contests_seen = 0
    with pdfplumber.open(SRC) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                hi, hj = find_header(table)
                if hi is None:
                    continue
                contests_seen += 1
                out = parse_table(table)
                if out:
                    contests_ok += 1
                    rows.extend(out)

    with open(OUT_CSV, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["county", "office", "district", "party", "candidate", "votes"])
        w.writerows(rows)

    print(f"contests seen: {contests_seen}")
    print(f"contests reconciled to their own Total row: {contests_ok}")
    print(f"-> {OUT_CSV} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
