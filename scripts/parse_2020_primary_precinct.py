#!/usr/bin/env python3
"""Parse the SD 2020 primary precinct canvass PDFs (2020/sources/*.pdf -- four
regional scans, each covering an alphabetical range of counties) using pdfplumber's
table grid, adapting the approach in scripts/parse_2022_precinct.py to this simpler
layout: one contest per page, precincts as rows, candidates as columns, contests may
span consecutive pages (large counties like Minnehaha). Unlike the 2022 canvass,
party isn't glued into the candidate cell -- it's its own header row -- and there's
no county-level totals CSV for the 2020 primary to validate against, so each contest
is instead checked against its own (possibly multi-page) "Total" row.

Usage:
    python scripts/parse_2020_primary_precinct.py
"""
import csv
import glob
import re
from collections import defaultdict
from pathlib import Path

import pdfplumber

REPO = Path(__file__).resolve().parents[1]
SOURCES = REPO / "2020/sources"
OUTDIR = REPO / "2020/counties"
ELECTION = "20200602__sd__primary"

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
    """Join a multi-line candidate cell into one name. A line ending in a
    hyphen glued to a word character is a mid-word wrap ('Vander-\\nWoude') --
    join with no space. A short all-lowercase continuation with no hyphen
    ('VanderWoud\\ne') is also a mid-word wrap in this source; everything else
    (e.g. a wrapped nickname or last name) joins with a space."""
    if not text:
        return ''
    parts = text.split('\n')
    out = parts[0]
    for p in parts[1:]:
        if re.search(r'\w-$', out) or re.match(r'^-\S', p):
            out += p
        elif re.match(r'^[a-z]{1,4}$', p) and out and out[-1].isalpha():
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
    m = re.search(r'^State Senator District (\w+)$', t)
    if m:
        d = m.group(1)
        return "State Senate", (str(int(d)) if d.isdigit() else d)
    m = re.search(r'^State Representative District (\w+)$', t)
    if m:
        d = m.group(1)
        return "State Representative", (str(int(d)) if d.isdigit() else d)
    return None  # local/other race -- kept as-is, not dropped (see main loop)


def normalize_precinct(p):
    """Strip the redundant 'Precinct' label, including inside combined-precinct
    parentheticals like '0104 (Precinct- 0105)' -> '0104 (0105)'. A purely
    numeric precinct number also has its leading zeros stripped ('0103' ->
    '103'), matching this repo's existing convention for plain precincts
    (combined precincts like '0104 (0105)' keep their zero-padding)."""
    p = re.sub(r'Precinct[\s\-_]*', '', p, flags=re.I)
    p = re.sub(r'\s+', ' ', p).strip()
    if p.isdigit():
        p = str(int(p))
    return p or "?"


def find_header(table):
    for i, row in enumerate(table):
        for j, cell in enumerate(row):
            if cell and cell.strip() == 'Precinct Name':
                return i, j
    return None, None


def forward_fill(row):
    out = list(row)
    for k in range(1, len(out)):
        if not out[k]:
            out[k] = out[k - 1]
    return out


def parse_page(page):
    """Return (county, [(office, district, [(party, candidate), ...],
    {precinct: [votes]}, [total_or_None, ...])]) or None if this isn't a
    contest results page."""
    text = page.extract_text() or ''
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    county = None
    for l in lines:
        if l.endswith(' County'):
            cand = l[:-len(' County')].strip()
            if cand.lower() in COUNTIES:
                county = COUNTIES[cand.lower()]
            break
    if not county:
        return None

    tables = page.extract_tables()
    if not tables:
        return None
    table = max(tables, key=lambda t: len(t) * len(t[0]) if t and t[0] else 0)
    hi, hj = find_header(table)
    if hi is None or hi + 2 >= len(table):
        return None

    office_row = forward_fill(table[hi][hj:])
    party_row = forward_fill(table[hi + 1][hj:]) if hi + 1 < len(table) else []
    cand_row = table[hi + 2][hj:] if hi + 2 < len(table) else []

    cols = []  # (col_idx, office, district, party, candidate)
    for k in range(1, len(office_row)):
        office_text = office_row[k]
        if not office_text:
            continue
        raw_cand = cand_row[k] if k < len(cand_row) else ''
        cname = join_name_lines(raw_cand)
        if not cname:
            continue  # phantom column (table-extraction artifact)
        raw_party = party_row[k] if k < len(party_row) else ''
        party = PARTY_MAP.get(clean(raw_party), clean(raw_party))
        norm = normalize_office(office_text)
        office, district = norm if norm else (clean(office_text), "")
        cols.append((k, office, district, party, cname))

    rows = []  # (precinct, {col_idx: votes})
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
        prec = normalize_precinct(clean(name))
        vals = {}
        for k in range(1, len(row)):
            v = row[k]
            if v and INT_RE.match(v.strip()):
                vals[k] = int(v.replace(',', ''))
        rows.append((prec, vals))

    by_key = defaultdict(list)
    for (k, office, district, party, cname) in cols:
        by_key[(office, district)].append((k, party, cname))

    contests = []
    for (office, district), colinfo in by_key.items():
        ks = [k for k, _, _ in colinfo]
        candidates = [(party, cname) for _, party, cname in colinfo]
        precinct_votes = {}
        for prec, vals in rows:
            row_vals = [vals.get(k) for k in ks]
            if all(v is None for v in row_vals):
                continue
            precinct_votes[prec] = row_vals
        total = None
        if total_vals is not None:
            total = []
            for k in ks:
                v = total_vals[k] if k < len(total_vals) else None
                total.append(int(v.replace(',', '')) if v and INT_RE.match(v.strip()) else None)
        contests.append((office, district, candidates, precinct_votes, total))

    return county, contests


def slug(c):
    return c.lower().replace(' ', '_')


def main():
    # (county, office, district) -> {'candidates': [(party,cname)], 'rows': {prec: [votes]}, 'total': [...]}
    merged = {}
    order = []
    key_mismatch_warnings = []

    for pdf_path in sorted(glob.glob(str(SOURCES / "*.pdf"))):
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                result = parse_page(page)
                if not result:
                    continue
                county, contests = result
                for office, district, candidates, precinct_votes, total in contests:
                    key = (county, office, district)
                    if key not in merged:
                        merged[key] = {'candidates': candidates, 'rows': {}, 'total': None}
                        order.append(key)
                    m = merged[key]
                    if len(candidates) != len(m['candidates']):
                        key_mismatch_warnings.append((Path(pdf_path).name, key,
                                                       m['candidates'], candidates))
                        continue
                    m['rows'].update(precinct_votes)
                    if total is not None:
                        m['total'] = total

    out_by_county = defaultdict(list)
    ok = 0
    mismatches = []

    for key in order:
        county, office, district = key
        m = merged[key]
        candidates = m['candidates']
        ncols = len(candidates)
        colsum = [0] * ncols
        for vals in m['rows'].values():
            for idx in range(ncols):
                if vals[idx] is not None:
                    colsum[idx] += vals[idx]
        total = m['total']
        valid = total is not None and len(total) == ncols and all(
            total[idx] == colsum[idx] for idx in range(ncols))
        if not valid:
            mismatches.append((key, candidates, colsum, total))
            continue
        ok += 1
        for prec, vals in m['rows'].items():
            for idx, (party, cname) in enumerate(candidates):
                v = vals[idx]
                if v is None:
                    continue
                out_by_county[county].append([county, prec, office, district, cname, party, v])

    OUTDIR.mkdir(exist_ok=True)
    for county, out_rows in out_by_county.items():
        with open(OUTDIR / f"{ELECTION}__{slug(county)}__precinct.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["county", "precinct", "office", "district", "candidate", "party", "votes"])
            w.writerows(out_rows)

    print(f"contests reconciled to Total: {ok} / {ok + len(mismatches)}")
    print(f"counties written: {len(out_by_county)}")
    print(f"output rows: {sum(len(v) for v in out_by_county.values())}")
    for key, candidates, colsum, total in mismatches:
        print("   MISMATCH", key, "candidates", candidates, "colsum", colsum, "total", total)
    for w in key_mismatch_warnings:
        print("   COLUMN-COUNT MISMATCH across pages", w[0], w[1])


if __name__ == "__main__":
    main()
