import sys
import os
import argparse
import mysql.connector
from mysql.connector import Error, errorcode
from config import Config

def run_sql_file(cursor, filepath):
    """Executes a SQL file containing multiple statements."""
    if not os.path.exists(filepath):
        print(f"Error: SQL file '{filepath}' not found.")
        return False

    with open(filepath, 'r', encoding='utf-8') as f:
        sql = f.read()

    # Split statements by semicolon, being mindful of multi-line blocks
    statements = sql.split(';')
    for statement in statements:
        stmt = statement.strip()
        if stmt:
            try:
                cursor.execute(stmt)
            except Error as err:
                # Ignore warning/minor notices, fail on real errors
                print(f"Executing statement warning/error: {err}")
                print(f"Query: {stmt[:80]}...")
                raise err
    return True

def initialize_database(host=None, user=None, password=None, port=None, seed=True):
    host = host or Config.DB_HOST
    user = user or Config.DB_USER
    password = password if password is not None else Config.DB_PASSWORD
    port = port or Config.DB_PORT

    print("=" * 60)
    print(" Scholarship & Financial Aid Management - DB Initializer")
    print("=" * 60)
    print(f"Connecting to MySQL server at {host}:{port} as user '{user}'...")

    try:
        conn = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            port=port,
            autocommit=True
        )
        print("Connected to MySQL Server successfully!")
    except Error as err:
        print(f"\n[ERROR] Connection failed: {err}")
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("\nHint: Please update your password in .env or pass it as an argument:")
            print("  python init_db.py --password YOUR_MYSQL_PASSWORD")
        return False

    cursor = conn.cursor()
    base_dir = os.path.dirname(os.path.abspath(__file__))
    schema_path = os.path.join(base_dir, 'schema.sql')
    seed_path = os.path.join(base_dir, 'seed_data.sql')

    try:
        print(f"\n[1/3] Running Schema Script ({schema_path})...")
        run_sql_file(cursor, schema_path)
        print("Schema created/updated successfully!")

        if seed:
            print(f"\n[2/3] Seeding Initial Records ({seed_path})...")
            run_sql_file(cursor, seed_path)
            print("Seed data inserted successfully!")

        print("\n[3/3] Verifying Database Structure & Record Counts:")
        cursor.execute("USE `ScholarshipDB`;")
        tables = ['Students', 'Schemes', 'Bank_Details', 'Applications', 'Sanctions', 'Disbursements']
        for tbl in tables:
            cursor.execute(f"SELECT COUNT(*) FROM `{tbl}`;")
            count = cursor.fetchone()[0]
            print(f"  - Table '{tbl}': {count} rows")

        print("\nSUCCESS: ScholarshipDB is fully initialized and ready to use!")
        return True

    except Error as err:
        print(f"\n[ERROR] Failed during database setup: {err}")
        return False
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Initialize ScholarshipDB schema and seed data.")
    parser.add_argument('--host', default=None, help="MySQL Host (default from .env)")
    parser.add_argument('--user', default=None, help="MySQL User (default from .env)")
    parser.add_argument('--password', default=None, help="MySQL Password")
    parser.add_argument('--port', type=int, default=None, help="MySQL Port (default 3306)")
    parser.add_argument('--no-seed', action='store_true', help="Skip inserting sample data")

    args = parser.parse_args()
    success = initialize_database(
        host=args.host,
        user=args.user,
        password=args.password,
        port=args.port,
        seed=not args.no_seed
    )
    sys.exit(0 if success else 1)

