## Greenville Neighborhood Map — FastAPI + React Leaflet

Make maps, not excuses. This project stitches together a FastAPI backend (serving PostGIS → GeoJSON) and a modern React + Vite front‑end with Leaflet to explore Greenville’s neighborhoods, parcels, zoning, trails, and more. Bring your shapefiles, pour a coffee, and watch layers light up.

### ✨ What you get
- **FastAPI + PostGIS API**: Endpoints to list tables and stream GeoJSON with optional limits.
- **React + Leaflet UI**: Toggle layers, click features, export visible data.
- **Subdivision timeline**: Color subdivisions by first development date and scrub through years.
- **Importer scripts**: Seed your PostGIS database from `.shp` files and bootstrap zoning rules.

### 🗺️ Repo layout
- `api.py` — FastAPI app exposing `/tables`, `/geojson/{table}`, subdivision GeoJSON and stats.
- `database.py` — Async Postgres connection helper (env‑driven `DATABASE_URL`).
- `seeder_shp.py` — Bulk import `.shp` files into PostGIS tables and index geometry.
- `zoning_rules_setup.py` — Detect zoning codes in `zoning` table and seed `zoning_rules`.
- `greenville-map/` — Vite + React front‑end. Main viewer at `src/components/MapViewer.tsx`.
- `shapefiles/` — Put your `.shp` files here (already populated in this repo).

### ⚙️ Prerequisites
- Python 3.10+
- Node.js 18+ and npm
- PostgreSQL 13+ with PostGIS extension
- Windows, macOS, or Linux (this repo’s current path suggests Windows; commands below work cross‑platform)

### 🔑 Environment variables
Create a `.env` in the project root with your database connection string (PostgreSQL):

```bash
# .env
DATABASE_URL=postgresql://USERNAME:PASSWORD@localhost:5432/qgisdb
```

If your DB uses a different name/host/port, update accordingly. Ensure PostGIS is enabled in that database:

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
```

### 📦 Install backend deps
From the project root:

```bash
python -m venv .venv
.\.venv\Scripts\activate   # PowerShell on Windows
# source .venv/bin/activate  # macOS/Linux
pip install --upgrade pip
pip install fastapi uvicorn[standard] sqlalchemy asyncpg psycopg2-binary python-dotenv geopandas shapely fiona
```

Note: Geo stack wheels (geopandas/fiona/shapely) may require system GDAL/PROJ on macOS/Linux. On Windows, prebuilt wheels usually just work.

### 🧬 Seed your database from shapefiles (optional but recommended)
This will import every `.shp` in `shapefiles/` into its own table, create a spatial index, and log the import to `shapefile_imports`.

```bash
.\.venv\Scripts\activate   # or source .venv/bin/activate
python seeder_shp.py
```

After seeding, verify a few rows:

```sql
SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY 1;
```

If you have a `zoning` table, bootstrap human‑editable rules:

```bash
python zoning_rules_setup.py
```

That script will:
- Detect the most likely zoning code column (e.g., `ZONING`, `district`, etc.)
- Create `zoning_rules` if missing
- Insert one row per distinct zoning code with sensible defaults

Later, update the rules with real values from your codebook:

```sql
UPDATE zoning_rules SET min_lot_acres=0.23, min_frontage_ft=70 WHERE zoning_code='R-10';
```

### 🚀 Run the backend (FastAPI)
The React app expects the API at `http://localhost:8000` by default. Start it like this:

```bash
.\.venv\Scripts\activate   # or source .venv/bin/activate
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://localhost:8000/
```

You should see a JSON response with your Postgres version.

### 🖥️ Run the front‑end (Vite + React + Leaflet)

```bash
cd greenville-map
npm install
# Optional: point the UI to a different API base
echo VITE_API_BASE_URL=http://localhost:8000 > .env
npm run dev
```

Open the printed local URL (usually `http://localhost:5173`). You’ll see:
- Layer toggle panel (top‑right)
- Parcels pre‑loaded (if present)
- Optional subdivision timeline (enable via checkbox)

Tip: Click features for a quick property pop‑up. Use “Export visible” to download a combined GeoJSON of currently visible layers.

### 🧭 API reference (selected)
- `GET /` — DB connection check with version.
- `GET /tables` — List available public tables.
- `GET /geojson/{table_name}?limit=9000` — Stream a table as a GeoJSON FeatureCollection. Geometry is automatically transformed to EPSG:4326 in `api.py`.
- `GET /geojson/subdivisions` — Subdivision polygons as GeoJSON, unioned and transformed to EPSG:4326.
- `GET /subdivision_stats` — First/last development date, parcel count, and acres per subdivision.

Swagger UI is available at `http://localhost:8000/docs` when running with `--reload`.

### 🧑‍💼 Real‑world problems this solves
- **Faster land‑use and zoning decisions**: Instantly visualize parcels, zoning, and subdivisions to answer “what’s allowed here?” without hopping across systems.
- **Development history at a glance**: The subdivision timeline highlights when areas first developed, helping assess change, infill opportunities, and precedent.
- **One map for many datasets**: Consolidates shapefiles (parcels, zoning, trails, streets, etc.) into a single, searchable, clickable map instead of scattered files and PDFs.
- **Better infrastructure planning**: Overlay streets, sidewalks, trails, and water bodies with neighborhoods to prioritize capital projects where they’ll help most.
- **Risk and compliance checks**: Spot FEMA flood zones and other constraints early, reducing costly late‑stage surprises for applicants and staff.
- **Community engagement made visual**: Clear, shareable maps help residents understand proposals, current conditions, and trade‑offs.
- **Data interoperability**: Converts PostGIS layers to web‑ready GeoJSON, so teams can reuse the same data in dashboards, analyses, or other apps.
- **Faster pre‑application feasibility**: Developers and consultants can self‑serve basic due diligence—parcel counts, acreage, and zoning context—before formal submissions.

### 🧩 Configuration notes
- The front‑end reads `VITE_API_BASE_URL` at build time; the UI falls back to `http://localhost:8000`.
- `MapViewer.tsx` styles and colors for many common municipal layers are defined in code. Unknown tables get a neutral style.
- Extremely large layers: use the `limit` query to keep payloads small, or add bbox filtering to `api.py` if needed.

### 🛠️ Troubleshooting
- “DATABASE_URL not found”: ensure a `.env` exists at project root and that your shell session can read it.
- “relation … does not exist”: run `seeder_shp.py` first or confirm the expected tables exist.
- Geo stack install errors on macOS/Linux: install GDAL/PROJ via your package manager (Homebrew/apt) before pip installing `geopandas`/`fiona`.
- Front‑end can’t reach API: confirm `uvicorn` is listening on `:8000` and that `VITE_API_BASE_URL` matches.

### 🧪 Nice stretches (ideas)
- Add bbox filtering to `/geojson/{table}` (the scaffold exists in `main.py`).
- Persist map state (visible layers, center/zoom) to the URL.
- Add legends and per‑layer opacity controls.
- Hook in a simple analysis panel (e.g., parcel counts inside a drawn polygon).


### Images

<img width="954" height="474" alt="Screenshot 2025-09-30 164855" src="https://github.com/user-attachments/assets/5f05e4da-865e-460d-a066-9eec811cd65f" />

<img width="956" height="477" alt="Screenshot 2025-09-30 165414" src="https://github.com/user-attachments/assets/87d96486-b526-47e4-8d3f-bf2d2aaff866" />

<img width="956" height="478" alt="Screenshot 2025-09-30 165502" src="https://github.com/user-attachments/assets/3159a1ce-e996-4f23-82a9-f58c382500d9" />

