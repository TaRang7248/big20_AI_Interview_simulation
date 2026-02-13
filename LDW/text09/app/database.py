import psycopg2
from fastapi import HTTPException
from .config import DB_HOST, DB_NAME, DB_USER, DB_PASS, DB_PORT, logger

def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT,
            connect_timeout=3
        )
        return conn
    except psycopg2.OperationalError as e:
        logger.error(f"DB Connection Failed: {e}")
        raise HTTPException(status_code=500, detail="Database connection failed")
