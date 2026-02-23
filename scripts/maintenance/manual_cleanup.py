
import sqlite3
import datetime
import os

DB_FILE = "sgubm.db"
RETENTION_DAYS = 7  # Keep only last 7 days

def clean_database():
    print(f"Cleaning database '{DB_FILE}' (keeping last {RETENTION_DAYS} days)...")
    if not os.path.exists(DB_FILE):
        print("Database not found!")
        return

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Calculate cutoff date
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=RETENTION_DAYS)
        print(f"Deleting records older than {cutoff_date}")
        
        # Delete old records
        cursor.execute("DELETE FROM client_traffic_history WHERE timestamp < ?", (cutoff_date,))
        deleted_count = cursor.rowcount
        print(f"Deleted {deleted_count} rows.")
        
        conn.commit()
        
        # Vacuum
        print("Vacuuming database...")
        cursor.execute("VACUUM")
        print("Vacuum complete.")
        
        conn.close()
        
        size_mb = os.path.getsize(DB_FILE) / (1024 * 1024)
        print(f"New database size: {size_mb:.2f} MB")
        
    except Exception as e:
        print(f"Database error: {e}")

if __name__ == "__main__":
    clean_database()
