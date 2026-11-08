import os
import sys
import dotenv
import pandas as pd
import psycopg2

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dotenv.load_dotenv(os.path.join(PROJECT_DIR, ".env"))

if len(sys.argv) < 2:
    print("Usage: python generator/run_sql.py <sql_file> [output_file]")
    sys.exit(1)

sql_arg = sys.argv[1]
out_arg = sys.argv[2] if len(sys.argv) > 2 else None

if os.path.isabs(sql_arg):
    sql_path = sql_arg
elif os.path.exists(os.path.join(os.getcwd(), sql_arg)):
    sql_path = os.path.join(os.getcwd(), sql_arg)
else:
    sql_path = os.path.join(PROJECT_DIR, sql_arg)

conn = psycopg2.connect(
    host=os.getenv("DB_HOST", "localhost"),
    port=os.getenv("DB_PORT", "5432"),
    dbname=os.getenv("DB_NAME", "paymentiq"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", "123456"),
)
conn.autocommit = False
cur = conn.cursor()

with open(sql_path, "r", encoding="utf-8") as f:
    sql_content = f.read()

output_lines = []

def record_print(text=""):
    print(text)
    output_lines.append(str(text))

has_checks = any(line.strip().startswith("-- CHECK:") for line in sql_content.splitlines())

if has_checks:
    raw_blocks = sql_content.split("-- CHECK:")
    for b in raw_blocks[1:]:
        block_text = "-- CHECK:" + b
        lines = block_text.strip().splitlines()
        
        check_name = lines[0].replace("--", "").strip()
        comment_lines = [l.strip() for l in lines if l.strip().startswith("--")]
        query_lines = [l for l in lines if not l.strip().startswith("--")]
        query = "\n".join(query_lines).strip()
        
        record_print(f"=== {check_name} ===")
        for c in comment_lines:
            record_print(c)
        
        cur.execute(query)
        cols = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        df_res = pd.DataFrame(rows, columns=cols)
        record_print(df_res.to_string(index=False))
        record_print("")
else:
    cur.execute(sql_content)
    conn.commit()
    record_print(f"Executed {sql_arg} successfully.")

if out_arg:
    if os.path.isabs(out_arg):
        out_path = out_arg
    elif os.path.exists(os.path.join(os.getcwd(), os.path.dirname(out_arg))):
        out_path = os.path.join(os.getcwd(), out_arg)
    else:
        out_path = os.path.join(PROJECT_DIR, out_arg)
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))

cur.close()
conn.close()
