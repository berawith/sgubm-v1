from sqlalchemy import create_engine, text
import logging

# Config
DB_URL = 'sqlite:///sgubm.db'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_schema():
    engine = create_engine(DB_URL)
    connection = engine.connect()
    
    try:
        # Check if columns exist
        result = connection.execute(text("PRAGMA table_info(clients)"))
        columns = [row[1] for row in result.fetchall()]
        
        if 'is_online' not in columns:
            logger.info("Adding 'is_online' column...")
            connection.execute(text("ALTER TABLE clients ADD COLUMN is_online BOOLEAN DEFAULT 0"))
        else:
            logger.info("'is_online' column already exists.")

        if 'last_seen' not in columns:
            logger.info("Adding 'last_seen' column...")
            connection.execute(text("ALTER TABLE clients ADD COLUMN last_seen DATETIME"))
        else:
            logger.info("'last_seen' column already exists.")
            
        logger.info("Schema update completed successfully.")
        
    except Exception as e:
        logger.error(f"Error updating schema: {e}")
    finally:
        connection.close()

if __name__ == "__main__":
    update_schema()
