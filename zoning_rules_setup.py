import os
from typing import Optional, Tuple, List
from sqlalchemy import create_engine, text


def get_engine():
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://gisdbwatch:umar@localhost:5432/qgisdb",
    )
    return create_engine(database_url)


def zoning_table_exists(conn) -> bool:
    sql = text(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'zoning'
        LIMIT 1;
        """
    )
    return conn.execute(sql).first() is not None


def detect_zoning_code_column(conn) -> Optional[str]:
    # Prefer common column names first (case-insensitive)
    candidate_names = [
        "ZONING",
        "zoning",
        "ZONE",
        "zone",
        "zone_code",
        "zonecode",
        "z_code",
        "district",
        "DISTRICT",
    ]

    # Pull actual columns
    cols = conn.execute(
        text(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'zoning'
            ORDER BY ordinal_position;
            """
        )
    ).fetchall()
    existing_cols = {row[0]: row[1] for row in cols}

    # Try exact matches (case sensitive + insensitive variants)
    for c in candidate_names:
        if c in existing_cols:
            return c
        # try exact insensitive by scanning
        for actual in existing_cols.keys():
            if actual.lower() == c.lower():
                return actual

    # Fallback: choose the first textual column with reasonably small distinct count
    text_like_cols = [
        c for c, t in existing_cols.items() if t in ("character varying", "text", "character")
    ]
    best_col = None
    best_count = None
    for c in text_like_cols:
        count = conn.execute(
            text(f'SELECT COUNT(DISTINCT "{c}") FROM "zoning"')
        ).scalar()
        if best_count is None or (count is not None and count < best_count):
            best_count = count
            best_col = c
    return best_col


def fetch_distinct_codes(conn, code_col: str) -> List[str]:
    rows = conn.execute(
        text(
            f'''
            SELECT DISTINCT trim("{code_col}") AS code
            FROM "zoning"
            WHERE "{code_col}" IS NOT NULL AND trim("{code_col}") <> ''
            ORDER BY 1;
            '''
        )
    ).fetchall()
    return [r[0] for r in rows if r[0] is not None]


def create_rules_table(conn):
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS zoning_rules (
                zoning_code VARCHAR PRIMARY KEY,
                min_lot_acres NUMERIC,
                min_frontage_ft NUMERIC,
                allowed_subdivision BOOLEAN
            );
            """
        )
    )


def allowed_subdivision_default(code: str) -> bool:
    # Heuristic default: residential codes often start with R/RS/RM/RD
    upper = (code or "").strip().upper()
    return upper.startswith("R") or upper.startswith("RS") or upper.startswith("RM") or upper.startswith("RD")


def seed_rules(conn, codes: List[str]):
    if not codes:
        print("No zoning codes found to seed.")
        return
    values = [
        {
            "code": code,
            "min_lot_acres": None,
            "min_frontage_ft": None,
            "allowed": allowed_subdivision_default(code),
        }
        for code in codes
    ]
    conn.execute(
        text(
            """
            INSERT INTO zoning_rules (zoning_code, min_lot_acres, min_frontage_ft, allowed_subdivision)
            VALUES (:code, :min_lot_acres, :min_frontage_ft, :allowed)
            ON CONFLICT (zoning_code) DO NOTHING;
            """
        ),
        values,
    )


def main():
    engine = get_engine()
    with engine.begin() as conn:
        if not zoning_table_exists(conn):
            raise RuntimeError("Table 'zoning' not found in schema 'public'.")

        code_col = detect_zoning_code_column(conn)
        if not code_col:
            raise RuntimeError("Could not detect a zoning code column on table 'zoning'.")
        print(f"Detected zoning code column: {code_col}")

        codes = fetch_distinct_codes(conn, code_col)
        print(f"Found {len(codes)} distinct zoning codes.")

        create_rules_table(conn)
        seed_rules(conn, codes)
        print("Seeded zoning_rules with detected codes.\n")

        print("Next steps:")
        print("- Update 'zoning_rules' with actual min_lot_acres and min_frontage_ft from your codebook.")
        print("  Example: UPDATE zoning_rules SET min_lot_acres=0.23, min_frontage_ft=70 WHERE zoning_code='R-10';")


if __name__ == "__main__":
    main()


