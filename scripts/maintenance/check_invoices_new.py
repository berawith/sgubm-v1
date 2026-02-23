
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Invoice

def check_invoices():
    db = get_db()
    session = db.session
    new_ids = [591, 592, 593, 594]
    invoices = session.query(Invoice).filter(Invoice.client_id.in_(new_ids)).all()
    
    print(f"--- Invoices for IDs {new_ids} ---")
    for inv in invoices:
        print(f"ID: {inv.id}, ClientID: {inv.client_id}, Amount: {inv.total_amount}, Paid: {inv.is_paid}, Date: {inv.created_at}")

if __name__ == "__main__":
    check_invoices()
