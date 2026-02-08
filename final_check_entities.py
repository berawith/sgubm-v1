
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.getcwd())
try:
    from src.infrastructure.database.models import Client, Payment, Invoice
except ImportError:
    sys.exit(1)

def check_current_entities():
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    print("--- ESTADO ACTUAL EN BASE DE DATOS ---")
    names = ['Juan Pablo Barrios', 'Grabiela Alvarado', 'Leocadia Mora']
    for name in names:
        results = session.query(Client).filter(Client.legal_name.ilike(f'%{name}%')).all()
        if not results:
            print(f"\n❌ {name}: No encontrado.")
        for c in results:
            print(f"\n✅ {c.legal_name} (ID: {c.id})")
            print(f"   IP: {c.ip_address} | Router: {c.router_id} | Cod: {c.subscriber_code}")
            
            # Listar pagos recientes para ver de qué IP provevían (basado en lógica de auditoría previa)
            payments = session.query(Payment).filter(Payment.client_id == c.id).all()
            for p in payments:
                print(f"      - Pago ID {p.id}: ${p.amount} | Ref: {p.reference} | Nota: {p.notes}")

    session.close()

if __name__ == "__main__":
    check_current_entities()
