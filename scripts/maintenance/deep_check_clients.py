import os
import sys
sys.path.append(os.getcwd())
from src.infrastructure.database.models import Client, Payment, Invoice
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def deep_check_clients():
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    # Juan Pablo check
    jp_clients = session.query(Client).filter(Client.legal_name.like('%Juan Pablo%')).all()
    print(f"\n--- Juan Pablo Barrios Analysis ({len(jp_clients)} found) ---")
    for c in jp_clients:
        payment_count = session.query(Payment).filter(Payment.client_id == c.id).count()
        invoice_count = session.query(Invoice).filter(Invoice.client_id == c.id).count()
        print(f"ID: {c.id} | Code: {c.subscriber_code} | User: '{c.username}' | IP: {c.ip_address} | Balance: {c.account_balance} | Payments: {payment_count} | Invoices: {invoice_count}")

    # Grabiela check
    ga_clients = session.query(Client).filter(Client.legal_name.like('%Grabiela%')).all()
    print(f"\n--- Grabiela Alvarado Analysis ({len(ga_clients)} found) ---")
    for c in ga_clients:
        payment_count = session.query(Payment).filter(Payment.client_id == c.id).count()
        invoice_count = session.query(Invoice).filter(Invoice.client_id == c.id).count()
        print(f"ID: {c.id} | Code: {c.subscriber_code} | User: '{c.username}' | IP: {c.ip_address} | Balance: {c.account_balance} | Payments: {payment_count} | Invoices: {invoice_count}")

    session.close()

if __name__ == "__main__":
    deep_check_clients()
