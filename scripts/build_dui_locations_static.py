"""
Static per-location layer for the Impaired Driving Enforcement page.

A location is either an intersection (backend: Intersection_Points_unique) or a
roadway block segment (backend: Roadway_Block_Segments, blocks over 1,000 ft
split into ~500 ft pieces). The backend assigns each crash to one of them
(LOCATION_ID in crashes.parquet). This file holds what does not depend on the
page filters, for every possible location:

  LOCATION_ID, LOCATION_TYPE ('Intersection' | 'Block'), ROAD_CLASS (blocks),
  LATITUDE, LONGITUDE           point drawn on the map (intersection point or
                                segment midpoint)
  x, y                          DC State Plane meters (EPSG:26985), for the
                                page's venue list
  est_kde, est_kde_norm         distance-decayed weight of late-hour on-premise
                                alcohol venues within 400 m (triangular kernel,
                                same weights as before), and scaled 0-1
  n_estab_400m                  number of those venues ("Venues Nearby")
  dui_arrests                   MPD DUI arrests within 400 m, ARREST_YEARS
                                (validation only; never part of the score)

Rerun when the venue file, the arrests file, or the backend's intersection or
segment files change.

Usage (from the frontend repo root):
  python scripts/build_dui_locations_static.py \
      path/to/backend/Spatial-Files/Roadway_Block_Segments.parquet \
      path/to/MPD_Adult_Arrests.csv
"""

import sys
import numpy as np
import pandas as pd
import geopandas as gpd
from scipy.spatial import cKDTree

INTX = "Intersection_Points_unique.parquet"
EST = "establishments_weighted.parquet"
OUT = "dui_locations_static.parquet"

BANDWIDTH_M = 400.0            # "nearby" = within 400 m (about 1,300 ft)
WEIGHT_COL = "weight"
ARREST_YEARS = (2021, 2025)    # inclusive; the open data file ends at 2025
EPSG_M = 26985                 # DC State Plane, meters


def main(segments_path, arrests_path):
    ix = pd.read_parquet(INTX)
    intx = pd.DataFrame({
        "LOCATION_ID": ix.INTERSECTIONKEY, "LOCATION_TYPE": "Intersection",
        "ROAD_CLASS": None, "LATITUDE": ix.LATITUDE, "LONGITUDE": ix.LONGITUDE})
    sg = pd.read_parquet(segments_path, columns=["SEGMENT_ID", "ROAD_CLASS", "MID_LAT", "MID_LON"])
    segs = pd.DataFrame({
        "LOCATION_ID": sg.SEGMENT_ID, "LOCATION_TYPE": "Block",
        "ROAD_CLASS": sg.ROAD_CLASS, "LATITUDE": sg.MID_LAT, "LONGITUDE": sg.MID_LON})
    loc = pd.concat([intx, segs], ignore_index=True).drop_duplicates("LOCATION_ID")

    pts = gpd.GeoSeries(gpd.points_from_xy(loc.LONGITUDE, loc.LATITUDE), crs=4326).to_crs(EPSG_M)
    loc["x"], loc["y"] = pts.x.values, pts.y.values
    lp = np.c_[loc.x.values, loc.y.values]

    # venue density: triangular kernel, weight * (1 - d / b) within b
    e = pd.read_parquet(EST)
    ep, ew = np.c_[e.XCOORD.values, e.YCOORD.values], e[WEIGHT_COL].values
    near = cKDTree(ep).query_ball_point(lp, r=BANDWIDTH_M)
    kde = np.zeros(len(loc)); n = np.zeros(len(loc), dtype=int)
    for i, idx in enumerate(near):
        if idx:
            idx = np.asarray(idx)
            d = np.hypot(lp[i, 0] - ep[idx, 0], lp[i, 1] - ep[idx, 1])
            kde[i] = np.sum(ew[idx] * (1.0 - d / BANDWIDTH_M))
            n[i] = len(idx)
    loc["est_kde"] = kde
    loc["est_kde_norm"] = kde / kde.max()
    loc["n_estab_400m"] = n

    # DUI arrests within 400 m (offense location, boating records dropped)
    a = pd.read_csv(arrests_path, low_memory=False,
                    usecols=["CATEGORY", "DESCRIPTION", "YEAR", "OFFENSE_LATITUDE", "OFFENSE_LONGITUDE"])
    a = a[(a.CATEGORY == "Driving/Boating While Intoxicated") & a.YEAR.between(*ARREST_YEARS)
          & ~a.DESCRIPTION.str.contains("boat", case=False, na=False)]
    a = a.dropna(subset=["OFFENSE_LATITUDE", "OFFENSE_LONGITUDE"])
    ap = gpd.GeoSeries(gpd.points_from_xy(a.OFFENSE_LONGITUDE, a.OFFENSE_LATITUDE), crs=4326).to_crs(EPSG_M)
    loc["dui_arrests"] = [len(x) for x in cKDTree(np.c_[ap.x, ap.y]).query_ball_point(lp, r=BANDWIDTH_M)]

    loc.to_parquet(OUT, index=False)
    print(f"{len(loc)} locations ({(loc.LOCATION_TYPE == 'Intersection').sum()} intersections, "
          f"{(loc.LOCATION_TYPE == 'Block').sum()} block segments) -> {OUT}")
    print(f"with any venue within 400 m: {(loc.n_estab_400m > 0).sum()} | "
          f"DUI arrests {ARREST_YEARS[0]}-{ARREST_YEARS[1]}: {len(a)}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
