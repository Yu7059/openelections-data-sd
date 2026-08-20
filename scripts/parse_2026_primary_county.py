#!/usr/bin/env python3
"""
Parse South Dakota 2026 PRIMARY statewide county canvass report using PaddleOCR.

The source PDF is a scanned image. We render each page at high DPI and run
PaddleOCR to get text + bounding boxes, then reconstruct the table from the
box *geometry* (clustering by row/y and column/x) rather than from reading
order. The canvass is laid out in one or two columns per page, so a naive
line-based parse scrambles contests; anchoring on the "County" header box and
aligning vote boxes to county rows by y-center recovers the structure.

Candidate names, parties, and the set of contested contests are canonicalized
against the official CandidateList.csv (the petition filing list), which is the
source of truth for spelling, party, and ballot order. Each contest's printed
"Total" row is used to verify that the sum of per-county votes matches.

Usage:
    PADDLE_OCR_TOKEN=... uv run scripts/parse_2026_primary_county.py
    # force re-OCR (slow): uv run scripts/parse_2026_primary_county.py --regen

Output:
    2026/20260602__sd__primary__county.csv
"""
import argparse
import csv
import difflib
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import fitz  # PyMuPDF for rendering
import numpy as np

REPO = Path(__file__).resolve().parents[1]
SRC = Path.home() / "code/openelections-sources-sd/2026/primary/State Canvass and Certificate.pdf"
CAND_LIST = Path.home() / "code/openelections-sources-sd/2026/primary/CandidateList.csv"
OUT_CSV = REPO / "2026/20260602__sd__primary__county.csv"
CACHE = Path.home() / "sd_cache" / "2026_primary_county"
CACHE.mkdir(parents=True, exist_ok=True)
RENDER_ZOOM = 3.5  # ~350 DPI

# South Dakota's 66 counties.
COUNTY_NAMES = [
    "Aurora", "Beadle", "Bennett", "Bon Homme", "Brookings", "Brown", "Brule", "Buffalo", "Butte",
    "Campbell", "Charles Mix", "Clark", "Clay", "Codington", "Corson", "Custer", "Davison", "Day",
    "Deuel", "Dewey", "Douglas", "Edmunds", "Fall River", "Faulk", "Grant", "Gregory", "Haakon",
    "Hamlin", "Hand", "Hanson", "Harding", "Hughes", "Hutchinson", "Hyde", "Jackson", "Jerauld",
    "Jones", "Kingsbury", "Lake", "Lawrence", "Lincoln", "Lyman", "Marshall", "McCook", "McPherson",
    "Meade", "Mellette", "Miner", "Minnehaha", "Moody", "Oglala Lakota", "Pennington", "Perkins",
    "Potter", "Roberts", "Sanborn", "Spink", "Stanley", "Sully", "Todd", "Tripp", "Turner", "Union",
    "Walworth", "Yankton", "Ziebach",
]
COUNTIES = {c.lower(): c for c in COUNTY_NAMES}

# Common OCR errors on county names (substring -> canonical county).
COUNTY_CORRECTIONS = {
    'innehaha': 'Minnehaha', 'linnehaha': 'Minnehaha', 'nion': 'Union', 'euel': 'Deuel',
    'oberts': 'Roberts', 'utte': 'Butte', 'orson': 'Corson', 'ewey': 'Dewey', 'arding': 'Harding',
    'erkins': 'Perkins', 'iebach': 'Ziebach', 'ead': 'Meade', 'uster': 'Custer',
    'all river': 'Fall River', 'ennington': 'Pennington', 'awrence': 'Lawrence', 'oulas': 'Douglas',
    'olley': 'Moody', 'amlin': 'Hamlin', 'anson': 'Hanson', 'utchinson': 'Hutchinson',
    'cCook': 'McCook', 'cPherson': 'McPherson', 'ellette': 'Mellette', 'iner': 'Miner',
    'oody': 'Moody', 'glala': 'Oglala Lakota', 'otter': 'Potter', 'anborn': 'Sanborn',
    'pink': 'Spink', 'tanley': 'Stanley', 'ully': 'Sully', 'odd': 'Todd', 'ripp': 'Tripp',
    'urner': 'Turner', 'alworth': 'Walworth', 'ankton': 'Yankton', 'ackson': 'Jackson',
    'erauld': 'Jerauld', 'ones': 'Jones', 'ingsbury': 'Kingsbury', 'yman': 'Lyman',
    'arshall': 'Marshall', 'on homme': 'Bon Homme', 'rookings': 'Brookings', 'rown': 'Brown',
    'rule': 'Brule', 'uffalo': 'Buffalo', 'ampbell': 'Campbell', 'harles mix': 'Charles Mix',
    'lark': 'Clark', 'lay': 'Clay', 'odington': 'Codington', 'odinaton': 'Codington',
    'avison': 'Davison', 'dmunds': 'Edmunds', 'aulk': 'Faulk', 'rant': 'Grant',
    'regory': 'Gregory', 'aakon': 'Haakon', 'and': 'Hand', 'ughes': 'Hughes', 'yde': 'Hyde',
    'rvan': 'Ryan',
}

# State-level contest names in CandidateList.csv that appear in the canvass.
STATE_CONTESTS = {
    "United States Senator", "United States Representative", "Governor",
    "Lieutenant Governor", "Secretary of State", "Attorney General", "State Auditor",
    "State Treasurer", "Superintendent of Public Instruction",
    "Commissioner of School and Public Lands", "Public Utilities Commissioner",
    "State Senator", "State Representative",
}

# Map canonical contest -> OpenElections office name.
OFFICE_OUT = {
    "United States Senator": "U.S. Senate",
    "United States Representative": "U.S. House",
    "Governor": "Governor",
    "Lieutenant Governor": "Lieutenant Governor",
    "Secretary of State": "Secretary of State",
    "Attorney General": "Attorney General",
    "State Auditor": "State Auditor",
    "State Treasurer": "State Treasurer",
    "Superintendent of Public Instruction": "Superintendent of Public Instruction",
    "Commissioner of School and Public Lands": "Commissioner of School and Public Lands",
    "Public Utilities Commissioner": "Public Utilities Commissioner",
    "State Senator": "State Senate",
    "State Representative": "State House",
}

PARTY_NORM = {
    "republican": "REP", "reou rlican": "REP", "republica": "REP", "rep": "REP",
    "democratic": "DEM", "democrat": "DEM", "dem": "DEM",
    "nonpartisan": "", "non": "", "libertarian": "LIB",
}

OFFICE_RE = re.compile(
    r'^(United States Senator|United States Representative|Governor|Lieutenant Governor|'
    r'Secretary of State|Attorney General|State Auditor|Auditor|State Treasurer|Treasurer|'
    r'Superintendent of Public Instruction|Commissioner of School and Public Lands|'
    r'Public Utilities Commissioner|State Senator District (\d+[A-Za-z]?)|'
    r'State Representative District (\d+[A-Za-z]?))\s*$',
    re.IGNORECASE,
)
NUM_RE = re.compile(r'^[\d,]+$')


# ---------------------------------------------------------------------------
# OCR / rendering
# ---------------------------------------------------------------------------

def render_page(page_idx: int) -> Path:
    """Render a PDF page with PyMuPDF to a cached PNG."""
    img = CACHE / f"page{page_idx}.png"
    if img.exists():
        return img
    doc = fitz.open(str(SRC))
    page = doc[page_idx]
    pix = page.get_pixmap(matrix=fitz.Matrix(RENDER_ZOOM, RENDER_ZOOM), alpha=False)
    pix.save(str(img))
    doc.close()
    return img


def ocr_boxes(page_idx: int, ocr) -> list:
    """Return cached boxes for a page, running PaddleOCR (preprocessing off) if needed."""
    cache = CACHE / f"page{page_idx}_boxes.json"
    if cache.exists():
        return json.loads(cache.read_text())
    img = render_page(page_idx)
    res = ocr.predict(str(img))[0]
    txts = list(res["rec_texts"])
    polys = np.asarray(res["rec_polys"])
    scores = list(res["rec_scores"]) if "rec_scores" in res else [1.0] * len(txts)
    boxes = []
    for j, t in enumerate(txts):
        x1, y1 = float(polys[j][0][0]), float(polys[j][0][1])
        x2, y2 = float(polys[j][2][0]), float(polys[j][2][1])
        boxes.append({"text": t, "x1": round(x1), "y1": round(y1),
                      "x2": round(x2), "y2": round(y2), "score": float(scores[j])})
    boxes.sort(key=lambda b: (b["y1"], b["x1"]))
    cache.write_text(json.dumps(boxes, ensure_ascii=False))
    return boxes


# ---------------------------------------------------------------------------
# Canonical reference from CandidateList.csv
# ---------------------------------------------------------------------------

def load_canonical() -> dict:
    """Build {(contest, district, party): [candidate names in ballot order]}.

    Only state-level contests with more than one active (non-withdrawn) candidate
    are included -- those are the contested primaries that appear in the canvass.
    """
    canon = {}
    with open(CAND_LIST, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            contest = row["Contest"].strip()
            if contest not in STATE_CONTESTS:
                continue
            name = row["Name"].strip()
            # Drop withdrawn / decertified candidates from the active set.
            if any(w in name for w in ("Withdrawn", "Decertified", "Successful Challenge")):
                continue
            party = row["Party"].strip()
            dist = row["District/County"].strip().replace("District ", "")
            key = (contest, dist, party)
            canon.setdefault(key, []).append((int(row["Ballot Order"]) if row["Ballot Order"].strip() else 99, name))
    out = {}
    for (contest, dist, party), items in canon.items():
        items.sort(key=lambda x: x[0])
        names = [n for _, n in items]
        # A primary is held only when candidates exceed seats. State House has 2
        # seats per district, except split districts (26A/B, 28A/B) with 1 seat.
        # State Senate and statewide offices have 1 seat. Uncontested races are
        # nominated without a primary and do not appear in the canvass.
        if contest == "State Representative":
            seats = 1 if re.match(r"^\d+[A-B]$", dist) else 2
            if len(names) > seats:
                out[(contest, dist, party)] = names
        elif len(names) > 1:
            out[(contest, dist, party)] = names
    return out


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def ycenter(b): return (b["y1"] + b["y2"]) / 2.0
def xcenter(b): return (b["x1"] + b["x2"]) / 2.0


def column_lefts(boxes: list) -> list:
    """Find column left x-coordinates by clustering the x1 of 'County' header boxes."""
    ch = [b for b in boxes if is_county_header(b["text"])]
    xs = sorted(set(b["x1"] for b in ch))
    if not xs:
        return [0]
    clusters = [[xs[0]]]
    for x in xs[1:]:
        if x - clusters[-1][-1] < 400:
            clusters[-1].append(x)
        else:
            clusters.append([x])
    return [int(round(sum(c) / len(c))) for c in clusters]


def assign_column(box: dict, lefts: list) -> int:
    """Assign a box to the column whose left edge is the largest value <= box.x1."""
    cand = [l for l in lefts if l <= box["x1"] + 8]
    return max(cand) if cand else lefts[0]


def is_county_header(text: str) -> bool:
    t = text.strip().lower()
    return t in ("county", "ounty", "coun ty") or (t.startswith("ounty") and len(t) <= 7) \
        or (t.startswith("coun") and len(t) <= 8)


def is_party(text: str) -> bool:
    return text.strip().lower() in PARTY_NORM


def is_total(text: str) -> bool:
    t = text.strip().lower()
    return t in ("total", "otal", "tatal", "tot")


def match_county(text: str):
    """Match an OCR'd county name to a canonical county, or None."""
    t = text.strip().rstrip(".")
    tl = t.lower()
    if not tl:
        return None
    if tl in COUNTIES:
        return COUNTIES[tl]
    for wrong, correct in COUNTY_CORRECTIONS.items():
        if wrong in tl and len(tl) <= len(correct) + 3:
            return correct
    # First letter dropped by OCR (left-edge clip).
    for c in COUNTIES:
        cl = c.lower()
        if len(cl) > 3 and tl == cl[1:]:
            return COUNTIES[c]
    # v/y confusion (Dewev->Dewey, Hvde->Hyde, Dav->Day, Stanlev->Stanley).
    swapped = tl.replace("v", "y")
    if swapped != tl and swapped in COUNTIES:
        return COUNTIES[swapped]
    # Fuzzy fallback.
    m = difflib.get_close_matches(t.title(), COUNTY_NAMES, n=1, cutoff=0.80)
    return m[0] if m else None


def norm_district(d: str) -> str:
    d = d.strip()
    if d.isdigit():
        return str(int(d))
    m = re.match(r'^0*(\d+)([A-Za-z])$', d)
    if m:
        return str(int(m.group(1))) + m.group(2).upper()
    return d


def parse_office(text: str):
    """Return (canonical_contest, district_raw, out_office, out_district) or None."""
    t = text.strip()
    m = OFFICE_RE.match(t)
    if not m:
        return None
    base = m.group(1)
    sen_d = m.group(2)
    rep_d = m.group(3)
    if sen_d:
        return "State Senator", sen_d, "State Senate", norm_district(sen_d)
    if rep_d:
        return "State Representative", rep_d, "State House", norm_district(rep_d)
    key = base.strip()
    # Normalize Auditor/Treasurer shorthand.
    if key.lower() == "auditor":
        key = "State Auditor"
    if key.lower() == "treasurer":
        key = "State Treasurer"
    out_office = OFFICE_OUT.get(key, key)
    out_district = "1" if key == "United States Representative" else ""
    return key, "", out_office, out_district


# ---------------------------------------------------------------------------
# Contest parsing (geometry-aware)
# ---------------------------------------------------------------------------

def parse_contest_region(region_boxes, page_idx, col_left, canon, warnings):
    """Parse one contest region (boxes under one office header, one column).

    A region may contain a single party's primary or a *combined* two-party
    table (one office header, two party sub-headers side by side, candidates
    grouped under each). Returns a list of per-party contest dicts (may be 1
    or 2), or None.
    """
    region = sorted(region_boxes, key=lambda b: (b["y1"], b["x1"]))
    if not region:
        return None

    office_box = next((b for b in region if parse_office(b["text"])), None)
    if office_box is None:
        return None
    contest_canon, dist_raw, out_office, out_district = parse_office(office_box["text"])
    office_y2 = office_box["y2"]

    # County header box anchors the county-name x band.
    county_hdr = next((b for b in region if is_county_header(b["text"])
                       and b["y1"] >= office_y2 - 20), None)
    if county_hdr is None:
        warnings.append(f"p{page_idx} {out_office} {out_district}: no County header")
        return None
    county_band_x = county_hdr["x1"]

    # County rows + total row live in the county-name column.
    county_rows = []
    total_box = None
    for b in region:
        if b["y1"] < office_y2 - 5:
            continue
        if b["x1"] > county_band_x + 160:
            continue  # data area, not a county label
        if is_total(b["text"]):
            total_box = b
            continue
        if is_county_header(b["text"]):
            continue
        c = match_county(b["text"])
        if c:
            county_rows.append((c, b))
    if not county_rows:
        warnings.append(f"p{page_idx} {out_office} {out_district}: no county rows")
        return None
    first_county_y = min(b["y1"] for _, b in county_rows)

    # Party sub-headers: party-labeled boxes in the header band (above county rows).
    party_boxes = [b for b in region
                   if is_party(b["text"]) and office_y2 - 5 <= b["y1"] < first_county_y
                   and b["x1"] > county_band_x + 150]
    party_boxes.sort(key=lambda b: xcenter(b))

    # Candidate-name boxes (used for verification only).
    cand_boxes = []
    for b in region:
        if b["y1"] < office_y2 - 5 or b["y1"] >= first_county_y:
            continue
        if b["x1"] <= county_band_x + 150:
            continue
        t = b["text"].strip()
        if not t or NUM_RE.match(t) or is_party(t) or is_county_header(t) or is_total(t):
            continue
        if "Contest Results" in t or parse_office(t):
            continue
        cand_boxes.append(b)

    # Vote boxes: numeric, in the data area, at/after the first county row.
    vote_boxes = [b for b in region
                  if b["y1"] >= first_county_y - 25
                  and b["x1"] > county_band_x + 150
                  and NUM_RE.match(b["text"].strip())]

    # Column centers from tightly-clustered vote x-centers.
    col_centers = cluster_vote_columns(vote_boxes)
    n_cols = len(col_centers)
    if n_cols == 0:
        warnings.append(f"p{page_idx} {out_office} {out_district}: no vote columns")
        return None

    # Determine which party each column belongs to.
    canon_parties = sorted(p for (c, d, p) in canon
                           if c == contest_canon and d == dist_raw)
    col_party = assign_columns_to_parties(
        col_centers, party_boxes, canon_parties, canon, contest_canon, dist_raw)

    # Cells: (row_idx, col_idx) -> (value, x_distance).
    row_centers = [(name, ycenter(b)) for name, b in county_rows]
    all_rows = list(row_centers)
    if total_box is not None:
        all_rows.append(("__TOTAL__", ycenter(total_box)))
    cells = {}
    for vb in vote_boxes:
        vy, vx = ycenter(vb), xcenter(vb)
        ridx = min(range(len(all_rows)), key=lambda k: abs(all_rows[k][1] - vy))
        if abs(all_rows[ridx][1] - vy) > 30:
            continue
        cidx = min(range(n_cols), key=lambda k: abs(col_centers[k] - vx))
        dist = abs(col_centers[cidx] - vx)
        key = (ridx, cidx)
        if key not in cells or dist < cells[key][1]:
            cells[key] = (int(vb["text"].replace(",", "")), dist)

    def row_vals(ridx):
        return [cells[(ridx, ci)][0] if (ridx, ci) in cells else 0 for ci in range(n_cols)]

    rows_out = [(cname, row_vals(ridx)) for ridx, (cname, _) in enumerate(row_centers)]
    total_votes = None
    if total_box is not None:
        tidx = len(all_rows) - 1
        total_votes = row_vals(tidx)

    # Split columns into per-party sub-contests (left-to-right order = ballot order).
    subcontests = []
    for party in sorted(set(col_party)):
        cols = [ci for ci in range(n_cols) if col_party[ci] == party]
        cols.sort(key=lambda ci: col_centers[ci])
        canon_names = canon.get((contest_canon, dist_raw, party))
        if canon_names and len(canon_names) == len(cols):
            candidates = list(canon_names)
        elif canon_names:
            warnings.append(
                f"p{page_idx} {out_office} {out_district} {party}: "
                f"cols={len(cols)} vs canon={len(canon_names)} "
                f"ocr_cands={[b['text'] for b in cand_boxes]}")
            candidates = list(canon_names)[:len(cols)]
            while len(candidates) < len(cols):
                candidates.append(f"?cand{len(candidates)+1}")
        else:
            candidates = [f"?cand{k+1}" for k in range(len(cols))]
            warnings.append(f"p{page_idx} {out_office} {out_district} {party}: "
                            f"no canonical candidates; ocr={[b['text'] for b in cand_boxes]}")
        sub_rows = [(cname, [vals[ci] for ci in cols]) for cname, vals in rows_out]
        sub_total = [total_votes[ci] for ci in cols] if total_votes else None
        subcontests.append({
            "office": out_office,
            "district": out_district,
            "party": party,
            "candidates": candidates,
            "rows": sub_rows,
            "total": sub_total,
            "col_centers": [col_centers[ci] for ci in cols],
            "col_idx": cols,
            "page": page_idx,
            "contest_canon": contest_canon,
            "dist_raw": dist_raw,
        })
    return subcontests


def assign_columns_to_parties(col_centers, party_boxes, canon_parties, canon,
                              contest_canon, dist_raw):
    """Return a list (one per column) of party codes."""
    n = len(col_centers)
    if party_boxes:
        pcenters = [(PARTY_NORM[b["text"].strip().lower()], xcenter(b)) for b in party_boxes]
        return [min(pcenters, key=lambda pc: abs(pc[1] - cx))[0] for cx in col_centers]
    # No party labels detected: distribute columns to canon parties alphabetically,
    # using each party's canonical candidate count.
    parties = sorted(canon_parties)
    if not parties:
        return [""] * n
    counts = [len(canon.get((contest_canon, dist_raw, p), [])) for p in parties]
    if sum(counts) != n or any(c == 0 for c in counts):
        # Can't confidently split; assign all to the (only) party if so, else blank.
        return [parties[0]] * n if len(parties) == 1 else [""] * n
    out = []
    for p, c in zip(parties, counts):
        out.extend([p] * c)
    return out


def cluster_vote_columns(vote_boxes, gap=60):
    """Cluster vote box x-centers into columns. Within-column spread is tiny
    (a few px) while between-column gaps are tens-to-hundreds of px, so a small
    gap threshold cleanly separates columns -- including the narrow double
    columns in combined two-party tables."""
    xs = sorted(set(round(xcenter(b)) for b in vote_boxes))
    if not xs:
        return []
    clusters = [[xs[0]]]
    for x in xs[1:]:
        if x - clusters[-1][-1] < gap:
            clusters[-1].append(x)
        else:
            clusters.append([x])
    return [sum(c) / len(c) for c in clusters]


# ---------------------------------------------------------------------------
# Page / multi-page assembly
# ---------------------------------------------------------------------------

def split_into_regions(col_boxes):
    """Split a column's boxes (sorted by y) into contest regions at office headers.

    The last region may be a continuation (no office header) -- returned as a
    region whose first box is not an office header, so the caller can append it
    to the pending contest from the previous page.
    """
    regions = []
    cur = []
    for b in col_boxes:
        if parse_office(b["text"]) and cur:
            regions.append(cur)
            cur = [b]
        else:
            cur.append(b)
    if cur:
        regions.append(cur)
    return regions


def process_pages(ocr, regen, canon):
    """Process all pages; return list of finalized sub-contests + warnings."""
    n_pages = fitz.open(str(SRC)).page_count
    contests = []          # finalized sub-contests
    pending = None         # list of sub-contests awaiting a Total / continuation
    warnings = []

    for pi in range(n_pages):
        boxes = ocr_boxes(pi, ocr) if regen else json.loads((CACHE / f"page{pi}_boxes.json").read_text())
        if not boxes:
            warnings.append(f"page{pi}: no OCR boxes")
            continue
        lefts = column_lefts(boxes)
        cols = defaultdict(list)
        for b in boxes:
            cols[assign_column(b, lefts)].append(b)
        for left in lefts:
            col_boxes = sorted(cols.get(left, []), key=lambda b: (b["y1"], b["x1"]))
            if not col_boxes:
                continue
            for region in split_into_regions(col_boxes):
                has_office = any(parse_office(b["text"]) for b in region)
                if not has_office:
                    # Continuation of pending sub-contests (same column slot).
                    if pending is not None:
                        for sc in pending:
                            append_continuation(sc, region, pi, warnings)
                        if any(sc.get("got_total") for sc in pending):
                            contests.extend(pending)
                            pending = None
                    continue
                # New contest header: finalize any pending first.
                if pending is not None:
                    contests.extend(pending)
                    pending = None
                subcontests = parse_contest_region(region, pi, left, canon, warnings)
                if not subcontests:
                    continue
                if subcontests[0].get("total") is not None:
                    contests.extend(subcontests)
                else:
                    pending = subcontests
    if pending is not None:
        contests.extend(pending)
    return contests, warnings


def append_continuation(contest, region_boxes, page_idx, warnings):
    """Append county rows from a header-less continuation region to one sub-contest.

    The continuation page repeats the same column x-positions, so the contest's
    stored col_centers (absolute x) are reused to place votes.
    """
    region = sorted(region_boxes, key=lambda b: (b["y1"], b["x1"]))
    county_rows = []
    total_box = None
    county_band_x = min((b["x1"] for b in region), default=0)
    for b in region:
        if b["x1"] > county_band_x + 160:
            continue
        if is_total(b["text"]):
            total_box = b
            continue
        if is_county_header(b["text"]):
            continue
        c = match_county(b["text"])
        if c:
            county_rows.append((c, b))
    if not county_rows:
        return
    first_y = min(b["y1"] for _, b in county_rows)
    vote_boxes = [b for b in region if b["y1"] >= first_y - 25
                  and b["x1"] > county_band_x + 150 and NUM_RE.match(b["text"].strip())]
    n_cols = len(contest["candidates"])
    col_centers = contest.get("col_centers") or []
    if len(col_centers) != n_cols:
        warnings.append(f"p{page_idx} continuation {contest['office']} {contest['district']}: "
                        f"cols={len(col_centers)} vs {n_cols}")
        return
    all_rows = [(name, ycenter(cb)) for name, cb in county_rows]
    if total_box is not None:
        all_rows.append(("__TOTAL__", ycenter(total_box)))
    cells = {}
    for vb in vote_boxes:
        vy, vx = ycenter(vb), xcenter(vb)
        ridx = min(range(len(all_rows)), key=lambda k: abs(all_rows[k][1] - vy))
        if abs(all_rows[ridx][1] - vy) > 30:
            continue
        cidx = min(range(n_cols), key=lambda k: abs(col_centers[k] - vx))
        dist = abs(col_centers[cidx] - vx)
        key = (ridx, cidx)
        if key not in cells or dist < cells[key][1]:
            cells[key] = (int(vb["text"].replace(",", "")), dist)
    for ridx, (cname, _rc) in enumerate(county_rows):
        vals = [cells[(ridx, ci)][0] if (ridx, ci) in cells else 0 for ci in range(n_cols)]
        contest["rows"].append((cname, vals))
    if total_box is not None:
        tidx = len(all_rows) - 1
        contest["total"] = [cells[(tidx, ci)][0] if (tidx, ci) in cells else None
                            for ci in range(n_cols)]
        contest["got_total"] = True


# ---------------------------------------------------------------------------
# Output + verification
# ---------------------------------------------------------------------------

def verify_and_write(contests, warnings):
    rows = []
    seen = set()
    for c in contests:
        office, district, party = c["office"], c["district"], c["party"]
        cands = c["candidates"]
        # Dedup counties within a contest (keep first).
        county_map = {}
        for cname, vals in c["rows"]:
            if cname not in county_map:
                county_map[cname] = vals
        # Verify against Total row.
        total = c.get("total")
        if total:
            sums = [0] * len(cands)
            for vals in county_map.values():
                for i in range(len(cands)):
                    if i < len(vals):
                        sums[i] += vals[i]
            for i, (s, t) in enumerate(zip(sums, total)):
                if t is not None and s != t:
                    warnings.append(
                        f"TOTAL MISMATCH {office} {district} {party} "
                        f"{cands[i]}: sum={s} total={t} (page {c['page']})")
        key = (office, district, party)
        if key in seen:
            warnings.append(f"DUPLICATE contest {key} -- merging")
            # merge would require dedup; skip second occurrence's counties already seen
        seen.add(key)
        for cname, vals in county_map.items():
            for i, cand in enumerate(cands):
                v = vals[i] if i < len(vals) else 0
                rows.append([cname, office, district, party, cand, v])
    rows.sort(key=lambda r: (r[1], str(r[2]), r[3], r[0], r[4]))
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["county", "office", "district", "party", "candidate", "votes"])
        w.writerows(rows)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--regen", action="store_true", help="Re-run PaddleOCR on all pages")
    args = ap.parse_args()

    ocr = None
    if args.regen or not all((CACHE / f"page{pi}_boxes.json").exists()
                             for pi in range(fitz.open(str(SRC)).page_count)):
        os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "true")
        from paddleocr import PaddleOCR
        ocr = PaddleOCR(lang="en", use_doc_orientation_classify=False,
                        use_doc_unwarping=False, use_textline_orientation=False)

    canon = load_canonical()
    print(f"Canonical contested primaries: {len(canon)}")
    contests, warnings = process_pages(ocr, args.regen, canon)

    rows = verify_and_write(contests, warnings)

    offices = {}
    for r in rows:
        offices.setdefault((r[1], r[2], r[3]), set()).add(r[0])
    print(f"\n=== Summary ===")
    print(f"Contests parsed: {len(contests)}")
    print(f"Rows written: {len(rows)}")
    print(f"Counties per contest: {sum(1 for _ in offices)} contests")
    print(f"Warnings: {len(warnings)}")
    for w in warnings:
        print(f"  ! {w}")
    # Report any canonical contest missing from output.
    out_keys = {(c["contest_canon"], c["dist_raw"], c["party"]) for c in contests}
    print(f"\n=== Missing contested primaries (in CandidateList, not in output) ===")
    for key in sorted(canon):
        if key not in out_keys:
            print(f"  MISSING {key[0]} | {key[1]} | {key[2]} | {canon[key]}")


if __name__ == "__main__":
    main()