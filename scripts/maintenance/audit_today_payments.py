
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.getcwd())
try:
    from src.infrastructure.database.models import Client, Payment
except ImportError:
    sys.exit(1)

def audit_all_recent_payments():
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    print("--- PAGOS DEL 2026-02-06 ---")
    ps = session.query(Payment).filter(Payment.payment_date >= '2026-02-06 00:00:00').order_by(Payment.id).all()
    
    for p in ps:
        client = session.query(Client).get(p.client_id)
        name = client.legal_name if client else "CLIENTE BORRADO"
        code = client.subscriber_code if client else "???"
        print(f"ID: {p.id} | Cliente: {name} ({code}) | Monto: {p.amount} | Ref: {p.reference} | Hora: {p.payment_date}")

    session.close()

if __name__ == "__main__":
    audit_all_recent_payments()
