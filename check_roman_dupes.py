
from src.infrastructure.database.models import Client, Payment
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
engine = create_engine('sqlite:///sgubm.db')
Session = sessionmaker(bind=engine)
session = Session()

for rid in [58, 143]:
    c = session.query(Client).get(rid)
    if c:
        print(f"ID {rid}: {c.legal_name} | IP: {c.ip_address}")
        ps = session.query(Payment).filter(Payment.client_id == rid).all()
        for p in ps:
            print(f"  - Pago ID {p.id}: {p.amount}")

session.close()
