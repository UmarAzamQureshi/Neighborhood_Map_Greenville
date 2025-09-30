from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os
import json

# ----------------------------
# Database setup
# ----------------------------
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://gisdbwatch:umar@localhost:5432/qgisdb"  # 👈 adjust if needed
)

def get_engine():
    """Lazy engine creation to avoid connection issues during import"""
    return create_engine(DATABASE_URL)

def get_session():
    """Lazy session creation"""
    engine = get_engine()
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal

# ----------------------------
# FastAPI app
# ----------------------------
app = FastAPI(title="GIS API", version="1.0")

# CORS for local dev (allow Vite dev server)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    # Test DB connection
    engine = get_engine()
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version();")).scalar()
    return {"message": "Connected to DB!", "db_version": version}


# ----------------------------
# List available tables
# ----------------------------
@app.get("/tables")
def list_tables():
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """))
        tables = [row[0] for row in result]
    return {"tables": tables}


# ----------------------------
# Subdivision endpoints
# ----------------------------
@app.get("/geojson/subdivisions")
def get_subdivisions():
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT "SUBDIV" AS subdiv,
                       ST_AsGeoJSON(
                           ST_Transform(
                               ST_UnaryUnion(ST_Union(geometry)),
                               4326
                           )
                       ) AS geom
                FROM "parcels"
                WHERE "SUBDIV" IS NOT NULL
                GROUP BY "SUBDIV";
            """))
            rows = result.mappings().all()

        features = []
        for row in rows:
            if not row["geom"]:
                continue
            features.append({
                "type": "Feature",
                "geometry": json.loads(row["geom"]),
                "properties": {"subdivision": row["subdiv"]}
            })

        return {"type": "FeatureCollection", "features": features}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/subdivision_stats")
def get_subdivision_stats():
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT "SUBDIV" AS subdiv,
                       MIN("PDDATE") AS first_date,
                       MAX("PDDATE") AS last_date,
                       COUNT(*) AS parcel_count,
                       SUM("GIS_ACRES") AS total_acres
                FROM "parcels"
                WHERE "SUBDIV" IS NOT NULL
                GROUP BY "SUBDIV"
                ORDER BY first_date;
            """))
            rows = result.mappings().all()
        return [dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ----------------------------
# Get table as GeoJSON
# ----------------------------
@app.get("/geojson/{table_name}")
def get_geojson(table_name: str, limit: int = 9000):
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text(f"""
                SELECT jsonb_build_object(
                    'type', 'FeatureCollection',
                    'features', COALESCE(
                        jsonb_agg(
                            jsonb_build_object(
                                'type', 'Feature',
                                'geometry', ST_AsGeoJSON(ST_Transform(geometry, 4326))::jsonb,
                                'properties', to_jsonb(row) - 'geometry'
                            )
                        ),
                        '[]'::jsonb
                    )
                )
                FROM (SELECT * FROM "{table_name}" LIMIT {limit}) row;
            """))
            geojson = result.scalar()
            if not geojson:
                raise HTTPException(status_code=404, detail=f"No data found in table {table_name}")
        return geojson
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/geojson/subdivisions")
def get_subdivisions():
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT SUBDIV,
                       ST_AsGeoJSON(ST_Union(geometry)) AS geom
                FROM "parcels"
                WHERE SUBDIV IS NOT NULL
                GROUP BY SUBDIV;
            """))
            rows = result.mappings().all()

        features = []
        for row in rows:
            if not row["geom"]:
                continue
            features.append({
                "type": "Feature",
                "geometry": json.loads(row["geom"]),
                "properties": {"subdivision": row["subdiv"]}
            })

        return {"type": "FeatureCollection", "features": features}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/subdivision_stats")
def get_subdivision_stats():
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT SUBDIV,
                       MIN(PDDATE) AS first_date,
                       MAX(PDDATE) AS last_date,
                       COUNT(*) AS parcel_count,
                       SUM(GIS_ACRES) AS total_acres
                FROM "parcels"
                WHERE SUBDIV IS NOT NULL
                GROUP BY SUBDIV
                ORDER BY first_date;
            """))
            rows = result.mappings().all()
        return [dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
