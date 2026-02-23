
from src.infrastructure.database.models import Client, Invoice, AuditLog
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine('sqlite:///sgubm.db')
Session = sessionmaker(bind=engine)
session = Session()

print("--- VERIFICACIÓN FINAL ---")
c = session.query(Client).get(58)
print(f"Cliente: {c.legal_name}")
print(f"Balance Actual: {c.account_balance}")

# Verificar facturas impagas
unpaid_count = session.query(Invoice).filter(Invoice.client_id == 58, Invoice.status == 'unpaid').count()
print(f"Facturas Impagas: {unpaid_count}")

# Verificar log de auditoría
latest_log = session.query(AuditLog).filter(AuditLog.entity_id == 58).order_by(AuditLog.timestamp.desc()).first()
print(f"Último Log: {latest_log.timestamp} | {latest_log.description}")

if c.account_balance == 90000.0 and unpaid_count == 1:
    print("\n✅ VERIFICACIÓN EXITOSA: La deuda es de 90,000 y coincide con la factura pendiente.")
else:
    print("\n❌ ERROR EN VERIFICACIÓN: Los datos no coinciden.")

session.close()
