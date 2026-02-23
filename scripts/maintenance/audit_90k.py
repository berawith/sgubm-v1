
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.getcwd())
try:
    from src.infrastructure.database.models import Client, Payment
except ImportError:
    sys.exit(1)

def audit_90k_payments():
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    print("--- AUDITORÍA DE PAGOS DE $90,000 HOY (2026-02-06) ---")
    ps = session.query(Payment).filter(Payment.amount == 90000.0).all()
    
    for p in ps:
        client = session.query(Client).get(p.client_id)
        print(f"ID: {p.id} | Cliente: {client.legal_name if client else '??'} (ID: {p.client_id}) | Ref: {p.reference} | Nota: {p.notes} | Fecha: {p.payment_date}")

    session.close()

if __name__ == "__main__":
    audit_90k_payments()
