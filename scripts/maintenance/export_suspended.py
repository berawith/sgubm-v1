
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client, Invoice
from datetime import datetime

db = get_db()
session = db.session
now = datetime.now()

# Buscamos clientes que tienen facturas vencidas antes de hoy a las 6pm
# que es cuando hicimos el cambio masivo.
cutoff_time = datetime(2026, 2, 5, 18, 0, 0)

# Un cliente estaba suspendido si tenía al menos una factura impaga con fecha de vencimiento <= ahora
# y no tenía una promesa de pago vigente *antes* de que la cambiáramos.
# Como ya cambiamos la promesa de todos a mañana 6pm, buscamos esa coincidencia.

query = session.query(Client).join(Invoice).filter(
    Invoice.status == 'unpaid',
    Invoice.due_date <= cutoff_time,
    Client.promise_date == datetime(2026, 2, 6, 18, 0, 0)
).distinct()

results = query.all()

with open('clientes_que_estaban_cortados.txt', 'w', encoding='utf-8') as f:
    f.write(f"Clientes que estaban suspendidos o por suspenderse hoy ({len(results)}):\n")
    f.write("-" * 50 + "\n")
    for c in results:
        f.write(f"{c.legal_name} (@{c.username}) - Deuda: ${c.account_balance}\n")

print(f"Exportados {len(results)} clientes a clientes_que_estaban_cortados.txt")
