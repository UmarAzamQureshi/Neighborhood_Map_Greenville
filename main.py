from fastapi import FastAPI
from database import get_connection
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from typing import Optional
import json

app = FastAPI()

@app.get("/")
async def root():
    conn = await get_connection()
    row = await conn.fetchrow("SELECT version();")
    await conn.close()
    return {"message": "Connected to DB!", "db_version": row["version"]}


# CORS - allow your dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5174",  # Vite default
        "http://localhost:3000",  # if using other ports
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_origins=["*"],  # allow all (use only for local dev!)
)
# ----------------------------
# Get table as GeoJSON (with optional bbox and limit)
# ----------------------------
@app.get("/geojson/{table_name}")
def get_geojson(table_name: str, bbox: Optional[str] = None, limit: int = 500):
    """
    bbox format: xmin,ymin,xmax,ymax (in WGS84 / 4326)
    limit: max number of features returned (default 500)
    """
    try:
        engine = get_engine()  # your existing DB engine helper
        with engine.connect() as conn:
            if bbox:
                parts = bbox.split(",")
                if len(parts) != 4:
                    raise HTTPException(status_code=400, detail="bbox must be xmin,ymin,xmax,ymax")
                xmin, ymin, xmax, ymax = map(float, parts)
                sql = f"""
                SELECT jsonb_build_object(
                    'type','FeatureCollection',
                    'features', COALESCE(
                        jsonb_agg(
                            jsonb_build_object(
                                'type','Feature',
                                'geometry', ST_AsGeoJSON(geometry)::jsonb,
                                'properties', to_jsonb(row) - 'geometry'
                            )
                        ), '[]'::jsonb
                    )
                )
                FROM (SELECT * FROM "{table_name}"
                      WHERE ST_Intersects(geometry, ST_MakeEnvelope({xmin}, {ymin}, {xmax}, {ymax}, 4326))
                      LIMIT {limit}) row;
                """
            else:
                sql = f"""
                SELECT jsonb_build_object(
                    'type','FeatureCollection',
                    'features', COALESCE(
                        jsonb_agg(
                            jsonb_build_object(
                                'type','Feature',
                                'geometry', ST_AsGeoJSON(geometry)::jsonb,
                                'properties', to_jsonb(row) - 'geometry'
                            )
                        ), '[]'::jsonb
                    )
                )
                FROM (SELECT * FROM "{table_name}" LIMIT {limit}) row;
                """

            result = conn.execute(text(sql))
            geojson = result.scalar()
            if not geojson:
                raise HTTPException(status_code=404, detail=f"No data found in table {table_name}")

            # result.scalar() can be a JSON string or a dict - normalize it
            if isinstance(geojson, str):
                geojson_obj = json.loads(geojson)
            else:
                geojson_obj = geojson

            return JSONResponse(content=geojson_obj)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))