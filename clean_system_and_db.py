
import os
import sqlite3
import datetime
import time

# Configuration
DB_FILE = "sgubm.db"
TEMP_FILES = [
    "sgubm_temp.db",
    "sgubm_audit.db",
    "sgubm_unlocked.db",
    "check_db_sizes.py"
]
LOG_FILE = "server_debug_fresh.log"
RETENTION_DAYS = 30

def clean_file_system():
    print("Cleaning unnecessary files...")
    for f in TEMP_FILES:
        if os.path.exists(f):
            try:
                os.remove(f)
                print(f"Deleted {f}")
            except Exception as e:
                print(f"Failed to delete {f}: {e}")
    
    if os.path.exists(LOG_FILE):
        try:
            # Truncate log file
            with open(LOG_FILE, 'w') as f:
                f.write("")
            print(f"Truncated {LOG_FILE}")
        except Exception as e:
            print(f"Failed to truncate log file: {e}")

def clean_database():
    print(f"\nCleaning database '{DB_FILE}' (keeping last {RETENTION_DAYS} days of history)...")
    if not os.path.exists(DB_FILE):
        print("Database not found!")
        return

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Count before
        cursor.execute("SELECT COUNT(*) FROM client_traffic_history")
        count_before = cursor.fetchone()[0]
        print(f"Rows before cleanup: {count_before}")
        
        # Calculate cutoff date
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=RETENTION_DAYS)
        print(f"Deleting records older than {cutoff_date}")
        
        # Delete old records
        # Assuming timestamp is stored as standard SQLite datetime string ISO8601
        cursor.execute("DELETE FROM client_traffic_history WHERE timestamp < ?", (cutoff_date,))
        deleted_count = cursor.rowcount
        print(f"Deleted {deleted_count} rows.")
        
        conn.commit()
        
        # Vacuum to reclaim space
        print("Vacuuming database (this might take a few seconds)...")
        cursor.execute("VACUUM")
        print("Vacuum complete.")
        
        # Count after
        cursor.execute("SELECT COUNT(*) FROM client_traffic_history")
        count_after = cursor.fetchone()[0]
        print(f"Rows after cleanup: {count_after}")
        
        conn.close()
        
        # Check new size
        size_mb = os.path.getsize(DB_FILE) / (1024 * 1024)
        print(f"New database size: {size_mb:.2f} MB")
        
    except Exception as e:
        print(f"Database error: {e}")

if __name__ == "__main__":
    clean_file_system()
    clean_database()
