
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client, Payment, Invoice, DeletedPayment

def investigate_client(subscriber_code):
    db = get_db()
    session = db.session
    
    client = session.query(Client).filter(Client.subscriber_code == subscriber_code).first()
    if not client:
        print(f"Client {subscriber_code} not found.")
        return

    print(f"--- Client Info ---")
    print(f"ID: {client.id}")
    print(f"Name: {client.legal_name}")
    print(f"Code: {client.subscriber_code}")
    print(f"Fee: {client.monthly_fee}")
    print(f"Balance: {client.account_balance}")
    print(f"Status: {client.status}")

    print(f"\n--- Invoices ---")
    invoices = session.query(Invoice).filter(Invoice.client_id == client.id).all()
    total_invoiced = 0
    for inv in invoices:
        print(f"ID: {inv.id}, Date: {inv.issue_date}, Total: {inv.total_amount}, Status: {inv.status}")
        total_invoiced += inv.total_amount
    print(f"Total Invoiced: {total_invoiced}")

    print(f"\n--- Payments (Active) ---")
    payments = session.query(Payment).filter(Payment.client_id == client.id).all()
    total_paid = 0
    for p in payments:
        print(f"ID: {p.id}, Date: {p.payment_date}, Amount: {p.amount}, Status: {p.status}, Ref: {p.reference}")
        total_paid += p.amount
    print(f"Total Paid: {total_paid}")

    print(f"\n--- Deleted Payments ---")
    deleted_payments = session.query(DeletedPayment).filter(DeletedPayment.client_id == client.id).all()
    for dp in deleted_payments:
        print(f"Original ID: {dp.original_id}, Date: {dp.payment_date}, Amount: {dp.amount}, Deleted at: {dp.deleted_at}, Reason: {dp.reason}")

    print(f"\n--- Calculation ---")
    print(f"Theoretical Balance (Invoiced - Paid): {total_invoiced - total_paid}")

if __name__ == "__main__":
    investigate_client("CLI-0009")
