import psycopg2

from db_config import DB_CONFIG

try:
    conn = psycopg2.connect(**DB_CONFIG)
    print("Connected!")
except Exception as e:
    print("Error:", e)
finally:
    conn.close()
