import os
import hashlib
import geopandas as gpd
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy import create_engine, Column, Integer, String, text
from sqlalchemy.orm import declarative_base, sessionmaker

# -----------------------------
# Database setup
# -----------------------------
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://gisdbwatch:umar@localhost:5432/qgisdb"  
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


# -----------------------------
# Model for logging imports
# -----------------------------
class ShapefileImport(Base):
    __tablename__ = "shapefile_imports"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    checksum = Column(String)
    layer_name = Column(String)
    table_name = Column(String)


# -----------------------------
# Seeder function
# -----------------------------
def import_shapefile(filepath, table_name):
    session = SessionLocal()

    # Calculate checksum so we don't import duplicates
    with open(filepath, "rb") as f:
        checksum = hashlib.md5(f.read()).hexdigest()

    existing = session.query(ShapefileImport).filter_by(checksum=checksum).first()
    if existing:
        print(f"⚠️ Skipping {filepath}, already imported.")
        return

    try:
        # Read shapefile using GeoPandas
        print(f"📖 Reading {filepath}...")
        gdf = gpd.read_file(filepath)
        
        # Ensure CRS is set
        if gdf.crs is None:
            gdf.crs = "EPSG:4326"  # Default to WGS84
        
        # Connect to PostgreSQL and import
        print(f"📤 Importing to PostgreSQL table: {table_name}")
        
        # Parse connection string for psycopg2
        import re
        pattern = r"postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)"
        match = re.match(pattern, DATABASE_URL)
        if not match:
            raise ValueError("Invalid DATABASE_URL format")
        
        username, password, host, port, dbname = match.groups()
        
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host=host,
            port=int(port),
            database=dbname,
            user=username,
            password=password
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        
        # Drop table if it exists
        with conn.cursor() as cursor:
            cursor.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE;")
        
        # Write GeoDataFrame to PostGIS
        gdf.to_postgis(
            name=table_name,
            con=engine,
            if_exists="replace",  # overwrite if exists
            chunksize=10000  # Process in chunks for large files
        )
        
        # Add PostGIS geometry indexes for better performance
        with conn.cursor() as cursor:
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS {table_name}_geometry_idx 
                ON {table_name} USING GIST (geometry);
            """)
        
        conn.close()
        print(f"✅ Imported {filepath} -> table {table_name}")
        
    except Exception as e:
        print(f"❌ Error importing {filepath}: {e}")
        return

    # Log import into DB
    shapefile_import = ShapefileImport(
        filename=os.path.basename(filepath),
        checksum=checksum,
        layer_name=os.path.splitext(os.path.basename(filepath))[0],
        table_name=table_name
    )
    session.add(shapefile_import)
    session.commit()
    session.close()


# -----------------------------
# Main
# -----------------------------
if __name__ == "__main__":
    # Create table for logging imports if it doesn’t exist
    Base.metadata.create_all(bind=engine)

    shapefiles_dir = "shapefiles"  # 👈 put your shapefiles in this folder
    for filename in os.listdir(shapefiles_dir):
        if filename.endswith(".shp"):
            filepath = os.path.join(shapefiles_dir, filename)
            table_name = os.path.splitext(filename)[0].lower()
            import_shapefile(filepath, table_name)
