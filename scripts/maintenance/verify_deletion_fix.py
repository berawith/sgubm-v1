
from src.infrastructure.database.db_manager import get_db
import logging

# Configure logging to see SQLAlchemy actions
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('sqlalchemy.engine')
logger.setLevel(logging.INFO)

def verify_deletion(client_id):
    db = get_db()
    client_repo = db.get_client_repository()
    
    print(f"Attempting to delete client {client_id} (Global Delete simulation)...")
    try:
        success = client_repo.delete(client_id)
        if success:
            print("SUCCESS: Client deleted correctly.")
        else:
            print("FAILED: Client not found or deletion failed.")
    except Exception as e:
        print(f"ERROR during deletion: {e}")

if __name__ == "__main__":
    verify_deletion(5)
