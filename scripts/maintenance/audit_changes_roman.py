
from src.infrastructure.database.models import Client, Invoice, AuditLog
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta

engine = create_engine('sqlite:///sgubm.db')
Session = sessionmaker(bind=engine)
session = Session()

client_id = 58
three_days_ago = datetime.now() - timedelta(days=3)

print(f"--- AUDITORIA DE AUDIT_LOGS PARA ID {client_id} (Ultimos 3 dias) ---")
logs = session.query(AuditLog).filter(
    (AuditLog.entity_id == client_id) & (AuditLog.entity_type == 'client') |
    (AuditLog.description.ilike(f"%{client_id}%"))
).filter(AuditLog.timestamp >= three_days_ago).all()

for l in logs:
    print(f"{l.timestamp} | {l.operation} | {l.description}")

print(f"\n--- FACTURAS CANCELADAS PARA ID {client_id} ---")
cancelled_invoices = session.query(Invoice).filter(Invoice.client_id == client_id, Invoice.status == 'cancelled').all()
for i in cancelled_invoices:
    print(f"ID: {i.id} | Fecha: {i.issue_date} | Total: {i.total_amount} | Status: {i.status}")

session.close()
