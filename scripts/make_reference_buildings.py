#!/usr/bin/env python3
"""
Generate the Paris and Miami reference buildings as GeoJSON polygons,
placed in the Pacific Ocean just west of Ocean Beach, for the 3D map.

When the camera looks west toward the coast, these reference buildings
appear in the same frame as SF's real FZP heights — at true scale.

Output:
  maps/data/reference_buildings.geojson        (polygon footprints)
  maps/data/reference_buildings_labels.geojson (point features for text labels)
"""

from __future__ import annotations

import json
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "maps" / "data"
OUT_DIR.mkdir(parents=True, exist_ok=True)

FT_TO_M = 0.3048

# Buildings are placed in a west-trending line, offshore from Ocean Beach.
# (name, city, height_ft, footprint_width_m, center_lon, center_lat)
# Longitudes are negative (west). Distances are approximate:
#   At SF latitude, 1 km ≈ 0.0113° longitude.
BUILDINGS = [
    ("Haussmann Paris apartment block",    "Paris", 65,  35, -122.5170, 37.7752),
    ("Paris central city height limit",    "Paris", 82,  40, -122.5205, 37.7740),
    ("Paris outlying height limit",        "Paris", 121, 50, -122.5245, 37.7728),
    ("Geary + Masonic (tallest SF FZP)",   "SF",    250, 65, -122.5295, 37.7715),
    ("Porsche Design Tower (Miami)",       "Miami", 641, 80, -122.5460, 37.7690),
]

# Color + metadata per city bucket
CITY_META = {
    "SF":    {"color": "#9e1f0c"},
    "Paris": {"color": "#4a6fa0"},
    "Miami": {"color": "#1d5570"},
}


def rect_polygon(lon: float, lat: float, width_m: float) -> list[list[list[float]]]:
    """Make a square polygon centered at (lon, lat) with width in meters."""
    # Approximate conversions at SF latitude (~37.77°)
    lat_delta = (width_m / 2) / 111_000
    lon_delta = (width_m / 2) / 88_200
    return [[
        [lon - lon_delta, lat - lat_delta],
        [lon + lon_delta, lat - lat_delta],
        [lon + lon_delta, lat + lat_delta],
        [lon - lon_delta, lat + lat_delta],
        [lon - lon_delta, lat - lat_delta],
    ]]


def main() -> None:
    poly_features = []
    label_features = []

    for name, city, height_ft, width_m, lon, lat in BUILDINGS:
        height_m = round(height_ft * FT_TO_M, 1)
        props = {
            "name": name,
            "city": city,
            "height_ft": height_ft,
            "height_m": height_m,
            "color": CITY_META[city]["color"],
        }
        poly_features.append({
            "type": "Feature",
            "properties": props,
            "geometry": {
                "type": "Polygon",
                "coordinates": rect_polygon(lon, lat, width_m),
            },
        })
        label_features.append({
            "type": "Feature",
            "properties": {
                **props,
                "label": f"{name}\n{height_ft} ft",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat],
            },
        })

    poly_fc = {"type": "FeatureCollection", "features": poly_features}
    label_fc = {"type": "FeatureCollection", "features": label_features}

    poly_out = OUT_DIR / "reference_buildings.geojson"
    label_out = OUT_DIR / "reference_buildings_labels.geojson"

    poly_out.write_text(json.dumps(poly_fc, indent=2))
    label_out.write_text(json.dumps(label_fc, indent=2))

    print(f"wrote {poly_out} ({len(poly_features)} polygons)")
    print(f"wrote {label_out} ({len(label_features)} labels)")
    print("\nBuildings placed:")
    for name, city, h, _, lon, lat in BUILDINGS:
        print(f"  {city:7} {h:>4}ft  {name:40} @ ({lon}, {lat})")


if __name__ == "__main__":
    main()
