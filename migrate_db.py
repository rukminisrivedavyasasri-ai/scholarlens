import sqlite3
import os

db_path = "scholar_lens.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(document_chunks);")
    columns = [row[1] for row in cur.fetchall()]
    if "embedding" not in columns:
        print("Adding 'embedding' column to document_chunks table...")
        cur.execute("ALTER TABLE document_chunks ADD COLUMN embedding JSON;")
        conn.commit()
        print("Column added successfully.")
    else:
        print("'embedding' column already exists.")
    conn.close()
