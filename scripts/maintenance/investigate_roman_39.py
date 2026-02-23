
from src.infrastructure.database.models import Client, Invoice, Payment
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine('sqlite:///sgubm.db')
Session = sessionmaker(bind=engine)
session = Session()

print("--- INVESTIGANDO ID 39 Y RELACIONES ---")

c39 = session.query(Client).get(39)
if c39:
    print(f"Cliente 39: {c39.legal_name} | IP: {c39.ip_address} | Balance: {c39.account_balance}")
    ps39 = session.query(Payment).filter(Payment.client_id == 39).all()
    print(f"Pagos ID 39 ({len(ps39)}):")
    for p in ps39:
        print(f"  - ID: {p.id} | Monto: {p.amount} | Fecha: {p.payment_date}")
else:
    print("No se encontró el Cliente 39.")

# Buscar por IP en toda la tabla
ip_clients = session.query(Client).filter(Client.ip_address == '177.77.73.39').all()
print(f"\nClientes con IP 177.77.73.39 ({len(ip_clients)}):")
for ic in ip_clients:
    print(f"  - ID: {ic.id} | Nombre: {ic.legal_name} | Balance: {ic.account_balance}")

session.close()
