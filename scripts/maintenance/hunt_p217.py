
from src.infrastructure.database.models import AuditLog, Payment
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine('sqlite:///sgubm.db')
Session = sessionmaker(bind=engine)
session = Session()

print("--- BUSCANDO PAGO 217 EN AUDITORIA ---")
logs = session.query(AuditLog).filter(
    (AuditLog.description.ilike('%217%')) |
    (AuditLog.entity_id == 217) & (AuditLog.entity_type == 'payment')
).all()

for l in logs:
    print(f"ID: {l.id} | Timestamp: {l.timestamp} | {l.operation} | {l.description}")

print("\n--- BUSCANDO TODOS LOS PAGOS RECIENTES DE ROMAN (ID 58) ---")
payments = session.query(Payment).filter(Payment.client_id == 58).all()
for p in payments:
    print(f"ID: {p.id} | Amount: {p.amount} | Date: {p.payment_date} | Status: {p.status if hasattr(p, 'status') else 'N/A'}")

session.close()
