
import sqlite3
import os

DB_PATH = 'sgubm.db'

def list_tables(cursor):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    return [r[0] for r in cursor.fetchall()]

def get_columns(cursor, table_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [r[1] for r in cursor.fetchall()]

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database {DB_PATH} not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        tables = list_tables(cursor)
        if 'client_traffic_history' not in tables:
            print("Table client_traffic_history does not exist. Skipping.")
            return

        columns = get_columns(cursor, 'client_traffic_history')
        print(f"Current columns: {columns}")

        # 1. Add is_online
        if 'is_online' not in columns:
            print("Adding is_online column...")
            cursor.execute("ALTER TABLE client_traffic_history ADD COLUMN is_online BOOLEAN DEFAULT 0")
        
        # 2. Add quality_score
        if 'quality_score' not in columns:
            print("Adding quality_score column...")
            cursor.execute("ALTER TABLE client_traffic_history ADD COLUMN quality_score FLOAT DEFAULT 100.0")

        # 3. Add latency_ms
        if 'latency_ms' not in columns:
            print("Adding latency_ms column...")
            cursor.execute("ALTER TABLE client_traffic_history ADD COLUMN latency_ms INTEGER DEFAULT 0")

        # 4. Add packet_loss_pct
        if 'packet_loss_pct' not in columns:
             print("Adding packet_loss_pct column...")
             cursor.execute("ALTER TABLE client_traffic_history ADD COLUMN packet_loss_pct FLOAT DEFAULT 0.0")

        conn.commit()
        print("Migration completed successfully.")

    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
