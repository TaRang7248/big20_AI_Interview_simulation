import psycopg2
import os
from dotenv import load_dotenv

# Load .env
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env'))

# DB settings
DB_HOST = "127.0.0.1"
DB_NAME = "interview_db"
DB_USER = "postgres"
DB_PASS = os.getenv("POSTGRES_PASSWORD", "013579")
DB_PORT = "5432"

try:
    print(f"Connecting to {DB_NAME} at {DB_HOST}...")
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        port=DB_PORT
    )
    c = conn.cursor()
    
    print("Connection successful.")
    
    # Check users table
    print("Checking 'users' table...")
    c.execute("SELECT id_name, name, type, pw FROM users")
    rows = c.fetchall()
    
    if not rows:
        print("No users found in the database. Please register a user first.")
    else:
        print(f"Found {len(rows)} users:")
        for row in rows:
            print(f" - ID: {row[0]}, Name: {row[1]}, Type: {row[2]}, PW Hash (prefix): {row[3][:10]}...")

    conn.close()

except Exception as e:
    print(f"Error: {e}")
