
from src.infrastructure.database.models import Client, Payment, DeletedPayment, Invoice, AuditLog
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine('sqlite:///sgubm.db')
Session = sessionmaker(bind=engine)
session = Session()

client_id = 58

print(f"--- AUDITORIA PARA CLIENTE ID: {client_id} ---")

client = session.query(Client).get(client_id)
if client:
    print(f"Nombre: {client.legal_name} | Balance: {client.account_balance} | Cuota: {client.monthly_fee}")
    
    print("\n--- FACTURAS ---")
    invoices = session.query(Invoice).filter(Invoice.client_id == client_id).all()
    for i in invoices:
        print(f"ID: {i.id} | Fecha: {i.issue_date} | Vence: {i.due_date} | Total: {i.total_amount} | Status: {i.status}")
        
    print("\n--- PAGOS ACTIVOS ---")
    payments = session.query(Payment).filter(Payment.client_id == client_id).all()
    for p in payments:
        print(f"ID: {p.id} | Fecha: {p.payment_date} | Monto: {p.amount} | Status: {p.status} | Ref: {p.reference}")
        
    print("\n--- PAGOS ELIMINADOS (PAPELERA) ---")
    d_payments = session.query(DeletedPayment).filter(DeletedPayment.client_id == client_id).all()
    for dp in d_payments:
        print(f"ID: {dp.id} | Org ID: {dp.original_id} | Fecha Org: {dp.payment_date} | Monto: {dp.amount} | Razon: {dp.reason}")

else:
    print("Cliente no encontrado.")

session.close()
