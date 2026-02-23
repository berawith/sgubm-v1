
from src.infrastructure.database.models import Client, Payment, DeletedPayment, Invoice, AuditLog
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta

engine = create_engine('sqlite:///sgubm.db')
Session = sessionmaker(bind=engine)
session = Session()

client_id = 58
days = 10
since = datetime.now() - timedelta(days=days)

print(f"--- DIAGNOSTICO COMPLETO ID {client_id} (Ultimos {days} dias) ---")

# 1. Pagos Activos
print("\n[PAGOS ACTIVOS]")
ps = session.query(Payment).filter(Payment.client_id == client_id).all()
for p in ps:
    print(f"ID: {p.id} | Ref: {p.reference} | Status: {p.status} | Monto: {p.amount} | Fecha: {p.payment_date}")

# 2. Pagos Eliminados
print("\n[PAGOS ELIMINADOS]")
dps = session.query(DeletedPayment).filter(DeletedPayment.client_id == client_id).all()
for dp in dps:
    print(f"ID: {dp.id} | OrgID: {dp.original_id} | Ref: {dp.reference} | Monto: {dp.amount} | Fecha Org: {dp.payment_date} | Borrado: {dp.deleted_at}")

# 3. Facturas
print("\n[FACTURAS]")
invs = session.query(Invoice).filter(Invoice.client_id == client_id).all()
for i in invs:
    print(f"ID: {i.id} | Fecha: {i.issue_date} | Total: {i.total_amount} | Status: {i.status}")

# 4. Auditoria
print("\n[AUDITORIA DESTACADA]")
logs = session.query(AuditLog).filter(
    (AuditLog.entity_id == client_id) | (AuditLog.description.ilike(f"%{client_id}%"))
).filter(AuditLog.timestamp >= since).order_by(AuditLog.timestamp.asc()).all()
for l in logs:
    print(f"{l.timestamp} | {l.operation} | {l.description}")

session.close()
