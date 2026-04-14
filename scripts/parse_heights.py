#!/usr/bin/env python3
"""
Parse the X//Y-Z label format in Height Districts to recover pre-FZP (base)
and post-FZP (local program) heights. Write a cleaned GeoJSON with base/local
columns, and print upzoning statistics.

Label format (as observed 2026-04-11):
    base // local - condition    e.g. "40//65-R-4"
    flat (unchanged)              e.g. "40-X", "65-X", "400-S"
    mixed special                 e.g. "100//250-R-4", "100-Mission Rock"
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import geopandas as gpd
import pandas as pd

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
DERIVED = Path(__file__).resolve().parent.parent / "data" / "derived"
DERIVED.mkdir(parents=True, exist_ok=True)

LABEL_SPLIT = re.compile(r"^\s*([\d.]+)\s*//\s*([\d.]+)\s*(?:[-/]\s*(.*))?$")
LABEL_FLAT = re.compile(r"^\s*([\d.]+)\s*(?:[-/]\s*(.*))?$")


def parse_label(label: str | None) -> tuple[float | None, float | None, str | None, bool]:
    """Return (base_ft, local_ft, condition, is_diff)."""
    if label is None or not isinstance(label, str):
        return None, None, None, False
    label = label.strip()
    m = LABEL_SPLIT.match(label)
    if m:
        base = float(m.group(1))
        local = float(m.group(2))
        cond = (m.group(3) or "").strip() or None
        return base, local, cond, True
    m = LABEL_FLAT.match(label)
    if m:
        base = float(m.group(1))
        cond = (m.group(2) or "").strip() or None
        return base, base, cond, False
    return None, None, None, False


def main() -> None:
    heights = gpd.read_file(RAW / "height_districts.geojson")
    print(f"loaded {len(heights)} height districts")

    parsed = heights["height"].map(parse_label)
    heights["base_ft"] = [p[0] for p in parsed]
    heights["local_ft"] = [p[1] for p in parsed]
    heights["condition"] = [p[2] for p in parsed]
    heights["is_diff_label"] = [p[3] for p in parsed]
    heights["delta_ft"] = heights["local_ft"] - heights["base_ft"]

    # --- sanity ---
    unparsed = heights[heights["base_ft"].isna()]
    print(f"unparsed labels: {len(unparsed)}")
    if len(unparsed):
        print("  sample unparsed labels:")
        for lbl in unparsed["height"].dropna().unique()[:10]:
            print(f"    {lbl!r}")

    # --- diff stats ---
    diff = heights[heights["is_diff_label"]]
    print(f"\ndistricts with X//Y label (FZP candidates): {len(diff)}")
    print(f"districts with flat label (unchanged):       {len(heights) - len(diff) - len(unparsed)}")

    upzoned = diff[diff["delta_ft"] > 0]
    print(f"actually upzoned (delta > 0): {len(upzoned)}")
    print(f"flat labels with X//X (no change): {(diff['delta_ft'] == 0).sum()}")

    if len(upzoned):
        print("\nupzone size distribution (base -> local):")
        bins = Counter()
        for _, r in upzoned.iterrows():
            bins[(int(r.base_ft), int(r.local_ft))] += 1
        for (b, l), n in sorted(bins.items(), key=lambda x: (-x[1], x[0])):
            print(f"  {b:>4}ft -> {l:>4}ft  (+{l-b:>3}ft)   {n:>4} districts")

    # --- area-weighted (projected) ---
    heights_proj = heights.to_crs(26910).copy()
    heights_proj["area_m2"] = heights_proj.area

    # Filter out sentinel values and unparsed
    real = heights_proj[
        heights_proj["base_ft"].notna()
        & (heights_proj["base_ft"] < 2000)
        & (heights_proj["local_ft"] < 2000)
    ].copy()
    total_area = real["area_m2"].sum()
    upzoned_real = real[real["delta_ft"] > 0]
    print(f"\n--- area-weighted (excl. sentinels) ---")
    print(f"total land area covered: {total_area / 1e6:.2f} km^2")
    print(f"upzoned land area:       {upzoned_real['area_m2'].sum() / 1e6:.2f} km^2")
    print(f"share upzoned:            {upzoned_real['area_m2'].sum() / total_area * 100:.1f}%")

    base_mean = (real["base_ft"] * real["area_m2"]).sum() / total_area
    local_mean = (real["local_ft"] * real["area_m2"]).sum() / total_area
    print(f"area-weighted mean base height:  {base_mean:.1f} ft")
    print(f"area-weighted mean local height: {local_mean:.1f} ft")
    print(f"area-weighted delta:              +{local_mean - base_mean:.1f} ft")

    # --- by supervisor district ---
    print("\n--- upzoned area by supervisor district ---")
    sup = gpd.read_file(RAW / "supervisor_districts_2022_2032.geojson").to_crs(26910)

    over = gpd.overlay(real[["base_ft", "local_ft", "delta_ft", "geometry"]], sup, how="intersection")
    over["area_m2"] = over.area

    def dist_stats(g: pd.DataFrame) -> pd.Series:
        total = g["area_m2"].sum()
        up = g[g["delta_ft"] > 0]
        return pd.Series({
            "supname": g["supname"].iloc[0],
            "land_km2": round(total / 1e6, 2),
            "upzoned_km2": round(up["area_m2"].sum() / 1e6, 2),
            "pct_upzoned": round(up["area_m2"].sum() / total * 100, 1) if total else 0,
            "base_mean_ft": round((g["base_ft"] * g["area_m2"]).sum() / total, 1),
            "local_mean_ft": round((g["local_ft"] * g["area_m2"]).sum() / total, 1),
            "delta_mean_ft": round(((g["local_ft"] - g["base_ft"]) * g["area_m2"]).sum() / total, 1),
        })

    by_dist = over.groupby("district").apply(dist_stats, include_groups=False)
    by_dist = by_dist.sort_values("pct_upzoned", ascending=False)
    print(by_dist.to_string())

    # --- write derived geojson ---
    out = heights.drop(columns=["last_edit", "create_date"], errors="ignore")
    out_path = DERIVED / "height_districts_parsed.geojson"
    out.to_file(out_path, driver="GeoJSON")
    print(f"\nwrote {out_path} ({len(out)} features)")

    # --- summary csv ---
    summary_path = DERIVED / "upzoning_by_district.csv"
    by_dist.to_csv(summary_path)
    print(f"wrote {summary_path}")


if __name__ == "__main__":
    main()
