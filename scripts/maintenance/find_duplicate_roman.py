
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Payment

def find_duplicate_payment():
    db = get_db()
    session = db.session
    # Roman is ID 58
    payments = session.query(Payment).filter(Payment.client_id == 58).all()
    
    print("--- Payments for Roman (ID 58) ---")
    for p in payments:
        print(f"ID: {p.id}, Amount: {p.amount}, Date: {p.payment_date}, Ref: {p.reference}, Status: {p.status}")

if __name__ == "__main__":
    find_duplicate_payment()
