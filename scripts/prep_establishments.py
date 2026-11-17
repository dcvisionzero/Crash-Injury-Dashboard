"""
Alcohol venue layer for the Impaired Driving Enforcement page.

Output: establishments_weighted.parquet, one weighted point per active,
on-premise establishment. build_dui_locations_static.py turns these into each
location's venue density and "Venues Nearby" count, and the page lists them.

Runs monthly on the EGH runner (refresh_reference_layers.yml), just before the
location layer rebuild. Pulls ABCA's Alcohol License Business Locations layer
from the DC GIS REST service, or reads the Open Data CSV when one is passed.

Design choices (all tunable, all in one place below):
  * On-premise only. CLASS C and D. Off-premise retail (A, B) and Caterer are
    not origin-of-trip drinking locations, so they are excluded. Marine Vessel,
    Railroad, and Third-Party Delivery are dropped as non-roadway origins.
  * No hours in this dataset, so late operation is proxied by TYPE plus the
    nightlife flags (DANCING / COVERCHARGE / ENTERTAINMENT). A restaurant that
    carries a cover charge and dancing is treated as bar-like.
  * Coordinates: XCOORD/YCOORD are DC State Plane (meters), used directly for
    distance. LONGITUDE/LATITUDE kept for mapping.
  * Two weight columns are emitted: `weight` (type/flag only) and `weight_cap`
    (type/flag scaled gently by capacity). The page uses `weight`; `weight_cap`
    is there if venue size should matter.

Safety: the script exits with an error, leaving the existing file untouched,
when the download comes back short of the service's own count, or when the
number of kept venues moves more than MAX_CHANGE from the current file.

Usage (from the frontend repo root):
  python scripts/prep_establishments.py                       # from the service
  python scripts/prep_establishments.py path/to/Alcohol_License_Business_Locations.csv
"""

import os
import sys
import time

import numpy as np
import pandas as pd
import requests

OUT = "establishments_weighted.parquet"
SERVICE_URL = ("https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/"
               "Business_Licensing_and_Grants_WebMercator/FeatureServer/5/query")
FIELDS = ["OBJECTID", "LICENSE", "TRADE_NAME", "APPLICANT", "CLASS", "TYPE",
          "STATUS", "ADDRESS", "WARD", "ANC", "DANCING", "COVERCHARGE",
          "ENTERTAINMENT", "TOTAL_CAPACITY", "CO_CAPACITY",
          "XCOORD", "YCOORD", "LONGITUDE", "LATITUDE"]
PAGE_SIZE = 1000
MAX_CHANGE = 0.15     # refuse a venue count more than 15% off the current file

# --- tunables -------------------------------------------------------------
BASE_WEIGHT = {
    "Nightclub":   1.0,
    "Club":        1.0,
    "Tavern":      0.9,
    "Arena":       0.8,
    "Multipurpose": 0.7,
    "Restaurant":  0.4,
    "Hotel":       0.3,
    "Bed and Breakfast": 0.2,
}
# a nightlife flag bumps these types up toward bar-like late operation
FLAG_BUMP = {
    "Restaurant":  0.8,
    "Multipurpose": 0.8,
    "Arena":       0.9,
    "Hotel":       0.6,
    "Bed and Breakfast": 0.5,
}
DROP_TYPES = {"Marine Vessel", "Railroad", "Third-Party Delivery"}
NIGHTLIFE_FLAGS = ["DANCING", "COVERCHARGE", "ENTERTAINMENT"]
# capacity scaling: sqrt(cap / median), clipped so it never dominates type
CAP_CLIP = (0.5, 2.0)
# --------------------------------------------------------------------------


def _get(params, max_retries=3):
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.get(SERVICE_URL, params=params, timeout=120)
            r.raise_for_status()
            data = r.json()
            if "error" in data:            # ArcGIS reports errors with HTTP 200
                raise requests.exceptions.RequestException(data["error"])
            return data
        except (requests.exceptions.RequestException, ValueError) as e:
            if attempt == max_retries:
                raise
            print(f"attempt {attempt} failed ({e}); retrying in {30 * attempt}s")
            time.sleep(30 * attempt)


def fetch_licenses():
    """Download every license record (attributes only), one page at a time."""
    base = {"where": "1=1", "f": "json"}
    expected = _get({**base, "returnCountOnly": "true"})["count"]
    rows, offset = [], 0
    while True:
        page = _get({**base, "outFields": ",".join(FIELDS), "returnGeometry": "false",
                     "orderByFields": "OBJECTID", "resultOffset": offset,
                     "resultRecordCount": PAGE_SIZE})
        got = page.get("features", [])
        if not got:
            break
        rows.extend(f["attributes"] for f in got)
        offset += len(got)
        print(f"fetched {len(rows)} of {expected}")
        if not page.get("exceededTransferLimit") and len(got) < PAGE_SIZE:
            break
    if len(rows) != expected:
        sys.exit(f"download incomplete: {len(rows)} records, service reports "
                 f"{expected}; existing file left untouched")
    return pd.DataFrame(rows, columns=FIELDS)


def check_count(n):
    """Stop if the venue count moved too far from the file being replaced."""
    if not os.path.exists(OUT):
        return
    prev = len(pd.read_parquet(OUT, columns=["LICENSE"]))
    change = abs(n - prev) / prev
    print(f"venues: {n} now, {prev} in the current file ({change:.1%} change)")
    if change > MAX_CHANGE:
        sys.exit(f"venue count changed {change:.1%} (limit {MAX_CHANGE:.0%}); "
                 "existing file left untouched")


def main(src=None):
    df = fetch_licenses() if src is None else pd.read_csv(src)
    df = df.sort_values("OBJECTID", kind="mergesort")

    # active only (normalize casing seen in the raw file)
    df["STATUS"] = df["STATUS"].astype(str).str.upper()
    df = df[df["STATUS"] == "ACTIVE"].copy()

    # on-premise only, minus non-roadway origins
    df = df[df["CLASS"].isin(["C", "D"])]
    df = df[~df["TYPE"].isin(DROP_TYPES)]

    # nightlife flag: any of the three checked
    flagged = pd.Series(False, index=df.index)
    for f in NIGHTLIFE_FLAGS:
        flagged |= df[f].astype(str).str.upper().eq("CHECKED")
    df["nightlife_flag"] = flagged

    # type weight, then flag bump
    w = df["TYPE"].map(BASE_WEIGHT)
    bumped = df["TYPE"].map(FLAG_BUMP)
    w = np.where(df["nightlife_flag"] & bumped.notna(),
                 np.maximum(w, bumped), w)
    df["weight"] = w

    # anything that didn't map to a base weight is not a drinking origin -> drop
    df = df[df["weight"].notna()].copy()

    # venues need a location to count anywhere
    for c in ["XCOORD", "YCOORD", "LONGITUDE", "LATITUDE"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    no_xy = df[["XCOORD", "YCOORD"]].isna().any(axis=1)
    if no_xy.any():
        print(f"dropping {int(no_xy.sum())} venues with no coordinates")
        df = df[~no_xy].copy()

    # gentle capacity factor
    cap = pd.to_numeric(df["TOTAL_CAPACITY"], errors="coerce")
    cap = cap.fillna(pd.to_numeric(df["CO_CAPACITY"], errors="coerce"))
    med = cap[cap > 0].median()
    cap_factor = np.sqrt(cap / med).clip(*CAP_CLIP)
    cap_factor = cap_factor.fillna(1.0)
    df["cap_factor"] = cap_factor
    df["weight_cap"] = df["weight"] * df["cap_factor"]
    df["TOTAL_CAPACITY"] = pd.to_numeric(df["TOTAL_CAPACITY"], errors="coerce")

    keep = ["LICENSE", "TRADE_NAME", "APPLICANT", "CLASS", "TYPE",
            "ADDRESS", "WARD", "ANC", "TOTAL_CAPACITY", "nightlife_flag",
            "weight", "cap_factor", "weight_cap",
            "XCOORD", "YCOORD", "LONGITUDE", "LATITUDE"]
    out = df[keep].reset_index(drop=True)
    check_count(len(out))
    out.to_parquet(OUT, index=False)

    # --- sanity output ----------------------------------------------------
    print(f"kept {len(out)} weighted establishments -> {OUT}\n")
    print("by weight tier:")
    print(out["weight"].value_counts().sort_index(ascending=False).to_string())
    print("\nrestaurants bumped by a nightlife flag:",
          int(((out.TYPE == "Restaurant") & (out.weight == 0.8)).sum()))


if __name__ == "__main__":
    if len(sys.argv) > 2:
        sys.exit(__doc__)
    main(sys.argv[1] if len(sys.argv) == 2 else None)
