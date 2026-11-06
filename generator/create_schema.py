import os
from dotenv import load_dotenv
import psycopg2

# Load credentials from .env
load_dotenv()

db_host = os.getenv("DB_HOST", "localhost")
db_port = os.getenv("DB_PORT", "5432")
db_name = os.getenv("DB_NAME", "paymentiq")
db_user = os.getenv("DB_USER", "postgres")
db_password = os.getenv("DB_PASSWORD", "")

# Connect to paymentiq database using psycopg2
conn = psycopg2.connect(
    host=db_host,
    port=db_port,
    dbname=db_name,
    user=db_user,
    password=db_password
)

# Read sql/01_schema.sql and execute the whole file in one call, then commit
sql_path = os.path.join(os.path.dirname(__file__), "..", "sql", "01_schema.sql")
with open(sql_path, "r", encoding="utf-8") as f:
    sql_script = f.read()

cur = conn.cursor()
cur.execute(sql_script)
conn.commit()

# Print for each schema (public, staging, truth) the list of table names
schemas = ["public", "staging", "truth"]
for schema in schemas:
    cur.execute(
        """
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = %s AND table_type = 'BASE TABLE'
        ORDER BY table_name;
        """,
        (schema,)
    )
    tables = [row[0] for row in cur.fetchall()]
    print(f"Schema '{schema}': {', '.join(tables) if tables else 'None'}")

# Print the number of foreign key constraints in the whole database
cur.execute(
    """
    SELECT COUNT(*) 
    FROM information_schema.table_constraints 
    WHERE constraint_type = 'FOREIGN KEY';
    """
)
fk_count = cur.fetchone()[0]
print(f"Total Foreign Key constraints: {fk_count}")

cur.close()
conn.close()

print("Schema created OK")
