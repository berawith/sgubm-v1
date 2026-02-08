
from src.infrastructure.database.models import Client, Payment
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
engine = create_engine('sqlite:///sgubm.db')
Session = sessionmaker(bind=engine)
session = Session()

# Verificar Roman Pernia ID 71 vs Grabiela
rp71 = session.query(Client).get(71)
if rp71:
    print(f"Roman Pernia (71) IP: {rp71.ip_address}")
    ps = session.query(Payment).filter(Payment.client_id == 71).all()
    for p in ps:
        print(f"  - Pago ID {p.id}: {p.amount}")

grabiela = session.query(Client).filter(Client.legal_name.ilike('%Grabiela%')).first()
if grabiela:
    print(f"Grabiela ({grabiela.id}) IP: {grabiela.ip_address}")
    ps = session.query(Payment).filter(Payment.client_id == grabiela.id).all()
    for p in ps:
        print(f"  - Pago ID {p.id}: {p.amount}")

session.close()
