import psycopg2

DB_CONFIG = {
    'dbname': 'student_portal',
    'user': 'postgres',
    'password': 'hello123019',
    'host': 'host.docker.internal',
    'port': '5432',
}

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

parent_dir = 'D:\Myrepo\student-portal'