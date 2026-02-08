
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.getcwd())
try:
    from src.infrastructure.database.models import Payment, Client
except ImportError:
    sys.exit(1)

def search_payments_meta():
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    print("Buscando 'Grabiela' o 'Alvarado' en notas de pago...")
    ps = session.query(Payment).filter(
        (Payment.notes.ilike('%Grabiela%')) | 
        (Payment.notes.ilike('%Alvarado%')) | 
        (Payment.reference.ilike('%06390%'))
    ).all()
    
    for p in ps:
        c = session.query(Client).get(p.client_id)
        print(f"Pago ID: {p.id} | Cliente: {c.legal_name if c else p.client_id} | Ref: {p.reference} | Nota: {p.notes}")

    session.close()

if __name__ == "__main__":
    search_payments_meta()
