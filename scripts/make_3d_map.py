#!/usr/bin/env python3
"""
Prep data for a MapLibre GL JS 3D extrusion map and write the standalone
HTML viewer to maps/3d_map.html.

Strategy:
  - Load parsed height_districts geojson
  - Simplify geometry to shrink wire size for the browser
  - Convert heights from feet to meters (MapLibre extrusion wants meters)
  - Strip unneeded fields
  - Write a smaller geojson to maps/data/height_districts_web.geojson
  - Write a standalone HTML file that loads it and extrudes it
"""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd

ROOT = Path(__file__).resolve().parent.parent
DERIVED = ROOT / "data" / "derived"
MAPS = ROOT / "maps"
WEB_DATA = MAPS / "data"
WEB_DATA.mkdir(exist_ok=True)

FT_TO_M = 0.3048


def prep_geojson() -> Path:
    src = DERIVED / "height_districts_parsed.geojson"
    gdf = gpd.read_file(src)
    print(f"loaded {len(gdf)} features, CRS={gdf.crs}")

    # Drop rows where we can't extrude (unparsed labels, sentinels)
    gdf = gdf[
        gdf["base_ft"].notna()
        & (gdf["base_ft"] < 2000)
        & gdf["local_ft"].notna()
        & (gdf["local_ft"] < 2000)
    ].copy()
    print(f"after filtering sentinels: {len(gdf)}")

    # Simplify geometry to shrink file
    # In EPSG:4326 units are degrees; ~0.00003 deg ≈ 3m at SF latitude
    before = gdf.to_json().__len__()
    gdf["geometry"] = gdf["geometry"].simplify(0.00004, preserve_topology=True)
    gdf = gdf[gdf["geometry"].notna() & ~gdf["geometry"].is_empty]

    # Convert heights to meters
    gdf["base_m"] = (gdf["base_ft"] * FT_TO_M).round(1)
    gdf["local_m"] = (gdf["local_ft"] * FT_TO_M).round(1)
    gdf["delta_m"] = (gdf["delta_ft"] * FT_TO_M).round(1)

    # Keep only fields we need on the web side
    keep = ["height", "base_ft", "local_ft", "delta_ft", "base_m", "local_m", "delta_m", "condition", "geometry"]
    gdf = gdf[[c for c in keep if c in gdf.columns]]

    out = WEB_DATA / "height_districts_web.geojson"
    gdf.to_file(out, driver="GeoJSON")
    after = out.stat().st_size
    print(f"wrote {out}")
    print(f"  before simplify: ~{before // 1024} KB")
    print(f"  after  simplify: ~{after // 1024} KB")
    print(f"  features: {len(gdf)}")
    return out


HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>SF Family Zoning Plan — 3D height map (Fogline)</title>
<meta name="viewport" content="width=device-width, initial-scale=1" />
<link href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css" rel="stylesheet" />
<style>
  html, body { margin: 0; padding: 0; height: 100%; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }
  #map { position: absolute; inset: 0; }
  .overlay {
    position: absolute; top: 14px; left: 14px;
    background: rgba(20, 20, 24, 0.82);
    color: #f5f3ee;
    padding: 14px 16px;
    border-radius: 8px;
    max-width: 340px;
    box-shadow: 0 3px 14px rgba(0,0,0,0.3);
    font-size: 13px;
    line-height: 1.45;
    backdrop-filter: blur(4px);
  }
  .overlay h1 {
    font-size: 15px; margin: 0 0 4px 0; font-weight: 700;
  }
  .overlay p { margin: 4px 0; }
  .legend {
    position: absolute; bottom: 18px; left: 14px;
    background: rgba(20, 20, 24, 0.85);
    color: #f5f3ee;
    padding: 10px 12px;
    border-radius: 8px;
    font-size: 12px;
  }
  .legend-row { display: flex; align-items: center; margin: 3px 0; }
  .legend-sw { width: 20px; height: 10px; margin-right: 8px; border: 1px solid #222; }
  .popup { font-size: 13px; line-height: 1.5; }
  .popup b { color: #4a1f08; }
  .byline {
    position: absolute; bottom: 18px; right: 14px;
    background: rgba(20, 20, 24, 0.82);
    color: #f5f3ee;
    padding: 8px 12px;
    border-radius: 8px;
    font-size: 11px;
  }
  .byline a { color: #9ec9ff; text-decoration: none; }
</style>
</head>
<body>
<div id="map"></div>

<div class="overlay">
  <h1>San Francisco in 3D — what the Family Zoning Plan actually allows</h1>
  <p>Each block is extruded to its maximum permitted height under the Family Zoning Plan.</p>
  <p>Grey blocks = no change. Colored blocks = FZP <i>family-housing bonus</i> raised the cap. Taller + redder = bigger jump.</p>
  <p><b>Drag</b> to pan · <b>right-drag</b> to tilt/rotate · <b>scroll</b> to zoom · <b>click</b> a block for details.</p>
</div>

<div class="legend">
  <div class="legend-row"><div class="legend-sw" style="background:#bdbdbd"></div>no FZP bonus (Δ = 0 ft)</div>
  <div class="legend-row"><div class="legend-sw" style="background:#ffe08a"></div>+10 to +30 ft</div>
  <div class="legend-row"><div class="legend-sw" style="background:#fdae61"></div>+30 to +60 ft</div>
  <div class="legend-row"><div class="legend-sw" style="background:#f46d43"></div>+60 to +120 ft</div>
  <div class="legend-row"><div class="legend-sw" style="background:#a50026"></div>+120 ft and up</div>
</div>

<div class="byline">
  Data: SF Planning · built by <a href="https://foglinesf.com" target="_blank">Fogline</a>
</div>

<script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
<script>
const map = new maplibregl.Map({
  container: 'map',
  // Positron-style vector basemap from MapTiler's open-sourced demo tiles
  style: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
  center: [-122.445, 37.770],
  zoom: 12.2,
  pitch: 60,
  bearing: -20,
  antialias: true,
  maxPitch: 80,
});

map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right');
map.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-right');

map.on('load', () => {
  map.addSource('heights', {
    type: 'geojson',
    data: 'data/height_districts_web.geojson',
  });

  // Color expression on delta_ft
  const colorExpr = [
    'interpolate',
    ['linear'],
    ['coalesce', ['get', 'delta_ft'], 0],
    0,   '#bdbdbd',
    10,  '#ffe08a',
    30,  '#fdae61',
    60,  '#f46d43',
    120, '#d73027',
    250, '#a50026',
    400, '#67001f',
  ];

  // Extrusion height = local_m; base = 0 (ground)
  map.addLayer({
    id: 'heights-3d',
    type: 'fill-extrusion',
    source: 'heights',
    paint: {
      'fill-extrusion-color': colorExpr,
      'fill-extrusion-height': ['coalesce', ['get', 'local_m'], 0],
      'fill-extrusion-base': 0,
      'fill-extrusion-opacity': 0.92,
    },
  });

  // Thin outline layer
  map.addLayer({
    id: 'heights-outline',
    type: 'line',
    source: 'heights',
    paint: {
      'line-color': '#333',
      'line-width': 0.3,
      'line-opacity': 0.5,
    },
  });

  // Click popup
  map.on('click', 'heights-3d', (e) => {
    const f = e.features[0];
    const p = f.properties;
    const delta = p.delta_ft ?? 0;
    const baseF = p.base_ft ?? '—';
    const localF = p.local_ft ?? '—';
    const label = p.height ?? '—';
    const cond = p.condition ?? '';
    const html = `
      <div class="popup">
        <b>Height district: ${label}</b><br>
        Base: ${baseF} ft &nbsp; → &nbsp; Local Program: ${localF} ft<br>
        Bonus: ${delta > 0 ? '+' + delta + ' ft' : 'none'}<br>
        ${cond ? 'Condition: ' + cond : ''}
      </div>`;
    new maplibregl.Popup({ offset: 8 }).setLngLat(e.lngLat).setHTML(html).addTo(map);
  });

  map.on('mouseenter', 'heights-3d', () => { map.getCanvas().style.cursor = 'pointer'; });
  map.on('mouseleave', 'heights-3d', () => { map.getCanvas().style.cursor = ''; });
});
</script>
</body>
</html>
"""


def main() -> None:
    prep_geojson()
    html_path = MAPS / "3d_map.html"
    html_path.write_text(HTML)
    print(f"wrote {html_path}")
    print("\nTo view:")
    print(f"  cd {MAPS}")
    print("  python -m http.server 8000")
    print("  open http://localhost:8000/3d_map.html")


if __name__ == "__main__":
    main()
