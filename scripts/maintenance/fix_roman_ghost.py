
from src.infrastructure.database.models import Client, Payment, Invoice
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

engine = create_engine('sqlite:///sgubm.db')
Session = sessionmaker(bind=engine)
session = Session()

client_id = 58
ref = "5899"
amount = 90000.0

print(f"--- REPARANDO PAGO FANTASMA REF {ref} PARA CLIENTE {client_id} ---")

client = session.query(Client).get(client_id)
if not client:
    print("Error: Cliente no encontrado.")
    exit()

# 1. Crear el pago faltante
new_payment = Payment(
    client_id=client_id,
    amount=amount,
    payment_date=datetime(2026, 2, 11, 16, 49, 53),
    payment_method='transfer',
    reference=ref,
    notes="Restaurado por reconciliación técnica (Ghost Payment Fix)",
    status='verified'
)
session.add(new_payment)

# 2. Actualizar balance (Restar el pago)
old_balance = client.account_balance or 0.0
client.account_balance = old_balance - amount
client.last_payment_date = new_payment.payment_date

print(f"Balance: {old_balance} -> {client.account_balance}")

# 3. Aplicar a facturas unpaid si existen
unpaid_invoices = session.query(Invoice).filter(
    Invoice.client_id == client_id,
    Invoice.status == 'unpaid'
).order_by(Invoice.issue_date).all()

remaining = amount
for inv in unpaid_invoices:
    if remaining <= 0: break
    if remaining >= inv.total_amount:
        inv.status = 'paid'
        remaining -= inv.total_amount
        print(f"Factura #{inv.id} marcada como PAGADA")

session.commit()
print("¡Actualización exitosa!")
session.close()
