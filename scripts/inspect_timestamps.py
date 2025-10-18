import pymysql
from datetime import datetime

DB_HOST = '127.0.0.1'
DB_PORT = 3306
DB_USER = 'fh_admin'
DB_PASS = 'SqlP@ss8'
DB_NAME = 'PhotoDB2025v1'

conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS, database=DB_NAME)
try:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM files")
        total = cur.fetchone()[0]
        print('total rows in files:', total)
        cur.execute("SELECT path, created_at, updated_at FROM files LIMIT 5")
        rows = cur.fetchall()
        for path, created_at, updated_at in rows:
            print('\npath:', path)
            print(' created_at:', created_at)
            print(' updated_at:', updated_at)
        cur.execute("SELECT COUNT(*) FROM files WHERE updated_at = created_at")
        same = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM files WHERE updated_at != created_at")
        diff = cur.fetchone()[0]
        print('\nrows with updated_at == created_at:', same)
        print('rows with updated_at != created_at:', diff)
finally:
    conn.close()
