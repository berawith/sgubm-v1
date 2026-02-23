
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client, Payment, Invoice

def check_zulay_details():
    db = get_db()
    session = db.session
    
    zulay = session.query(Client).filter(Client.subscriber_code == 'CLI-0330').first()
    if not zulay:
        print("Zulay not found.")
        return
        
    print(f"--- Invoices for Zulay (ID: {zulay.id}) ---")
    invoices = session.query(Invoice).filter(Invoice.client_id == zulay.id).all()
    for inv in invoices:
        print(f"ID: {inv.id}, Amount: {inv.total_amount}, Date: {inv.issue_date}, Status: {inv.status}")
    
    print(f"\n--- Payments for Zulay ---")
    payments = session.query(Payment).filter(Payment.client_id == zulay.id).all()
    for p in payments:
        print(f"ID: {p.id}, Amount: {p.amount}, Date: {p.payment_date}, Ref: {p.reference}")

if __name__ == "__main__":
    check_zulay_details()
