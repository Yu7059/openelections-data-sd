#!/usr/bin/env python3
"""Parse the SD 2022 general precinct canvass (clean digital PDF, one contest per page,
contests may span consecutive pages) using the PDF's own table grid (pdfplumber
extract_tables) instead of text-line heuristics. The grid gives us, per page: the office
(+district) header, the candidate/party header, and precinct-name cells that are already
correctly reassembled even when a name wraps across 2-3 lines (e.g. "Best Western Ramkota
Hotel and Convention Center"). Because candidate names and parties live in the header
cells, columns are labeled directly from the page -- no matching against county-level
totals is needed to identify them, which means local contests (county commissioner,
conservation-district referendums, etc.) are captured too, not just the ~17 statewide/
legislative/judicial races. County-file totals are still used, but only as a validation
check after the fact."""
import os, re, csv
from pathlib import Path
from collections import defaultdict
import pdfplumber

REPO = Path(__file__).resolve().parents[1]
SOURCES = Path(os.environ.get("SD_SOURCES", REPO / "sources"))
PREC_PDF = str(SOURCES / "2022PrecintCanvass.pdf")
COUNTY_CSV = str(REPO / "2022/20221108__sd__general__county.csv")
# Output goes to a staging dir; scripts/merge_2022_precinct.py folds it into 2022/counties,
# preserving Yankton (absent from this PDF) and any Minnehaha legislative contests that
# still don't reconcile digitally.
OUTDIR = os.environ.get("SD_PRECINCT_OUT", "/tmp/sd_2022_precinct_staging")

COUNTIES = {c.lower(): c for c in [
 "Aurora","Beadle","Bennett","Bon Homme","Brookings","Brown","Brule","Buffalo","Butte",
 "Campbell","Charles Mix","Clark","Clay","Codington","Corson","Custer","Davison","Day",
 "Deuel","Dewey","Douglas","Edmunds","Fall River","Faulk","Grant","Gregory","Haakon",
 "Hamlin","Hand","Hanson","Harding","Hughes","Hutchinson","Hyde","Jackson","Jerauld",
 "Jones","Kingsbury","Lake","Lawrence","Lincoln","Lyman","Marshall","McCook","McPherson",
 "Meade","Mellette","Miner","Minnehaha","Moody","Oglala Lakota","Pennington","Perkins",
 "Potter","Roberts","Sanborn","Spink","Stanley","Sully","Todd","Tripp","Turner","Union",
 "Walworth","Yankton","Ziebach"]}

PARTY = r'(DEM|REP|LIB|IND|NON|CON|NPA|UNF)'
CAND_RE = re.compile(r'^(.*?)\s*-\s*' + PARTY + r'$')
INT_RE = re.compile(r'^[\d,]+$')
ORD = {"First":"1","Second":"2","Third":"3","Fourth":"4","Fifth":"5","Sixth":"6",
       "Seventh":"7","Eighth":"8","Ninth":"9"}

def join_cell_lines(text):
    """Join a multi-line table cell's lines into one string. A line ending in a
    hyphen glued to a word character (e.g. 'Frye-') is a mid-word wrap -- join
    directly with no space so it becomes 'Frye-Mueller'. A line ending in ' -'
    (hyphen as its own token, the 'Name - PARTY' separator) keeps its space."""
    if not text:
        return ''
    parts = text.split('\n')
    out = parts[0]
    for p in parts[1:]:
        if re.search(r'\w-$', out) or re.match(r'^-\S', p):
            out += p
        else:
            out += ' ' + p
    return out

ORPHAN_LETTER_RE = re.compile(r'\b([A-Z]) (?=[a-z])')

def clean(text):
    t = re.sub(r'\s+', ' ', join_cell_lines(text or '')).strip()
    return ORPHAN_LETTER_RE.sub(r'\1', t)

def normalize_office(text):
    t = clean(text)
    if re.search(r'United States Senator', t): return "U.S. Senate", ""
    if re.search(r'United States Representative', t): return "U.S. House", "1"
    if re.search(r'Governor and Lieutenant Governor', t): return "Governor", ""
    if re.search(r'Secretary of State', t): return "Secretary of State", ""
    if re.search(r'Attorney General', t): return "Attorney General", ""
    if re.search(r'State Auditor', t): return "State Auditor", ""
    if re.search(r'State Treasurer', t): return "State Treasurer", ""
    if re.search(r'Commissioner of School and Public Lands', t):
        return "Commissioner of School and Public Lands", ""
    if re.search(r'Public Utilities Commissioner', t): return "Public Utilities Commissioner", ""
    m = re.search(r'State Senator District (\w+)', t)
    if m: return "State Senate", m.group(1)
    m = re.search(r'State Representative District (\w+)', t)
    if m: return "State House", m.group(1)
    m = re.search(r'Judge of the Circuit Court,\s*(Position \w+ \w+ Circuit)', t)
    if m: return "Judge of the Circuit Court", m.group(1)
    if re.search(r'Supreme Court Justice Retention', t):
        dm = re.search(r'the (\w+) Supreme Court District', t)
        return "Supreme Court Retention", (ORD.get(dm.group(1), "") if dm else "")
    m = re.search(r'Constitutional Amendment ([A-Z])\b', t)
    if m: return f"Constitutional Amendment {m.group(1)}", ""
    m = re.search(r'Initiated Measure (\d+)\b', t)
    if m: return f"Initiated Measure {m.group(1)}", ""
    m = re.search(r'Referred Law (\d+)\b', t)
    if m: return f"Referred Law {m.group(1)}", ""
    if re.search(r'James River Water Development District', t):
        return "James River Water Development District", ""
    # tolerant fallback for headers wrapped mid-word ('State Representati ve District 26B')
    flat = re.sub(r'\s+', '', t)
    m = re.search(r'StateSenatorDistrict(\d+[AB]?)', flat)
    if m: return "State Senate", m.group(1)
    m = re.search(r'StateRepresentativeDistrict(\d+[AB]?)', flat)
    if m: return "State House", m.group(1)
    return None  # unknown / local -- kept, not dropped (see main loop)

def retention_name(text):
    """Extract the justice's name for retention races, to match the county-file
    convention of encoding the yes/no choice into the candidate field."""
    t = clean(text)
    m = re.search(r'Shall Justice (.+?) representing the \w+ Supreme Court District', t)
    return m.group(1).strip() if m else None

def normalize_precinct(p):
    p = re.sub(r'^Precinct[\s\-_]+', '', p, flags=re.I).strip()
    return p or "?"

def parse_candidate_cell(text):
    t = clean(text)
    if t in ('Yes', 'No'):
        return t, ''
    m = CAND_RE.match(t)
    if m: return m.group(1).strip(), m.group(2)
    return t, ''

def find_header(table):
    """Locate the (row, col) of the 'Precinct Name' cell. Pages can carry a garbage
    lead row (the whole page's text flattened into one cell -- an artifact of
    multi-page contests where the outer border rect and the real grid overlap);
    searching for the literal header cell skips past it automatically."""
    for i, row in enumerate(table):
        for j, cell in enumerate(row):
            if cell and cell.strip() == 'Precinct Name':
                return i, j
    return None, None

def forward_fill(row):
    """District/office labels span multiple candidate columns as one merged cell;
    pdfplumber represents that as the label then None for the spanned columns."""
    out = list(row)
    for k in range(1, len(out)):
        if not out[k]:
            out[k] = out[k - 1]
    return out

# ---- load county totals: (county,office,district) -> [(candidate,party,total)] ----
cf = defaultdict(list)
with open(COUNTY_CSV) as f:
    for r in csv.DictReader(f):
        cf[(r['county'], r['office'], r['district'])].append(
            (r['candidate'], r['party'], int(r['votes'])))

pdf = pdfplumber.open(PREC_PDF)
merged = {}   # (county,office,district) -> {'candidates':[(name,party)], 'rows':{prec:[votes]}, 'total':[...]}
order = []
header_anomalies = 0
dup_precinct_warnings = []

for i, page in enumerate(pdf.pages):
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
        continue
    tables = page.extract_tables()
    if not tables:
        continue
    table = max(tables, key=lambda t: len(t) * len(t[0]) if t and t[0] else 0)
    hi, hj = find_header(table)
    if hi is None or hi + 2 >= len(table):
        continue

    office_row = forward_fill(table[hi][hj:])
    blank_row = table[hi + 1][hj:] if hi + 1 < len(table) else []
    cand_row = table[hi + 2][hj:]
    if any((c or '').strip() for c in blank_row[1:]):
        header_anomalies += 1

    cols = []  # (col_idx_in_slice, office, district, candidate, party)
    for k in range(1, len(office_row)):
        office_text = office_row[k]
        if not office_text:
            continue
        norm = normalize_office(office_text)
        office, district = norm if norm else (clean(office_text), "")
        raw_cand = cand_row[k] if k < len(cand_row) else ''
        cname, cparty = parse_candidate_cell(raw_cand)
        if not cname and not cparty:
            continue  # phantom column (table-extraction artifact); no candidate here
        if norm and norm[0] == "Supreme Court Retention" and cname in ('Yes', 'No'):
            jname = retention_name(office_text)
            if jname:
                cname, cparty = f"{jname} - {cname}", ''
        cols.append((k, office, district, cname, cparty))

    row_data = []  # (precinct, {col_idx: votes})
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
        row_data.append((prec, vals))

    by_key = defaultdict(list)
    for (k, office, district, cname, cparty) in cols:
        by_key[(office, district)].append((k, cname, cparty))

    for (office, district), colinfo in by_key.items():
        key = (county, office, district)
        if key not in merged:
            merged[key] = {'candidates': [(cn, cp) for _, cn, cp in colinfo],
                            'rows': {}, 'total': None}
            order.append(key)
        m = merged[key]
        ks = [k for k, _, _ in colinfo]
        for prec, vals in row_data:
            row_vals = [vals.get(k) for k in ks]
            if all(v is None for v in row_vals):
                continue
            if prec in m['rows'] and m['rows'][prec] != row_vals:
                dup_precinct_warnings.append((key, prec))
            m['rows'][prec] = row_vals
        if total_vals is not None:
            tv = []
            for k in ks:
                v = total_vals[k] if k < len(total_vals) else None
                tv.append(int(v.replace(',', '')) if v and INT_RE.match(v.strip()) else None)
            m['total'] = tv

# ---- validate + emit ----
out_by_county = defaultdict(list)
county_extra = []  # local-office totals to append to the county-level CSV
statewide_mismatch = []
local_mismatch = []
local_ok = 0
statewide_ok = 0

for key in order:
    county, office, district = key
    m = merged[key]
    candidates = m['candidates']
    cands_cf = cf.get(key)
    ncols = len(candidates)
    colsum = [0] * ncols
    for vals in m['rows'].values():
        for idx in range(ncols):
            if vals[idx] is not None:
                colsum[idx] += vals[idx]

    if cands_cf:
        expected = {(cn, cp): ct for cn, cp, ct in cands_cf}
        ok = len(cands_cf) == ncols and all(
            expected.get((cn, cp)) == colsum[idx] for idx, (cn, cp) in enumerate(candidates))
        if ok:
            statewide_ok += 1
        else:
            statewide_mismatch.append((key, candidates, colsum, cands_cf))
            continue
    else:
        expected_total = m['total']
        ok = expected_total is not None and len(expected_total) == ncols and \
            all(expected_total[idx] == colsum[idx] for idx in range(ncols))
        if ok:
            local_ok += 1
            for idx, (cn, cp) in enumerate(candidates):
                county_extra.append([county, office, district, cp, cn, colsum[idx]])
        else:
            local_mismatch.append((key, candidates, colsum, expected_total))
            continue

    for prec, vals in m['rows'].items():
        for idx, (cn, cp) in enumerate(candidates):
            v = vals[idx]
            if v is None:
                continue
            out_by_county[county].append([county, prec, office, district, cn, cp, v])

# ---- write per-county CSVs + county-level local-office extras ----
os.makedirs(OUTDIR, exist_ok=True)
def slug(c): return c.lower().replace(' ', '_')
for county, rows in out_by_county.items():
    with open(f"{OUTDIR}/20221108__sd__general__{slug(county)}__precinct.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["county", "precinct", "office", "district", "candidate", "party", "votes"])
        w.writerows(rows)
with open(f"{OUTDIR}/county_local_extra.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["county", "office", "district", "party", "candidate", "votes"])
    w.writerows(county_extra)

print(f"pages: {len(pdf.pages)}   contests seen: {len(order)}   counties out: {len(out_by_county)}")
print(f"output rows: {sum(len(v) for v in out_by_county.values())}")
print(f"header anomalies (non-blank spacer row): {header_anomalies}")
print(f"duplicate-precinct-in-contest warnings: {len(dup_precinct_warnings)}")
for w in dup_precinct_warnings[:20]: print("   DUP", w)
print(f"\nstatewide/legislative/judicial contests reconciled: {statewide_ok} / {statewide_ok+len(statewide_mismatch)}")
for key, cands, colsum, cands_cf in statewide_mismatch[:30]:
    print("   MISMATCH", key, "cols", cands, colsum, "cf", cands_cf)
print(f"\nlocal contests reconciled to page Total: {local_ok} / {local_ok+len(local_mismatch)}")
for key, cands, colsum, total in local_mismatch[:30]:
    print("   MISMATCH", key, "cols", cands, colsum, "total", total)
