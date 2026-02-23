
import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    try:
        conn = sqlite3.connect('sgubm.db')
        cursor = conn.cursor()

        # Add promise_date to clients
        try:
            cursor.execute("ALTER TABLE clients ADD COLUMN promise_date DATETIME")
            logger.info("Column 'promise_date' added to 'clients' table.")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                logger.info("Column 'promise_date' already exists in 'clients' table.")
            else:
                logger.error(f"Error adding 'promise_date': {e}")

        # Check for billing columns in routers (added in previous migrations but let's be sure)
        router_cols = ["billing_day", "grace_period", "cut_day"]
        for col in router_cols:
            try:
                cursor.execute(f"ALTER TABLE routers ADD COLUMN {col} INTEGER DEFAULT 1")
                logger.info(f"Column '{col}' added to 'routers' table.")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e).lower():
                    logger.info(f"Column '{col}' already exists in 'routers' table.")
                else:
                    logger.error(f"Error adding '{col}': {e}")

        conn.commit()
        conn.close()
        logger.info("Migration completed successfully.")
    except Exception as e:
        logger.error(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate()
