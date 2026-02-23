
from src.infrastructure.database.models import Client, Payment
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
engine = create_engine('sqlite:///sgubm.db')
Session = sessionmaker(bind=engine)
session = Session()

print("--- REASIGNANDO PAGO A ROMAN PERNIA ---")

# 1. Pago de 90k mas reciente bajo Juan Pablo que probablemente era de Roman
p217 = session.query(Payment).get(217)
roman = session.query(Client).filter(Client.legal_name.ilike('%Roman Pernia%')).first()

if p217 and roman:
    old_id = p217.client_id
    p217.client_id = roman.id
    print(f"✅ Pago ID 217 ($90,000) movido de ID {old_id} a {roman.legal_name} (ID: {roman.id})")
else:
    print("❌ No se encontró el pago o el cliente.")

session.commit()
session.close()
