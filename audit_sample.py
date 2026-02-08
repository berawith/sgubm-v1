
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client, Invoice, InvoiceItem, Payment
from sqlalchemy import text

def audit_marilu():
    db = get_db()
    session = db.session
    
    # 1. Client data
    client = session.query(Client).filter(Client.legal_name.like('%Marilu%')).first()
    if not client:
        print("Client not found")
        return
        
    print(f"--- Audit for {client.legal_name} ({client.id}) ---")
    print(f"Subscriber Code: {client.subscriber_code}")
    print(f"Monthly Fee: {client.monthly_fee}")
    print(f"Current Balance: {client.account_balance}")
    print(f"Created At: {client.created_at}")
    print(f"Updated At: {client.updated_at}")
    
    # 2. Invoices
    invoices = session.query(Invoice).filter(Invoice.client_id == client.id).all()
    print(f"\nInvoices ({len(invoices)}):")
    inv_total = 0
    for inv in invoices:
        print(f"  ID: {inv.id}, Date: {inv.issue_date}, Total: {inv.total_amount}, Created: {inv.created_at}")
        inv_total += inv.total_amount
        
    # 3. Payments
    payments = session.query(Payment).filter(Payment.client_id == client.id).all()
    print(f"\nPayments ({len(payments)}):")
    pay_total = 0
    for p in payments:
        print(f"  ID: {p.id}, Date: {p.payment_date}, Amount: {p.amount}, Created: {p.created_at}")
        pay_total += p.amount
        
    # 4. Calculation
    calculated = inv_total - pay_total
    print(f"\nExpected Balance (Invoices - Payments): {calculated}")
    print(f"Actual Balance: {client.account_balance}")
    print(f"Difference (Discrepancy): {client.account_balance - calculated}")

if __name__ == "__main__":
    audit_marilu()
