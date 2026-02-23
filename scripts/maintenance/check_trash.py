
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import DeletedPayment

def check_trash():
    db = get_db()
    deleted_repo = db.get_deleted_payment_repository()
    deleted = deleted_repo.get_all()
    print(f"Found {len(deleted)} deleted payments.")
    for d in deleted:
        print(f"ID: {d.id}, Amount: {d.amount}, Client: {d.client_name if d.client else 'None'}")

if __name__ == "__main__":
    check_trash()
