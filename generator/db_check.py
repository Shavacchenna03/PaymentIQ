import os
from dotenv import load_dotenv
import psycopg2
from sqlalchemy import create_engine, text

# Load credentials from .env
load_dotenv()

db_host = os.getenv("DB_HOST", "localhost")
db_port = os.getenv("DB_PORT", "5432")
db_user = os.getenv("DB_USER", "postgres")
db_password = os.getenv("DB_PASSWORD", "")
target_db = os.getenv("DB_NAME", "paymentiq")

# Connect to the default "postgres" database using psycopg2
conn = psycopg2.connect(
    host=db_host,
    port=db_port,
    user=db_user,
    password=db_password,
    dbname="postgres"
)
conn.autocommit = True

cur = conn.cursor()
cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (target_db,))
exists = cur.fetchone()

if not exists:
    cur.execute(f'CREATE DATABASE "{target_db}";')
    print(f"Database '{target_db}' created.")
else:
    print(f"Database '{target_db}' already exists.")

cur.close()
conn.close()

# Connect to "paymentiq" using SQLAlchemy and run SELECT version();
database_url = f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{target_db}"
engine = create_engine(database_url)

with engine.connect() as connection:
    result = connection.execute(text("SELECT version();"))
    version = result.scalar()
    print(version)
    print("DB connection OK")
