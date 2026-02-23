
from src.infrastructure.database.models import Client, Payment, DeletedPayment, Invoice, AuditLog
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine('sqlite:///sgubm.db')
Session = sessionmaker(bind=engine)
session = Session()

search_val = "217"
search_int = 217

print(f"--- BUSCANDO GLOBALMENTE: {search_val} ---")

# Search Clients
clients = session.query(Client).filter(
    (Client.id == search_int) | 
    (Client.subscriber_code.ilike(f"%{search_val}%")) |
    (Client.username.ilike(f"%{search_val}%"))
).all()
for c in clients:
    print(f"[Client] ID: {c.id} | Code: {c.subscriber_code} | Name: {c.legal_name}")

# Search Payments
payments = session.query(Payment).filter(Payment.id == search_int).all()
for p in payments:
    print(f"[Payment] ID: {p.id} | Client ID: {p.client_id} | Amount: {p.amount}")

# Search DeletedPayments
d_payments = session.query(DeletedPayment).filter(
    (DeletedPayment.id == search_int) | (DeletedPayment.original_id == search_int)
).all()
for dp in d_payments:
    print(f"[DeletedPayment] ID: {dp.id} | Org ID: {dp.original_id} | Client ID: {dp.client_id} | Amount: {dp.amount}")

# Search Invoices
invoices = session.query(Invoice).filter(
    (Invoice.id == search_int) | (Invoice.invoice_number.ilike(f"%{search_val}%"))
).all()
for i in invoices:
    print(f"[Invoice] ID: {i.id} | Num: {i.invoice_number} | Client ID: {i.client_id} | Total: {i.total_amount}")

# Search AuditLogs
logs = session.query(AuditLog).filter(
    (AuditLog.entity_id == search_int) | (AuditLog.description.ilike(f"%{search_val}%"))
).all()
for l in logs:
    print(f"[AuditLog] ID: {l.id} | Entity: {l.entity_type}({l.entity_id}) | Op: {l.operation} | Desc: {l.description}")

session.close()
