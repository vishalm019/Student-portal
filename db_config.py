import psycopg2

DB_CONFIG = {
    'dbname': 'devboard',
    'user': 'postgres',
    'password': 'hello123019',
    'host': 'localhost',
    'port': '5432',
}

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()