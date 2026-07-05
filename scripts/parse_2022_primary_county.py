#!/usr/bin/env python3
"""Vision-LLM extraction of the SD 2022 PRIMARY statewide county canvass
report (2022/sources/2022PrimaryStateCanvassReport.pdf -- 10 pages: one
certificate page followed by one page per statewide/multi-county contest,
COUNTIES as rows instead of precincts). Uses Claude Sonnet 4.6, adapting the
same page-image + self-validating-JSON approach as
scripts/parse_2022_primary_precinct.py.

Usage:
    python scripts/parse_2022_primary_county.py
"""
import json
import re
import time
from pathlib import Path

import llm
from json_repair import repair_json
from natural_pdf import PDF

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "2022/sources/2022PrimaryStateCanvassReport.pdf"
OUT_CSV = REPO / "2022/20220607__sd__primary__county.csv"
CACHE = Path.home() / "sd_cache" / "2022_primary_county"
CACHE.mkdir(parents=True, exist_ok=True)
RENDER_DPI = 250
MODEL_NAME = "claude-sonnet-4.6"
MAX_ATTEMPTS = 3

COUNTIES = {c.lower(): c for c in [
 "Aurora","Beadle","Bennett","Bon Homme","Brookings","Brown","Brule","Buffalo","Butte",
 "Campbell","Charles Mix","Clark","Clay","Codington","Corson","Custer","Davison","Day",
 "Deuel","Dewey","Douglas","Edmunds","Fall River","Faulk","Grant","Gregory","Haakon",
 "Hamlin","Hand","Hanson","Harding","Hughes","Hutchinson","Hyde","Jackson","Jerauld",
 "Jones","Kingsbury","Lake","Lawrence","Lincoln","Lyman","Marshall","McCook","McPherson",
 "Meade","Mellette","Miner","Minnehaha","Moody","Oglala Lakota","Pennington","Perkins",
 "Potter","Roberts","Sanborn","Spink","Stanley","Sully","Todd","Tripp","Turner","Union",
 "Walworth","Yankton","Ziebach"]}

PARTY_MAP = {"REP": "REP", "Republican": "REP", "DEM": "DEM", "Democratic": "DEM",
             "Nonpartisan": "", "NON": "", "": ""}

PROMPT = """This is one page from the South Dakota 2022 PRIMARY ELECTION statewide
county canvass report. Read the actual page IMAGE carefully.

If this page is a CERTIFICATE/OATH page (not a results table -- look for
"STATE OF SOUTH DAKOTA", "CERTIFICATE", signatures, notary text), return a
bare JSON empty array [].

Otherwise the page shows ONE contest, with COUNTIES as rows (not precincts):
the OFFICE name near the top (e.g. "United States Senator", "Governor",
"State Senator District 01", "Constitutional Amendment C: ..."), then the
PARTY for this primary ballot (Republican, Democratic, or Nonpartisan).
Below that is a table: "County" as the row label, and one column per
candidate (names may wrap across 2-3 lines in the header). Data rows list a
county name and a vote count per candidate column, covering all counties
that have data for this contest (not necessarily all 66 -- some multi-county
legislative districts only include a handful). A "Total" row sums each
column at the bottom.

Return a JSON array with ONE element for this contest (empty array if this
is a certificate page), shaped like this:
{
  "office": "United States Senator",
  "party": "REP",
  "candidates": ["John R. Thune", "Bruce Whalen", "Mark Mowry"],
  "counties": {
    "Aurora": [280, 84, 26],
    "Beadle": [1402, 232, 122]
  },
  "total": [85613, 24071, 8827]
}

Rules:
- "candidates" lists candidates left to right exactly as the columns appear.
- Each value in "counties" is a list of vote counts in that SAME candidate
  order, one integer per candidate (no commas; use null for a blank cell).
- "total" is the page's own "Total" row, in that same candidate order --
  include it, don't skip it.
- Read digits and names carefully from the image. Before answering, re-add
  each candidate's column of county numbers yourself and confirm it equals
  the printed Total for that column; if it doesn't, re-examine the image and
  fix whichever digit you misread.
- Return ONLY the JSON array, no prose, no markdown fences."""


def extract_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    if text.startswith("null"):
        return []
    if not text.startswith("["):
        s = text.find("[")
        e = text.rfind("]")
        if s != -1 and e != -1:
            text = text[s:e + 1]
    parsed = json.loads(repair_json(text))
    return parsed if isinstance(parsed, list) else [parsed]


def record_valid(r):
    if not isinstance(r, dict):
        return False
    candidates = r.get("candidates")
    counties = r.get("counties")
    total = r.get("total")
    if not isinstance(candidates, list) or not isinstance(counties, dict):
        return False
    ncand = len(candidates)
    colsum = [0] * ncand
    for vals in counties.values():
        if not isinstance(vals, list) or len(vals) != ncand:
            return False
        for idx in range(ncand):
            if isinstance(vals[idx], (int, float)):
                colsum[idx] += vals[idx]
    return isinstance(total, list) and len(total) == ncand and all(
        total[idx] == colsum[idx] for idx in range(ncand))


def all_valid(rec):
    if rec is None:
        return True
    items = rec if isinstance(rec, list) else [rec]
    return all(record_valid(r) for r in items)


def normalize_county(raw):
    if not raw:
        return None
    t = re.sub(r'\s+county\s*$', '', raw.strip(), flags=re.I).strip()
    return COUNTIES.get(t.lower())


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
        # The page header wraps across several lines and the model often
        # only captures the first one -- restore the full title so this
        # matches the precinct-level files' naming for cross-checking.
        return ("Constitutional Amendment C: A Constitutional Amendment Requiring "
                "Three-Fifths Vote for Approval of Ballot Measures Imposing Taxes "
                "or Fees or Obligating over $10 Million"), ""
    return t, ""


def process():
    model = llm.get_model(MODEL_NAME)
    model_slug = re.sub(r"[^A-Za-z0-9]+", "-", MODEL_NAME).strip("-")
    pdf = PDF(str(SRC))

    contests = []
    failed_pages = []
    for i in range(len(pdf.pages)):
        cache = CACHE / f"page{i}_{model_slug}.json"
        if cache.exists():
            rec = json.load(open(cache))
            print(f"  p{i} (cached)")
        else:
            img = CACHE / f"page{i}.png"
            if not img.exists():
                pdf.pages[i].render(resolution=RENDER_DPI).save(str(img))
            rec = None
            call_ok = False
            for attempt in range(1, MAX_ATTEMPTS + 1):
                suffix = f" (retry {attempt})" if attempt > 1 else ""
                print(f"  p{i} -> {MODEL_NAME}{suffix} ...", flush=True)
                try:
                    resp = model.prompt(PROMPT, attachments=[llm.Attachment(path=str(img))])
                    rec = extract_json(resp.text())
                    call_ok = True
                except Exception as e:
                    print("    CALL FAILED", e)
                    call_ok = False
                    rec = None
                    if attempt < MAX_ATTEMPTS:
                        time.sleep(5 * attempt)
                    continue
                if all_valid(rec):
                    break
                print("    self-check failed (colsum != total)")
            if not call_ok:
                print(f"    giving up on p{i} -- not caching")
                failed_pages.append(i)
                continue
            json.dump(rec, open(cache, "w"), indent=1)
        for r in (rec or []):
            r["page"] = i
            contests.append(r)
    return contests, failed_pages


def main():
    contests, failed_pages = process()

    valid, invalid = [], []
    for c in contests:
        (valid if record_valid(c) else invalid).append(c)

    rows = []
    for c in valid:
        office, district = normalize_office(c["office"])
        party = PARTY_MAP.get(c.get("party"), c.get("party") or "")
        for county_raw, vals in c["counties"].items():
            county = normalize_county(county_raw)
            if not county:
                print(f"   SKIP unrecognized county {county_raw!r} on page {c['page']}")
                continue
            for idx, cand in enumerate(c["candidates"]):
                v = vals[idx]
                if v is None:
                    continue
                rows.append([county, office, district, party, cand, v])

    import csv
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["county", "office", "district", "party", "candidate", "votes"])
        w.writerows(rows)

    print(f"\npages: {len(list(range(10)))}")
    print(f"contests found: {len(contests)}")
    print(f"reconciled to page's own Total: {len(valid)} / {len(contests)}")
    for c in invalid:
        print("   MISMATCH page", c["page"], c.get("office"), c.get("candidates"))
    if failed_pages:
        print(f"pages that never got a completed API call: {failed_pages}")
    print(f"\n-> {OUT_CSV} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
