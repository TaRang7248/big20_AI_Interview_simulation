import sqlite3
import os

db_path = r'C:\big20\big20_AI_Interview_simulation\LDW\text02\db\interview.db'
if not os.path.exists(db_path):
    print(f"File not found: {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get table names
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print(f"Tables: {tables}")

for table in tables:
    table_name = table[0]
    print(f"\nSchema for table: {table_name}")
    cursor.execute(f"PRAGMA table_info({table_name});")
    info = cursor.fetchall()
    for col in info:
        print(col)
    
    print(f"\nSample data from {table_name}:")
    cursor.execute(f"SELECT * FROM {table_name} LIMIT 5;")
    rows = cursor.fetchall()
    for row in rows:
        print(row)

conn.close()
