import sqlite3
import os

db_path = r'C:\big20\big20_AI_Interview_simulation\LDW\text08\db\interview.db'

if not os.path.exists(db_path):
    print(f"Error: {db_path} does not exist.")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # List tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Tables:", tables)
    
    for table_name in tables:
        print(f"\nSchema for {table_name[0]}:")
        cursor.execute(f"PRAGMA table_info({table_name[0]})")
        columns = cursor.fetchall()
        for col in columns:
            print(col)
            
    # Check sample data for interview_results if it exists
    if ('interview_results',) in tables:
        print("\nSample data from interview_results:")
        cursor.execute("SELECT * FROM interview_results LIMIT 1")
        print(cursor.fetchone())

    conn.close()
