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
  dui_arrests                   MPD DUI arrests within 400 m, 2021-2025
                                (validation only; never part of the score)

The page joins crashes to this file on LOCATION_ID, so it must be rebuilt
whenever the intersection or segment files change, or new locations drop off
the page. The monthly reference-layer refresh on EGH runs it right after
rebuilding those files.

Inputs (all committed):
  Intersection_Points_unique.parquet       copied in by the monthly refresh
  establishments_weighted.parquet          venue points and weights, rebuilt
                                           monthly by prep_establishments.py
  scripts/dui_arrests_2021_2025.parquet    DUI arrest points, 2021-2025, from
                                           MPD Adult Arrests (driving, not
                                           boating; offense location). Fixed:
                                           the open data file ends at 2025.
  Roadway_Block_Segments.parquet           backend file, path passed in

Needs only pandas, geopandas and shapely 2 (no scipy), so it runs on the EGH
runner with the backend's pinned packages.

Usage (from the frontend repo root):
  python scripts/build_dui_locations_static.py \
      path/to/backend/Spatial-Files/Roadway_Block_Segments.parquet
"""

import sys
import numpy as np
import pandas as pd
import geopandas as gpd
import shapely

INTX = "Intersection_Points_unique.parquet"
EST = "establishments_weighted.parquet"
ARRESTS = "scripts/dui_arrests_2021_2025.parquet"
OUT = "dui_locations_static.parquet"

BANDWIDTH_M = 400.0            # "nearby" = within 400 m (about 1,300 ft)
WEIGHT_COL = "weight"
EPSG_M = 26985                 # DC State Plane, meters


def pairs_within(loc_xy, pts_xy, r):
    """Index pairs (location i, point j) with distance <= r, and the distances."""
    tree = shapely.STRtree(shapely.points(pts_xy))
    i, j = tree.query(shapely.points(loc_xy), predicate="dwithin", distance=r)
    d = np.hypot(loc_xy[i, 0] - pts_xy[j, 0], loc_xy[i, 1] - pts_xy[j, 1])
    return i, j, d


def main(segments_path):
    ix = pd.read_parquet(INTX)
    intx = pd.DataFrame({
        "LOCATION_ID": ix.INTERSECTIONKEY, "LOCATION_TYPE": "Intersection",
        "ROAD_CLASS": None, "LATITUDE": ix.LATITUDE, "LONGITUDE": ix.LONGITUDE})
    sg = pd.read_parquet(segments_path, columns=["SEGMENT_ID", "ROAD_CLASS", "MID_LAT", "MID_LON"])
    segs = pd.DataFrame({
        "LOCATION_ID": sg.SEGMENT_ID, "LOCATION_TYPE": "Block",
        "ROAD_CLASS": sg.ROAD_CLASS, "LATITUDE": sg.MID_LAT, "LONGITUDE": sg.MID_LON})
    loc = (pd.concat([intx, segs], ignore_index=True)
             .drop_duplicates("LOCATION_ID").reset_index(drop=True))

    pts = gpd.GeoSeries(gpd.points_from_xy(loc.LONGITUDE, loc.LATITUDE), crs=4326).to_crs(EPSG_M)
    loc["x"], loc["y"] = pts.x.values, pts.y.values
    lp = np.c_[loc.x.values, loc.y.values]

    # venue density: triangular kernel, weight * (1 - d / b) within b
    e = pd.read_parquet(EST)
    i, j, d = pairs_within(lp, np.c_[e.XCOORD.values, e.YCOORD.values], BANDWIDTH_M)
    w = e[WEIGHT_COL].values[j] * (1.0 - d / BANDWIDTH_M)
    kde = np.bincount(i, weights=w, minlength=len(loc))
    loc["est_kde"] = kde
    loc["est_kde_norm"] = kde / kde.max()
    loc["n_estab_400m"] = np.bincount(i, minlength=len(loc))

    # DUI arrests within 400 m
    a = pd.read_parquet(ARRESTS)
    ap = gpd.GeoSeries(gpd.points_from_xy(a.LONGITUDE, a.LATITUDE), crs=4326).to_crs(EPSG_M)
    i, _, _ = pairs_within(lp, np.c_[ap.x.values, ap.y.values], BANDWIDTH_M)
    loc["dui_arrests"] = np.bincount(i, minlength=len(loc))

    loc.to_parquet(OUT, index=False)
    print(f"{len(loc)} locations ({(loc.LOCATION_TYPE == 'Intersection').sum()} intersections, "
          f"{(loc.LOCATION_TYPE == 'Block').sum()} block segments) -> {OUT}")
    print(f"with any venue within 400 m: {(loc.n_estab_400m > 0).sum()} | "
          f"DUI arrests {a.YEAR.min()}-{a.YEAR.max()}: {len(a)}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
