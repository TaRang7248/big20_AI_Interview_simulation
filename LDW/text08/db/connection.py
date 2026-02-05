import sqlite3
import os

DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIR, "interview.db")

def get_connection():
    """Returns a connection to the SQLite database."""
    return sqlite3.connect(DB_PATH)

def init_db():
    """Initializes the database by executing all schema SQL files."""
    conn = get_connection()
    cursor = conn.cursor()

    schema_files = [
        "schema_auth.sql",
        "schema_interview.sql",
        "schema_stt.sql",
        "schema_evaluation.sql"
    ]

    print(f"Initializing database at: {DB_PATH}")

    for schema_file in schema_files:
        file_path = os.path.join(DB_DIR, schema_file)
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                sql_script = f.read()
                try:
                    cursor.executescript(sql_script)
                    print(f"Successfully executed: {schema_file}")
                except sqlite3.Error as e:
                    print(f"Error executing {schema_file}: {e}")
        else:
            print(f"Schema file not found: {schema_file}")

    conn.commit()
    conn.close()
    print("Database initialization complete.")

if __name__ == "__main__":
    init_db()
