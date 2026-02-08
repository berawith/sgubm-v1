
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.getcwd())
from src.infrastructure.database.models import Payment, Client

def check_specific():
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    p57 = session.query(Payment).get(57)
    p58 = session.query(Payment).get(58)

    print(f"Pago 57: ClientID={p57.client_id}, Monto={p57.amount}, Ref={p57.reference}")
    print(f"Pago 58: ClientID={p58.client_id}, Monto={p58.amount}, Ref={p58.reference}")

    c57 = session.query(Client).get(p57.client_id)
    c58 = session.query(Client).get(p58.client_id)

    print(f"Cliente 57: {c57.legal_name} (ID: {c57.id})")
    print(f"Cliente 58: {c58.legal_name} (ID: {c58.id})")

    session.close()

if __name__ == "__main__":
    check_specific()
