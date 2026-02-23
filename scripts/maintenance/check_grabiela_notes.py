
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.getcwd())
try:
    from src.infrastructure.database.models import Payment, Client
except ImportError:
    sys.exit(1)

def check_grabiela_payment():
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    grabiela = session.query(Client).filter(Client.legal_name.ilike('%Grabiela%')).first()
    if grabiela:
        print(f"Grabiela ID: {grabiela.id}")
        payments = session.query(Payment).filter(Payment.client_id == grabiela.id).all()
        for p in payments:
            print(f"Pago ID: {p.id} | Referencia: {p.reference} | Nota: {p.notes} | Fecha: {p.payment_date}")
    else:
        print("Grabiela no encontrada.")
    session.close()

if __name__ == "__main__":
    check_grabiela_payment()
