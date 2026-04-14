#!/usr/bin/env python3
"""
Fetch SF Planning GIS layers from the public ArcGIS REST API.

Source:
    https://sfplanninggis.org/arcgiswa/rest/services/PlanningData/MapServer

Notes:
    The layer was wholesale republished on 2026-01-11 (day before the
    Family Zoning Plan took effect). The heights we get here are the
    post-FZP "Local Program" heights. We do NOT have the pre-FZP
    baseline from this endpoint.

Usage:
    python scripts/fetch_planning_layers.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

BASE = "https://sfplanninggis.org/arcgiswa/rest/services/PlanningData/MapServer"
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# (layer_id, friendly_name, where_clause)
LAYERS: list[tuple[int, str, str]] = [
    (5, "height_districts", "1=1"),
    (3, "zoning_districts", "1=1"),
    (4, "special_use_districts", "1=1"),
    (14, "coastal_zone", "1=1"),
    (26, "supervisor_districts_2022_2032", "1=1"),
    (39, "seismic_liquefaction", "1=1"),
    (41, "fema_flood_hazard", "1=1"),
]


def fetch_layer(layer_id: int, name: str, where: str) -> dict:
    """Pull every feature from a layer, paging past the server transfer limit."""
    all_features: list[dict] = []
    offset = 0
    page = 2000
    spatial_ref = None
    geometry_type = None

    while True:
        params = {
            "where": where,
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "geojson",
            "resultOffset": offset,
            "resultRecordCount": page,
        }
        url = f"{BASE}/{layer_id}/query?{urlencode(params)}"
        print(f"  GET {url[:110]}...")
        with urlopen(url, timeout=60) as resp:
            chunk = json.load(resp)

        feats = chunk.get("features", [])
        if not feats:
            break

        all_features.extend(feats)
        print(f"    got {len(feats)} features (total so far: {len(all_features)})")

        if len(feats) < page:
            break
        offset += page
        time.sleep(0.25)

    fc = {
        "type": "FeatureCollection",
        "name": name,
        "features": all_features,
    }
    return fc


def main() -> None:
    summary = []
    for layer_id, name, where in LAYERS:
        print(f"\n=== layer {layer_id}: {name} ===")
        try:
            fc = fetch_layer(layer_id, name, where)
        except Exception as exc:  # noqa: BLE001
            print(f"  FAILED: {exc}")
            summary.append((name, "FAILED", str(exc)))
            continue

        out = OUT_DIR / f"{name}.geojson"
        out.write_text(json.dumps(fc))
        count = len(fc["features"])
        size_kb = out.stat().st_size // 1024
        print(f"  wrote {out.name} ({count} features, {size_kb} KB)")
        summary.append((name, count, size_kb))

    print("\n=== summary ===")
    for row in summary:
        print("  " + "  ".join(str(x) for x in row))


if __name__ == "__main__":
    main()
