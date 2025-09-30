import os
import asyncpg
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

DATABASE_URL = os.getenv("DATABASE_URL")

async def get_connection():
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL not found. Check your .env file.")
    return await asyncpg.connect(DATABASE_URL)
