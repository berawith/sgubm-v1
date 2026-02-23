
from src.infrastructure.database.models import Client, Invoice, Payment
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine('sqlite:///sgubm.db')
Session = sessionmaker(bind=engine)
session = Session()

print("--- INVESTIGANDO A ROMAN PERNIA ---")
clients = session.query(Client).filter((Client.ip_address == '177.77.73.39') | (Client.legal_name.ilike('%Roman Pernia%'))).all()

for client in clients:
    print(f"\nCliente: {client.legal_name} (ID: {client.id})")
    print(f"IP: {client.ip_address} | Balance: {client.account_balance} | Fee: {client.monthly_fee}")
    print(f"Status: {client.status} | Subscriber Code: {client.subscriber_code}")
    
    invoices = session.query(Invoice).filter(Invoice.client_id == client.id).all()
    print(f"Facturas ({len(invoices)}):")
    for inv in invoices:
        print(f"  - ID: {inv.id} | Fecha: {inv.issue_date} | Vence: {inv.due_date} | Total: {inv.total_amount} | Status: {inv.status}")
        
    payments = session.query(Payment).filter(Payment.client_id == client.id).all()
    print(f"Pagos ({len(payments)}):")
    for p in payments:
        print(f"  - ID: {p.id} | Fecha: {p.payment_date} | Monto: {p.amount} | Ref: {p.reference} | Status: {p.status}")

session.close()
