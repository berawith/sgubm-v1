
from src.infrastructure.database.models import Client, Invoice, Payment
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine('sqlite:///sgubm.db')
Session = sessionmaker(bind=engine)
session = Session()

print("--- BUSCANDO POSIBLES DUPLICADOS O PAGOS PERDIDOS ---")

# Buscar cualquier cliente con "Roman" o "Pernia"
roman_clients = session.query(Client).filter(Client.legal_name.ilike('%Roman%') | Client.legal_name.ilike('%Pernia%')).all()
for c in roman_clients:
    print(f"Cliente: {c.legal_name} (ID: {c.id}) | IP: {c.ip_address} | Balance: {c.account_balance}")
    ps = session.query(Payment).filter(Payment.client_id == c.id).all()
    if ps:
        for p in ps:
            print(f"  - Pago ID: {p.id} | Monto: {p.amount} | Fecha: {p.payment_date}")

# Buscar el Pago 217 específicamente
p217 = session.query(Payment).get(217)
if p217:
    owner = session.query(Client).get(p217.client_id)
    print(f"\nPago 217 (ID: {p217.id}) | Monto: {p217.amount}")
    print(f"Dueño actual: {owner.legal_name if owner else '??'} (ID: {p217.client_id})")
else:
    print("\nNo se encontró el Pago 217.")

# Verificar si hay facturas de 90k unpaid para otros "romanes"
all_invoices = session.query(Invoice).filter(Invoice.total_amount == 90000, Invoice.status == 'unpaid').all()
print(f"\nFacturas de 90k unpaid ({len(all_invoices)})")

session.close()
