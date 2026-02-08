
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.getcwd())
try:
    from src.infrastructure.database.models import Client, Payment
except ImportError:
    sys.exit(1)

def check_grabiela_jp_payments():
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    print("--- DETALLE DE PAGOS DE GRABIELA (ID 543) ---")
    ps_g = session.query(Payment).filter(Payment.client_id == 543).all()
    for p in ps_g:
        print(f"ID: {p.id} | Monto: {p.amount} | Ref: {p.reference} | Nota: {p.notes} | Fecha: {p.payment_date}")

    print("\n--- DETALLE DE PAGOS DE JUAN PABLO (ID 86) ---")
    ps_jp = session.query(Payment).filter(Payment.client_id == 86).all()
    for p in ps_jp:
        print(f"ID: {p.id} | Monto: {p.amount} | Ref: {p.reference} | Nota: {p.notes} | Fecha: {p.payment_date}")

    print("\n--- OTROS PAGOS DE $90,000 SIN DUEÑO CLARO O RECIENTES ---")
    ps_90 = session.query(Payment).filter(Payment.amount == 90000.0).order_by(Payment.id.desc()).limit(10).all()
    for p in ps_90:
        c = session.query(Client).get(p.client_id)
        print(f"ID: {p.id} | Cliente: {c.legal_name if c else '??'} | Ref: {p.reference} | Fecha: {p.payment_date}")

    session.close()

if __name__ == "__main__":
    check_grabiela_jp_payments()
