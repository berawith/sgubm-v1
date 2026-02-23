
from src.infrastructure.database.models import Client, Invoice, Payment, DeletedPayment
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

engine = create_engine('sqlite:///sgubm.db')
Session = sessionmaker(bind=engine)
session = Session()

print("--- INVESTIGANDO PAGOS ELIMINADOS Y RECIENTES ---")

# 1. Buscar en pagos eliminados
deleted = session.query(DeletedPayment).filter(DeletedPayment.amount == 90000).all()
print(f"\nPagos eliminados de 90k ({len(deleted)})")
for d in deleted:
    print(f"  - Original ID: {d.original_id} | Client ID: {d.client_id} | Fecha: {d.payment_date} | Borrado: {d.deleted_at}")

# 2. Buscar pagos de 90k en Feb 2026
feb_payments = session.query(Payment).filter(Payment.amount == 90000, Payment.payment_date >= datetime(2026, 2, 1)).all()
print(f"\nPagos de 90k en Feb 2026 ({len(feb_payments)})")
for p in feb_payments:
    c = session.query(Client).get(p.client_id)
    print(f"  - ID: {p.id} | Cliente: {c.legal_name if c else '??'} (ID: {p.client_id}) | Fecha: {p.payment_date}")

# 3. Ver el historial de auditoria para el cliente 58
from src.infrastructure.database.models import AuditLog
logs = session.query(AuditLog).filter(AuditLog.entity_id == 58, AuditLog.entity_type == 'client').order_by(AuditLog.timestamp.desc()).limit(10).all()
print(f"\nAuditoria reciente para ID 58:")
for l in logs:
    print(f"  - {l.timestamp} | {l.operation} | {l.description}")

session.close()
