# SF Family Zoning Plan — Data & 3D Map

The data, scripts, and interactive 3D map behind the Fogline article: **[NextDoor vs. Reality: What SF's new upzoning actually looks like](https://foglinesf.com)**

## What's here

- `scripts/` — Python scripts that pull, parse, and visualize SF Planning's zoning data
- `maps/3d_map.html` — Interactive 3D map of every height district in SF (MapLibre GL JS)
- `maps/03_height_ladder_full.png` — Height comparison chart: SF vs. Paris vs. Miami
- `data/derived/` — Parsed height data with base/local/delta columns

## How to run

```bash
# Install dependencies
uv sync

# Pull the raw data from SF Planning's public API
uv run python scripts/fetch_planning_layers.py

# Parse the X//Y-R-4 height labels
uv run python scripts/parse_heights.py

# Generate the height ladder chart
uv run python scripts/make_height_ladder.py

# Build the 3D map
uv run python scripts/make_3d_map.py

# Serve the 3D map locally
cd maps && python -m http.server 8765
# Open http://localhost:8765/3d_map.html
```

## Data source

SF Planning Department's public ArcGIS REST endpoint:
`sfplanninggis.org/arcgiswa/rest/services/PlanningData/MapServer`, Layer 5 (Height Districts)

No API keys required. No proprietary tools.

## Built with

Python, geopandas, shapely, matplotlib, MapLibre GL JS

## Author

Larry and Ashley — [Fogline](https://foglinesf.com)
