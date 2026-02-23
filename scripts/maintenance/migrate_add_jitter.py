import sqlite3
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = 'sgubm.db'

def migrate():
    if not os.path.exists(DB_PATH):
        logger.error(f"Database {DB_PATH} not found.")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Verificar si la columna ya existe
        cursor.execute("PRAGMA table_info(client_traffic_history)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'jitter_ms' not in columns:
            logger.info("Adding jitter_ms column to client_traffic_history...")
            cursor.execute("ALTER TABLE client_traffic_history ADD COLUMN jitter_ms FLOAT DEFAULT 0.0")
            conn.commit()
            logger.info("Migration successful.")
        else:
            logger.info("Column jitter_ms already exists.")

        conn.close()
    except Exception as e:
        logger.error(f"Migration error: {e}")

if __name__ == "__main__":
    migrate()
