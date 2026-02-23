
from src.infrastructure.database.models import Client, Invoice, Payment, PaymentPromise
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine('sqlite:///sgubm.db')
Session = sessionmaker(bind=engine)
session = Session()

print("--- REVISIÓN DETALLADA DE ROMAN PERNIA (ID 58) ---")
c = session.query(Client).get(58)
print(f"Nombre: {c.legal_name}")
print(f"Balance: {c.account_balance}")
print(f"Promise Date: {c.promise_date}")
print(f"Broken Promises: {c.broken_promises_count}")

print("\n--- FACTURAS ---")
invs = session.query(Invoice).filter(Invoice.client_id == 58).all()
for i in invs:
    print(f"ID: {i.id} | Fecha: {i.issue_date} | Total: {i.total_amount} | Status: {i.status}")

print("\n--- HISTORIAL DE PROMESAS ---")
proms = session.query(PaymentPromise).filter(PaymentPromise.client_id == 58).all()
for p in proms:
    print(f"ID: {p.id} | Fecha: {p.promise_date} | Creada: {p.created_at} | Status: {p.status}")

print("\n--- ÚLTIMOS PAGOS GENERALES (por si acaso) ---")
recent_payments = session.query(Payment).order_by(Payment.id.desc()).limit(20).all()
for rp in recent_payments:
    print(f"Pago ID: {rp.id} | Client ID: {rp.client_id} | Amount: {rp.amount} | Date: {rp.payment_date}")

session.close()
