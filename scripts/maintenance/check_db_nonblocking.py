
import sqlite3
import os

def check_db_direct():
    db_path = "sgubm.db"
    print(f"Checking database at {os.path.abspath(db_path)}")
    try:
        # Use a very short timeout to detect locks
        conn = sqlite3.connect(db_path, timeout=1)
        cursor = conn.cursor()
        
        print("Fetching client count...")
        cursor.execute("SELECT COUNT(*) FROM clients")
        count = cursor.fetchone()[0]
        print(f"Clients: {count}")
        
        print("Fetching accounting log count...")
        cursor.execute("SELECT COUNT(*) FROM audit_logs WHERE category = 'accounting'")
        log_count = cursor.fetchone()[0]
        print(f"Accounting Logs: {log_count}")
        
        conn.close()
    except sqlite3.OperationalError as e:
        print(f"DATABASE LOCKED: {e}")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    check_db_direct()
