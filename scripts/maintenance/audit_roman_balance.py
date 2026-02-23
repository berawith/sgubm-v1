
from src.infrastructure.database.models import Client, AuditLog
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine('sqlite:///sgubm.db')
Session = sessionmaker(bind=engine)
session = Session()

print("--- AUDITORIA DE BALANCE PARA ID 58 ---")
logs = session.query(AuditLog).filter(
    AuditLog.entity_id == 58, 
    AuditLog.entity_type == 'client',
    AuditLog.description.ilike('%balance%')
).all()

for l in logs:
    print(f"  - {l.timestamp} | {l.operation} | {l.description}")

print("\n--- BUSCANDO DUPLICADOS POR USERNAME O SUBSCRIBER_CODE ---")
c58 = session.query(Client).get(58)
if c58:
    dupes = session.query(Client).filter(
        (Client.username == c58.username) | 
        (Client.subscriber_code == c58.subscriber_code)
    ).filter(Client.id != 58).all()
    
    print(f"Buscando duplicados para Username: {c58.username} | Code: {c58.subscriber_code}")
    for d in dupes:
        print(f"  - ID: {d.id} | Name: {d.legal_name} | Balance: {d.account_balance}")
else:
    print("No se encontró el Cliente 58.")

session.close()
