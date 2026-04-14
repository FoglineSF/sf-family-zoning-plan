#!/usr/bin/env python3
"""
Answer two specific questions:

  Q1: Is the "10.3% upzoned" land area dominantly commercial corridors
      (Geary, Clement, California, Balboa, Judah, Irving, Taraval), or
      is it something else?

  Q2: What are the actual height values in play, and how does the
      NextDoor "nearly 4X" claim hold up against real building-height math?
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parent.parent
DERIVED = ROOT / "data" / "derived"

# Multiple sample points per corridor.
# (corridor_name, [(label, lon, lat), ...])
CORRIDORS = {
    "Geary Blvd (major transit, west from downtown)": [
        ("Geary + Webster",    -122.4310, 37.7850),
        ("Geary + Fillmore",   -122.4330, 37.7840),
        ("Geary + Masonic",    -122.4459, 37.7820),
        ("Geary + Arguello",   -122.4597, 37.7808),
        ("Geary + Park Presidio", -122.4720, 37.7799),
        ("Geary + 25th Ave",   -122.4840, 37.7795),
        ("Geary + 40th Ave",   -122.4987, 37.7787),
    ],
    "Clement St (Inner/Outer Richmond)": [
        ("Clement + 4th Ave",  -122.4602, 37.7830),
        ("Clement + 9th Ave",  -122.4680, 37.7830),
        ("Clement + 15th Ave", -122.4738, 37.7831),
        ("Clement + 25th Ave", -122.4842, 37.7826),
        ("Clement + 36th Ave", -122.4965, 37.7819),
    ],
    "California St (Inner/Outer Richmond)": [
        ("California + 5th Ave",  -122.4613, 37.7849),
        ("California + 12th Ave", -122.4710, 37.7849),
        ("California + 22nd Ave", -122.4815, 37.7845),
        ("California + 32nd Ave", -122.4928, 37.7840),
    ],
    "Balboa St (Richmond)": [
        ("Balboa + 7th Ave",   -122.4645, 37.7760),
        ("Balboa + 14th Ave",  -122.4734, 37.7760),
        ("Balboa + 25th Ave",  -122.4852, 37.7757),
        ("Balboa + 38th Ave",  -122.4990, 37.7750),
    ],
    "Judah St (Sunset, N-Judah transit)": [
        ("Judah + 9th Ave",    -122.4670, 37.7622),
        ("Judah + 19th Ave",   -122.4760, 37.7613),
        ("Judah + 30th Ave",   -122.4888, 37.7604),
        ("Judah + 45th Ave",   -122.5056, 37.7593),
    ],
    "Irving St (Inner/Outer Sunset)": [
        ("Irving + 9th Ave",   -122.4668, 37.7640),
        ("Irving + 19th Ave",  -122.4760, 37.7632),
        ("Irving + 30th Ave",  -122.4888, 37.7623),
    ],
    "Taraval St (L-Taraval transit)": [
        ("Taraval + 19th Ave", -122.4762, 37.7424),
        ("Taraval + 30th Ave", -122.4888, 37.7416),
        ("Taraval + 40th Ave", -122.4985, 37.7410),
    ],
    "Noriega St (Sunset)": [
        ("Noriega + 19th Ave", -122.4758, 37.7539),
        ("Noriega + 30th Ave", -122.4886, 37.7531),
        ("Noriega + 45th Ave", -122.5061, 37.7520),
    ],
}


def main() -> None:
    heights = gpd.read_file(DERIVED / "height_districts_parsed.geojson")
    heights_4326 = heights.to_crs("EPSG:4326")

    print("=" * 90)
    print("Q1: ARE THE UPZONED AREAS ACTUALLY WEST-SIDE COMMERCIAL CORRIDORS?")
    print("=" * 90)
    print("\nSampling several points along each named corridor. 'has_bonus' means local_ft > base_ft.\n")

    for corridor, points in CORRIDORS.items():
        print(f"\n{corridor}")
        print(f"  {'address':30} {'label':15} {'base':>5} {'local':>5} {'Δ':>5}   bonus?")
        gdf = gpd.GeoDataFrame(
            {"name": [p[0] for p in points]},
            geometry=[Point(p[1], p[2]) for p in points],
            crs="EPSG:4326",
        )
        j = gpd.sjoin(
            gdf,
            heights_4326[["height", "base_ft", "local_ft", "delta_ft", "geometry"]],
            how="left", predicate="intersects",
        )
        for _, r in j.iterrows():
            label = r.get("height") or "(none)"
            base = r.get("base_ft")
            local = r.get("local_ft")
            delta = r.get("delta_ft")
            has_bonus = "YES" if (pd.notna(delta) and delta > 0) else "no"
            b = f"{base:.0f}" if pd.notna(base) else "-"
            l = f"{local:.0f}" if pd.notna(local) else "-"
            d = f"{delta:+.0f}" if pd.notna(delta) else "-"
            print(f"  {r['name']:30} {label:15} {b:>5} {l:>5} {d:>5}   {has_bonus}")

    # -----------------------------------------------------------------
    print("\n" + "=" * 90)
    print("Q2: THE 36 UPZONED DISTRICTS (where the 10.3% comes from)")
    print("=" * 90)

    upzoned = heights[heights["delta_ft"] > 0].copy()
    upzoned_proj = upzoned.to_crs(26910)
    upzoned["area_km2"] = upzoned_proj.area / 1e6
    upzoned["perim_km"] = upzoned_proj.length / 1000
    upzoned["shape_ratio"] = upzoned["perim_km"] / (upzoned["area_km2"] ** 0.5)  # higher = more elongated
    upzoned["centroid_lon"] = upzoned_proj.to_crs(4326).geometry.centroid.x
    upzoned["centroid_lat"] = upzoned_proj.to_crs(4326).geometry.centroid.y

    cols = ["height", "base_ft", "local_ft", "delta_ft", "area_km2", "shape_ratio", "centroid_lon", "centroid_lat"]
    display = upzoned[cols].sort_values("delta_ft", ascending=False).reset_index(drop=True)
    display["area_km2"] = display["area_km2"].round(3)
    display["shape_ratio"] = display["shape_ratio"].round(1)
    display["centroid_lon"] = display["centroid_lon"].round(4)
    display["centroid_lat"] = display["centroid_lat"].round(4)
    pd.set_option("display.max_rows", 50)
    pd.set_option("display.width", 120)
    print(display.to_string())

    # Summary: how much of the 10.3% is along corridors vs. chunky downtown
    print("\nShape analysis (higher shape_ratio = more elongated / corridor-like):")
    print(f"  median shape_ratio of upzoned districts: {upzoned['shape_ratio'].median():.1f}")
    print(f"  corridor-shaped (ratio > 20):            {(upzoned['shape_ratio'] > 20).sum()}")
    print(f"  chunkier (ratio <= 20):                  {(upzoned['shape_ratio'] <= 20).sum()}")
    print(f"  total area corridor-shaped:              {upzoned.loc[upzoned['shape_ratio'] > 20, 'area_km2'].sum():.2f} km²")
    print(f"  total area chunky:                       {upzoned.loc[upzoned['shape_ratio'] <= 20, 'area_km2'].sum():.2f} km²")
    print(f"  total upzoned area:                      {upzoned['area_km2'].sum():.2f} km²")

    # -----------------------------------------------------------------
    print("\n" + "=" * 90)
    print("Q2b: BUILDING HEIGHT LADDER")
    print("=" * 90)
    print("""
  Typical story-to-story: ~10-11 ft (old SF) to ~12 ft (modern construction)

    25 ft  ≈ 2 stories  - small 1-story commercial, bungalow, or 2-flat wood frame
    35 ft  ≈ 3 stories  - typical SF 3-story rowhouse
    40 ft  ≈ 4 stories  - RH-1/RH-2 max (most Richmond/Sunset residential zoning)
    55 ft  ≈ 5 stories  - 5-story apartment building (old Geary mid-rise)
    65 ft  ≈ 6 stories  - 6-story building (Ocean Beach Safeway FZP base)
    85 ft  ≈ 8 stories  - 8-story (Safeway with state density bonus; Chestnut NC)
   100 ft  ≈ 10 stories - downtown-scale mid-rise (Van Ness apartments)
   140 ft  ≈ 14 stories - Geary/Arguello max under FZP bonus
   250 ft  ≈ 25 stories - Geary/Masonic max under FZP bonus
   650 ft  ≈ 60 stories - Salesforce Tower is 1,070 ft for comparison
""")


if __name__ == "__main__":
    main()
