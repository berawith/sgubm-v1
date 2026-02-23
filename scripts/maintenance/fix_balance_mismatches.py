
from src.infrastructure.database.models import Client, Invoice
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine('sqlite:///sgubm.db')
Session = sessionmaker(bind=engine)
session = Session()

clients_to_fix = [2, 9, 103, 196, 468]

print("--- ALINEANDO BALANCES CON FACTURAS PENDIENTES ---")

for cid in clients_to_fix:
    client = session.query(Client).get(cid)
    if not client:
        print(f"ID {cid} no encontrado.")
        continue
        
    unpaid_sum = sum(inv.total_amount for inv in session.query(Invoice).filter(
        Invoice.client_id == cid,
        Invoice.status == 'unpaid'
    ).all())
    
    old_balance = client.account_balance or 0.0
    client.account_balance = unpaid_sum
    
    print(f"Cliente: {client.legal_name} (ID {cid}) | Bal: {old_balance} -> {client.account_balance} (Ajustado a facturas)")

session.commit()
print("¡Balances alineados exitosamente!")
session.close()
