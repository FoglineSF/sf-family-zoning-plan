#!/usr/bin/env python3
"""
Verify that the X//Y parsing is catching all FZP upzones (vs. silently missing
labels that were simply replaced), and produce the first map.

Verification approach: sample labels at several POIs known from press coverage
to be FZP-upzoned corridors. If they show X//Y, good. If they show flat single
values, the "10.3%" number is an underestimate.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parent.parent
DERIVED = ROOT / "data" / "derived"
MAPS = ROOT / "maps"
MAPS.mkdir(exist_ok=True)

# Known FZP-upzoned locations (from SF Planning/press coverage).
# If these return X//Y labels, parsing is catching them.
# If they return flat labels at raised heights, parser is missing them.
VERIFY_POIS = {
    # West-side corridors frequently cited as upzoned
    "geary_masonic (Geary + Masonic, tallest spike)":      (-122.4459, 37.7820),
    "geary_japantown (Geary + Webster)":                    (-122.4310, 37.7850),
    "geary_arguello (Geary + Arguello)":                    (-122.4597, 37.7808),
    "clement_6th (Clement + 6th, Inner Richmond)":          (-122.4636, 37.7825),
    "judah_19th (Judah + 19th, Sunset)":                    (-122.4758, 37.7613),
    "taraval_22nd (Taraval + 22nd)":                        (-122.4800, 37.7426),
    "irving_9th (Irving + 9th Ave, Inner Sunset)":          (-122.4661, 37.7640),

    # Known project sites
    "ocean_beach_safeway (850 La Playa)":                   (-122.5094, 37.7726),
    "marina_safeway (Marina at Webster)":                   (-122.4361, 37.8044),

    # Larry's block
    "larry_inner_richmond (6th & Clement)":                 (-122.4636, 37.7830),

    # Control points we expect NOT to be upzoned
    "glen_park_bart":                                        (-122.4334, 37.7330),
    "pac_heights_residential (Clay + Divisadero)":          (-122.4404, 37.7907),
    "sunset_interior (Sunset Blvd + Lawton)":               (-122.4946, 37.7584),
}


def main() -> None:
    heights = gpd.read_file(DERIVED / "height_districts_parsed.geojson")
    sup = gpd.read_file(ROOT / "data" / "raw" / "supervisor_districts_2022_2032.geojson")
    coastal = gpd.read_file(ROOT / "data" / "raw" / "coastal_zone.geojson")

    # --- verify at POIs ---
    poi_gdf = gpd.GeoDataFrame(
        {"name": list(VERIFY_POIS.keys())},
        geometry=[Point(lon, lat) for lon, lat in VERIFY_POIS.values()],
        crs="EPSG:4326",
    )
    heights_4326 = heights.to_crs("EPSG:4326")
    joined = gpd.sjoin(
        poi_gdf,
        heights_4326[["height", "base_ft", "local_ft", "condition", "is_diff_label", "geometry"]],
        how="left",
        predicate="intersects",
    )

    print("=" * 90)
    print("VERIFICATION: labels at known/expected FZP corridors")
    print("=" * 90)
    print(f"{'name':55} {'label':20} {'base':>5} {'local':>5} {'diff?':>6}")
    print("-" * 90)
    for _, row in joined.iterrows():
        label = row.get("height") or "(outside)"
        base = row.get("base_ft")
        local = row.get("local_ft")
        diff = row.get("is_diff_label")
        base_s = f"{base:.0f}" if base == base else "-"  # NaN check
        local_s = f"{local:.0f}" if local == local else "-"
        print(f"{row['name']:55} {label:20} {base_s:>5} {local_s:>5} {str(diff):>6}")

    # --- map 1: upzoned districts only ---
    print("\n" + "=" * 90)
    print("MAP 1: upzoned districts colored by delta")
    print("=" * 90)

    upzoned = heights[(heights["is_diff_label"]) & (heights["local_ft"] > heights["base_ft"])]
    upzoned_proj = upzoned.to_crs(3857)
    sup_proj = sup.to_crs(3857)
    coastal_proj = coastal.to_crs(3857)

    fig, ax = plt.subplots(figsize=(11, 14))
    sup_proj.boundary.plot(ax=ax, color="#999", linewidth=0.6, zorder=1)
    # shade all other land lightly
    heights_other = heights[~heights.index.isin(upzoned.index)].to_crs(3857)
    heights_other.plot(ax=ax, color="#f3f3f3", edgecolor="none", zorder=0)
    # upzoned - color by delta
    cmap = plt.cm.YlOrRd
    upzoned_proj.plot(
        ax=ax,
        column="delta_ft",
        cmap=cmap,
        legend=True,
        legend_kwds={"label": "Height increase (ft)", "shrink": 0.55},
        edgecolor="#444",
        linewidth=0.3,
        zorder=2,
    )
    coastal_proj.boundary.plot(ax=ax, color="#0b6", linewidth=1.5, linestyle="--", zorder=3)

    ax.set_axis_off()
    ax.set_title(
        "San Francisco height districts upzoned by the Family Zoning Plan\n"
        "(districts with explicit X//Y diff labels; green dashed = coastal zone)",
        fontsize=12,
    )

    # annotate the biggest jumps
    big = upzoned_proj.sort_values("delta_ft", ascending=False).head(5)
    for _, r in big.iterrows():
        c = r.geometry.centroid
        ax.annotate(
            f"+{int(r.delta_ft)}ft\n({int(r.base_ft)}→{int(r.local_ft)})",
            xy=(c.x, c.y),
            fontsize=7,
            ha="center",
            color="#222",
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#888", lw=0.5, alpha=0.85),
        )

    out = MAPS / "01_upzoned_districts_overview.png"
    plt.tight_layout()
    plt.savefig(out, dpi=160, bbox_inches="tight")
    print(f"wrote {out}")

    # --- map 2: west-side focus ---
    print("\nMAP 2: west-side close-up")
    fig, ax = plt.subplots(figsize=(11, 11))
    sup_proj.boundary.plot(ax=ax, color="#999", linewidth=0.6)
    heights_proj = heights.to_crs(3857)
    # west side: roughly x < -13635000 in EPSG:3857
    ws_bbox = (-13639000, 4540000, -13628000, 4555000)  # xmin,ymin,xmax,ymax
    heights_proj.plot(
        ax=ax,
        column="local_ft",
        cmap="viridis",
        legend=True,
        legend_kwds={"label": "Local Program height (ft)", "shrink": 0.55},
        edgecolor="none",
        vmin=30,
        vmax=160,
    )
    upzoned_proj.boundary.plot(ax=ax, color="#e63", linewidth=1.2)
    coastal_proj.boundary.plot(ax=ax, color="#0b6", linewidth=1.5, linestyle="--")
    ax.set_xlim(ws_bbox[0], ws_bbox[2])
    ax.set_ylim(ws_bbox[1], ws_bbox[3])
    ax.set_axis_off()
    ax.set_title(
        "West-side heights (Inner Richmond to Outer Sunset)\n"
        "orange outline = district with X//Y upzone label; green dashed = coastal zone",
        fontsize=12,
    )
    out = MAPS / "02_westside_heights.png"
    plt.tight_layout()
    plt.savefig(out, dpi=160, bbox_inches="tight")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
