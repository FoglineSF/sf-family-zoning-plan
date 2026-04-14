#!/usr/bin/env python3
"""
First-pass exploration of the SF Planning GIS layers we downloaded.

Goal: sanity-check the data and surface the numbers we'll need to fact-check
the NextDoor thread. Every print here is a candidate fact to cite in the piece.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"

# A few known west-side / coastal-zone test points (lon, lat).
# Ocean Beach Safeway is the anchor.
POI = {
    "ocean_beach_safeway (850 La Playa)": (-122.5094, 37.7548),
    "larry_inner_richmond (6th Ave & Clement approx)": (-122.4643, 37.7831),
    "outer_sunset_beach (46th & Noriega approx)": (-122.5073, 37.7532),
    "marina_safeway (Marina & Buchanan)": (-122.4361, 37.8049),
    "geary_masonic": (-122.4459, 37.7826),
    "sunset_judah_19th": (-122.4761, 37.7609),
    "west_portal_ulloa": (-122.4666, 37.7401),
}


def hr(label: str) -> None:
    print(f"\n{'=' * 6} {label} {'=' * 6}")


def load_layer(name: str) -> gpd.GeoDataFrame:
    p = RAW / f"{name}.geojson"
    gdf = gpd.read_file(p)
    print(f"  loaded {name}: {len(gdf)} features, crs={gdf.crs}")
    return gdf


def main() -> None:
    hr("LOAD")
    heights = load_layer("height_districts")
    zoning = load_layer("zoning_districts")
    coastal = load_layer("coastal_zone")
    sup = load_layer("supervisor_districts_2022_2032")
    liq = load_layer("seismic_liquefaction")
    flood = load_layer("fema_flood_hazard")

    # ------------------------------------------------------------------
    hr("HEIGHT DISTRICTS — schema + value distribution")
    print("columns:", list(heights.columns))
    print("\nrows by gen_hght (top 25):")
    vc = heights["gen_hght"].value_counts().sort_index()
    print(vc.head(25))
    print(f"\nmin gen_hght: {heights['gen_hght'].min()}")
    print(f"max gen_hght: {heights['gen_hght'].max()}")
    print(f"median:       {heights['gen_hght'].median()}")
    print(f"unique HEIGHT label values: {heights['height'].nunique()}")
    print("\n10 distinct HEIGHT labels sorted:")
    for h in sorted(heights["height"].dropna().unique())[:10]:
        print(f"  {h}")

    # ------------------------------------------------------------------
    hr("COASTAL ZONE")
    print("columns:", list(coastal.columns))
    print(coastal[["LABEL"]] if "LABEL" in coastal.columns else coastal.head())
    print(f"total area (sq mi): {coastal.to_crs(6933).area.sum() / 2.59e6:.3f}")

    # ------------------------------------------------------------------
    hr("SUPERVISOR DISTRICTS")
    print("columns:", list(sup.columns))
    show_cols = [c for c in ("district", "DistNum", "supname", "supervisor") if c in sup.columns]
    print(sup[show_cols].to_string())

    # ------------------------------------------------------------------
    hr("POINT-OF-INTEREST HEIGHT LOOKUPS")
    # Build a gdf of POIs in WGS84
    poi_gdf = gpd.GeoDataFrame(
        {"name": list(POI.keys())},
        geometry=[Point(lon, lat) for lon, lat in POI.values()],
        crs="EPSG:4326",
    )
    # sjoin against height districts
    heights_4326 = heights.to_crs("EPSG:4326")
    joined = gpd.sjoin(
        poi_gdf, heights_4326[["height", "gen_hght", "geometry"]],
        how="left", predicate="intersects",
    )
    for _, row in joined.iterrows():
        print(f"  {row['name']:50} -> gen_hght={row['gen_hght']}  label={row['height']}")

    # Also check coastal zone membership
    coastal_4326 = coastal.to_crs("EPSG:4326")
    in_coastal = gpd.sjoin(poi_gdf, coastal_4326, how="left", predicate="intersects")
    print("\n  coastal zone membership:")
    for _, row in in_coastal.iterrows():
        in_cz = pd.notna(row.get("index_right"))
        print(f"    {row['name']:50} in_coastal_zone={in_cz}")

    # ------------------------------------------------------------------
    hr("HEIGHT DISTRIBUTION BY SUPERVISOR DISTRICT (post-FZP, area-weighted)")
    # Filter out sentinel 9999 (special districts - see label) for numeric math
    heights_numeric = heights[heights["gen_hght"] < 9999].copy()
    print(f"  (excluding {len(heights) - len(heights_numeric)} special/9999 districts)")

    heights_proj = heights_numeric.to_crs(26910)  # CA state plane metric
    sup_proj = sup.to_crs(26910)

    intersected = gpd.overlay(heights_proj, sup_proj, how="intersection")
    intersected["area_m2"] = intersected.area

    dist_col = "district" if "district" in sup.columns else "DistNum"
    name_col = "supname" if "supname" in sup.columns else None

    def dist_summary(g: pd.DataFrame) -> pd.Series:
        total = g["area_m2"].sum()
        return pd.Series({
            "supname": g[name_col].iloc[0] if name_col else "",
            "area_km2": round(total / 1e6, 2),
            "area_wt_mean_ft": round((g["gen_hght"] * g["area_m2"]).sum() / total, 1),
            "max_ft": int(g["gen_hght"].max()),
            "pct_leq_40ft": round(g.loc[g["gen_hght"] <= 40, "area_m2"].sum() / total * 100, 1),
            "pct_geq_65ft": round(g.loc[g["gen_hght"] >= 65, "area_m2"].sum() / total * 100, 1),
            "pct_geq_85ft": round(g.loc[g["gen_hght"] >= 85, "area_m2"].sum() / total * 100, 1),
        })

    summary = intersected.groupby(dist_col).apply(dist_summary, include_groups=False)
    print(summary.to_string())

    # City-wide area-weighted stats
    hr("CITY-WIDE area-weighted height stats (post-FZP, excluding 9999 sentinels)")
    total_area = intersected["area_m2"].sum()
    citywide = {
        "area_km2": round(total_area / 1e6, 2),
        "area_wt_mean_ft": round((intersected["gen_hght"] * intersected["area_m2"]).sum() / total_area, 1),
        "pct_leq_40ft": round(intersected.loc[intersected["gen_hght"] <= 40, "area_m2"].sum() / total_area * 100, 1),
        "pct_41_to_64ft": round(intersected.loc[(intersected["gen_hght"] > 40) & (intersected["gen_hght"] < 65), "area_m2"].sum() / total_area * 100, 1),
        "pct_65_to_84ft": round(intersected.loc[(intersected["gen_hght"] >= 65) & (intersected["gen_hght"] < 85), "area_m2"].sum() / total_area * 100, 1),
        "pct_geq_85ft": round(intersected.loc[intersected["gen_hght"] >= 85, "area_m2"].sum() / total_area * 100, 1),
    }
    for k, v in citywide.items():
        print(f"  {k:20} {v}")

    # ------------------------------------------------------------------
    hr("LIQUEFACTION — which SF neighborhoods are in the zone?")
    print("columns:", list(liq.columns))
    print(f"features: {len(liq)}")
    if "LIQ" in liq.columns:
        print(liq["LIQ"].value_counts())
    elif "liq_class" in liq.columns:
        print(liq["liq_class"].value_counts())

    liq_4326 = liq.to_crs("EPSG:4326")
    liq_at_poi = gpd.sjoin(poi_gdf, liq_4326, how="left", predicate="intersects")
    print("\n  POI liquefaction hits:")
    for _, row in liq_at_poi.iterrows():
        hit = pd.notna(row.get("index_right"))
        extra = ""
        for col in ("LIQ", "liq_class", "LIQCLASS"):
            if col in row and pd.notna(row.get(col)):
                extra = f" ({col}={row[col]})"
                break
        print(f"    {row['name']:50} in_liquefaction={hit}{extra}")

    # ------------------------------------------------------------------
    hr("FEMA FLOOD HAZARD — coverage")
    print("columns:", list(flood.columns))
    print(f"features: {len(flood)}")
    if "FLD_ZONE" in flood.columns:
        print(flood["FLD_ZONE"].value_counts())

    flood_4326 = flood.to_crs("EPSG:4326")
    flood_at_poi = gpd.sjoin(poi_gdf, flood_4326, how="left", predicate="intersects")
    print("\n  POI flood hits:")
    for _, row in flood_at_poi.iterrows():
        hit = pd.notna(row.get("index_right"))
        extra = ""
        for col in ("FLD_ZONE", "fld_zone", "ZONE"):
            if col in row and pd.notna(row.get(col)):
                extra = f" ({col}={row[col]})"
                break
        print(f"    {row['name']:50} in_flood_zone={hit}{extra}")


if __name__ == "__main__":
    main()
