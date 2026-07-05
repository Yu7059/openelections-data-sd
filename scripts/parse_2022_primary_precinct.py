#!/usr/bin/env python3
"""Vision-LLM extraction of the SD 2022 PRIMARY precinct canvass PDFs in
2022/sources/ (four regional scans: AuroraClark, ClayFaulk, GrantLyman,
MarshallZiebach). Unlike the 2020 primary and 2022 general canvasses, these
are scanned page images with no vector table grid (pdfplumber.extract_tables()
returns nothing) and an unreliable embedded OCR text layer (garbled office
names, dropped/transposed digits). So instead of parsing text/tables, this
renders each page to an image and asks a vision LLM to read it directly,
adapting the approach in scripts/parse_2022_mz.py (which did the same for a
couple of scanned counties in the 2022 general) to a full-file batch run.

Usage (pilot -- one file, review output before running the rest):
    python scripts/parse_2022_primary_precinct.py AuroraClark
    python scripts/parse_2022_primary_precinct.py AuroraClark qwen3.5:397b-cloud
    python scripts/parse_2022_primary_precinct.py AuroraClark claude-3.5-sonnet 0 10  # pages 0-9 only
"""
import json
import os
import re
import sys
import time
from pathlib import Path

import llm
from json_repair import repair_json
from natural_pdf import PDF

REPO = Path(__file__).resolve().parents[1]
SOURCES = REPO / "2022/sources"
CACHE = Path(os.environ.get("SD_CACHE", Path.home() / "sd_cache" / "2022_primary"))
CACHE.mkdir(parents=True, exist_ok=True)
RENDER_DPI = 250

COUNTIES = {c.lower(): c for c in [
 "Aurora","Beadle","Bennett","Bon Homme","Brookings","Brown","Brule","Buffalo","Butte",
 "Campbell","Charles Mix","Clark","Clay","Codington","Corson","Custer","Davison","Day",
 "Deuel","Dewey","Douglas","Edmunds","Fall River","Faulk","Grant","Gregory","Haakon",
 "Hamlin","Hand","Hanson","Harding","Hughes","Hutchinson","Hyde","Jackson","Jerauld",
 "Jones","Kingsbury","Lake","Lawrence","Lincoln","Lyman","Marshall","McCook","McPherson",
 "Meade","Mellette","Miner","Minnehaha","Moody","Oglala Lakota","Pennington","Perkins",
 "Potter","Roberts","Sanborn","Spink","Stanley","Sully","Todd","Tripp","Turner","Union",
 "Walworth","Yankton","Ziebach"]}


def normalize_county(raw):
    """Return the canonical county name for a model-reported county string,
    or None if it doesn't match a known SD county (e.g. a page with a
    missing/illegible county header, where the model may hallucinate one)."""
    if not raw:
        return None
    t = re.sub(r'\s+county\s*$', '', raw.strip(), flags=re.I).strip()
    return COUNTIES.get(t.lower())

PROMPT = """This is one page from the South Dakota 2022 PRIMARY ELECTION precinct
canvass. It is a scanned document -- read the actual page IMAGE carefully;
the embedded OCR text layer is unreliable (garbled words, dropped or
transposed digits) and should not be trusted.

FIRST check whether this page is a CERTIFICATE/OATH page instead of a results
table. Certificate pages look like: "STATE OF SOUTH DAKOTA", "CERTIFICATE",
"COUNTY OF: ...", a paragraph starting "We, [Name], Chairman; [Name], Vice
Chairman; [Name], Commissioner, the County Board of Canvassers in ... County
...", followed by signature lines, a notary line ("Sworn to before me this
... day of ..."), a county seal graphic, and "County Auditor". If you see
this pattern -- even if it names a "Board of Canvassers" or officials that
might look like candidates -- this is NOT an election contest. Return a bare
JSON empty array [] for it. Do not invent a contest from the signers' names.

SECOND check whether this is a PROVISIONAL/CHALLENGED BALLOT recording form
instead of an aggregate results table. That form looks like: columns headed
"Precinct Name", "Name of Candidate or Ballot Question", "Number of votes
Received in figures", "Number of Votes received in words" -- and each row is
ONE SINGLE BALLOT's choice for ONE office, written as e.g. "United States
Senator - Bruce Whalen" with a vote count of 1 ("One"). Many different
offices are listed as separate ROWS for the same precinct, not as columns.
This is NOT an aggregate precinct-by-candidate results table -- it's a
manual record of individual challenged/provisional ballots. Return a bare
JSON empty array [] for it.

THIRD, if the page is rotated/sideways, poorly scanned, or you cannot
clearly make out a normal "precincts as rows, candidates as columns" grid
with a legible county header matching a real South Dakota county, do NOT
guess or reconstruct one from memory of typical candidates/results. Return
a bare JSON empty array [] rather than inventing county, precinct, or vote
data that isn't clearly visible on the page.

Otherwise the page shows one OR MORE contests: the COUNTY name is in the
header (e.g. "Aurora County"). Below that is a table with one or more
contests placed SIDE BY SIDE as separate groups of columns -- e.g. "State
Representative District 03" next to "State Representative District 23",
each its own office/party/candidates/Total. Don't assume there's only one;
scan the full width of the table for additional column groups. For each
contest: the OFFICE name (e.g. "United States Senator", "Governor and
Lieutenant Governor", "County Commissioner", "State Representative District
23"), then the PARTY for this primary ballot (Republican, Democratic, or
Nonpartisan -- primaries are single-party, so only one party appears per
contest). "Precinct Name" is the shared row label on the left, and each
contest has one column per candidate (candidate names may wrap across 2-3
lines in the header). Data rows list a precinct name and a vote count per
candidate column -- a precinct row may be blank under a contest it doesn't
belong to. A "Total" row sums each column at the bottom, followed by a page
footer like "N of M".

Return a JSON ARRAY with one element per contest on the page (empty array if
none), each shaped like this:
{
  "county": "Aurora County",
  "office": "United States Senator",
  "party": "REP",
  "candidates": ["John R. Thune", "Bruce Whalen", "Mark Mowry"],
  "precincts": {
    "Precinct-1": [90, 19, 5],
    "Precinct-2": [36, 19, 2]
  },
  "total": [280, 84, 26]
}

Rules:
- "candidates" lists candidates left to right exactly as the columns appear
  for THAT contest.
- Each value in "precincts" is a list of vote counts in that SAME candidate
  order, one integer per candidate (use null for a blank cell, not 0). Omit
  a precinct entirely from a contest's "precincts" if that precinct doesn't
  belong to that contest's district (don't invent zeros).
- "total" is that contest's own "Total" row, in that same candidate order --
  include it, don't skip it.
- Read digits and names carefully from the image -- this is a low-quality
  scan; the OCR text layer frequently drops or transposes digits/letters, so
  rely on your own reading of the image, not that text. Before answering,
  re-add each candidate's column of precinct numbers yourself and confirm it
  equals the printed Total for that column; if it doesn't, re-examine the
  image and fix whichever digit you misread. Do this separately for EACH
  contest on the page.
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
    # tolerate a lone object if the model forgets to wrap it in an array
    return parsed if isinstance(parsed, list) else [parsed]


def record_valid(r):
    """Self-check a single contest dict: does its own reported column sums
    match its own reported Total row?"""
    if not isinstance(r, dict):
        return False
    candidates = r.get("candidates")
    precincts = r.get("precincts")
    total = r.get("total")
    if not isinstance(candidates, list) or not isinstance(precincts, dict):
        return False
    ncand = len(candidates)
    colsum = [0] * ncand
    for vals in precincts.values():
        if not isinstance(vals, list) or len(vals) != ncand:
            return False
        for idx in range(ncand):
            if isinstance(vals[idx], (int, float)):
                colsum[idx] += vals[idx]
    return isinstance(total, list) and len(total) == ncand and all(
        total[idx] == colsum[idx] for idx in range(ncand))


def all_valid(rec):
    """rec may be None (certificate page -- nothing to check), a single
    contest dict, or (rarely) a list of them."""
    if rec is None:
        return True
    items = rec if isinstance(rec, list) else [rec]
    return all(record_valid(r) for r in items)


MAX_ATTEMPTS = 3


def process(src_name, model_name, pages=None):
    src_path = SOURCES / f"{src_name}.pdf"
    model = llm.get_model(model_name)
    model_slug = re.sub(r"[^A-Za-z0-9]+", "-", model_name).strip("-")
    pdf = PDF(str(src_path))
    if pages is None:
        pages = range(len(pdf.pages))

    contests = []
    dropped = []
    failed_pages = []
    for i in pages:
        cache = CACHE / f"{src_name}_{model_slug}_page{i}.json"
        if cache.exists():
            rec = json.load(open(cache))
            print(f"  p{i} (cached)")
        else:
            img = CACHE / f"{src_name}_page{i}.png"
            if not img.exists():
                pdf.pages[i].render(resolution=RENDER_DPI).save(str(img))
            rec = None
            call_ok = False
            for attempt in range(1, MAX_ATTEMPTS + 1):
                suffix = f" (retry {attempt})" if attempt > 1 else ""
                print(f"  p{i} -> {model_name}{suffix} ...", flush=True)
                try:
                    resp = model.prompt(PROMPT, attachments=[llm.Attachment(path=str(img))])
                    rec = extract_json(resp.text())
                    call_ok = True
                except Exception as e:
                    # A rate limit / network / bad-JSON failure is NOT the same
                    # as the model legitimately reporting no contest on this
                    # page -- don't let it collapse to that. Back off and retry
                    # (rate limits in particular need a real pause, not an
                    # immediate hammer), and never cache an uncompleted call.
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
                print(f"    giving up on p{i} after {MAX_ATTEMPTS} failed calls -- not caching")
                failed_pages.append(i)
                continue
            json.dump(rec, open(cache, "w"), indent=1)
        # Normalize into a list: null -> [], a single object -> [object],
        # and (occasionally, when the model second-guesses itself) a raw
        # array of candidate objects -> pass through as-is.
        recs = rec if isinstance(rec, list) else ([rec] if rec else [])
        for r in recs:
            if not isinstance(r, dict):
                dropped.append((i, "not a JSON object", r))
                continue
            county = normalize_county(r.get("county"))
            if not county:
                dropped.append((i, f"unrecognized county {r.get('county')!r}", r))
                continue
            candidates = r.get("candidates")
            precincts = r.get("precincts")
            if not isinstance(candidates, list) or not isinstance(precincts, dict):
                dropped.append((i, "malformed candidates/precincts", r))
                continue
            r["county"] = county
            r["page"] = i
            contests.append(r)
        print(f"    {len(recs)} record(s), {sum(1 for c in contests if c['page']==i)} kept")
    for i, reason, r in dropped:
        print(f"   DROPPED page {i}: {reason}")
    if failed_pages:
        print(f"   FAILED (no cache written, re-run to retry): {failed_pages}")
    return contests, failed_pages


def validate(contests):
    ok, mismatches = [], []
    for c in contests:
        candidates = c["candidates"]
        ncand = len(candidates)
        total = c.get("total")
        colsum = [0] * ncand
        malformed = False
        for vals in c["precincts"].values():
            if not isinstance(vals, list) or len(vals) != ncand:
                malformed = True
                continue
            for idx in range(ncand):
                if isinstance(vals[idx], (int, float)):
                    colsum[idx] += vals[idx]
        valid = (not malformed and isinstance(total, list) and len(total) == ncand
                 and all(total[idx] == colsum[idx] for idx in range(ncand)))
        (ok if valid else mismatches).append((c, colsum))
    return ok, mismatches


if __name__ == "__main__":
    src_name = sys.argv[1]  # e.g. AuroraClark
    model_name = sys.argv[2] if len(sys.argv) > 2 else "qwen3.5:397b-cloud"
    pages = None
    if len(sys.argv) > 4:
        pages = range(int(sys.argv[3]), int(sys.argv[4]))

    contests, failed_pages = process(src_name, model_name, pages)
    out = CACHE / f"{src_name}_contests.json"
    json.dump(contests, open(out, "w"), indent=1)

    ok, mismatches = validate(contests)
    print(f"\npages processed: {len(pages) if pages is not None else 'all'}")
    print(f"contests found: {len(contests)}")
    print(f"reconciled to page's own Total: {len(ok)} / {len(contests)}")
    for c, colsum in mismatches:
        print("   MISMATCH page", c["page"], c.get("county"), c.get("office"),
              "candidates", c.get("candidates"), "colsum", colsum, "total", c.get("total"))
    if failed_pages:
        print(f"pages that never got a completed API call (re-run to retry): {failed_pages}")
    print(f"\n-> {out}")
