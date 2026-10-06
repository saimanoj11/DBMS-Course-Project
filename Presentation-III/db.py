import mysql.connector
from mysql.connector import Error, errorcode
from contextlib import contextmanager
from config import Config

def get_raw_connection(include_db=True):
    """Establishes a raw connection to MySQL using Config."""
    cfg = Config.get_db_config(include_db=include_db)
    return mysql.connector.connect(**cfg)

@contextmanager
def get_db_cursor(commit=False, dictionary=True):
    """
    Context manager that yields a cursor and automatically handles commit/rollback and closing.
    Usage:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute(...)
    """
    conn = None
    cursor = None
    try:
        conn = get_raw_connection(include_db=True)
        cursor = conn.cursor(dictionary=dictionary)
        yield cursor
        if commit:
            conn.commit()
    except Error as e:
        if conn and commit:
            conn.rollback()
        raise e
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def execute_query(query, params=None, fetch_all=True, fetch_one=False, commit=False):
    """Helper to quickly execute a query and fetch results or return lastrowid / affected rows."""
    with get_db_cursor(commit=commit, dictionary=True) as cursor:
        cursor.execute(query, params or ())
        if commit:
            return cursor.lastrowid
        if fetch_one:
            return cursor.fetchone()
        if fetch_all:
            return cursor.fetchall()
        return None

def test_connection():
    """Tests the MySQL connection and returns a diagnostic dict."""
    try:
        conn = get_raw_connection(include_db=False)
        if conn.is_connected():
            cursor = conn.cursor()
            cursor.execute("SELECT VERSION()")
            ver = cursor.fetchone()[0]
            cursor.execute("SHOW DATABASES LIKE %s", (Config.DB_NAME,))
            db_exists = cursor.fetchone() is not None
            cursor.close()
            conn.close()
            return {
                "success": True,
                "version": ver,
                "database_exists": db_exists,
                "database_name": Config.DB_NAME,
                "user": Config.DB_USER,
                "host": Config.DB_HOST,
                "port": Config.DB_PORT
            }
    except Error as err:
        msg = str(err)
        hint = "Please check your MySQL credentials in .env file."
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            hint = f"Access denied for user '{Config.DB_USER}'. Please set the correct DB_PASSWORD in your .env file."
        elif err.errno == errorcode.CR_CONN_HOST_ERROR:
            hint = f"Could not connect to MySQL server at {Config.DB_HOST}:{Config.DB_PORT}. Ensure the MySQL service is running."
        return {
            "success": False,
            "error_code": getattr(err, 'errno', None),
            "error_message": msg,
            "hint": hint,
            "user": Config.DB_USER,
            "host": Config.DB_HOST,
            "port": Config.DB_PORT
        }

