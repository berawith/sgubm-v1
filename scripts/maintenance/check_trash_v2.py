
import sys
import os

# Set path to project root
sys.path.append(os.path.abspath("c:/SGUBM-V1"))

from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import DeletedPayment

def check_trash():
    db = get_db()
    deleted_repo = db.get_deleted_payment_repository()
    deleted = deleted_repo.get_all()
    print(f"Found {len(deleted)} deleted payments.")
    for d in deleted:
        try:
            client_name = d.client.legal_name if d.client else 'None'
            print(f"ID: {d.id}, Amount: {d.amount}, Client: {client_name}")
            print(f"Dict: {d.to_dict()}")
        except Exception as e:
            print(f"Error accessing payment {d.id}: {e}")

if __name__ == "__main__":
    check_trash()
