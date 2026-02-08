
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.getcwd())
try:
    from src.infrastructure.database.models import Client, Router
except ImportError:
    print("Error")
    sys.exit(1)

def verify_current_state():
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    print("--- ESTADO ACTUAL DE CLIENTES ---")
    
    names = ['Juan Pablo Barrios', 'Grabiela Alvarado', 'Leocadia Mora', 'Roman Pernia']
    for name in names:
        results = session.query(Client).filter(Client.legal_name.like(f'%{name}%')).all()
        print(f"\nBúsqueda: {name}")
        if not results:
            print("  ❌ NO ENCONTRADO (Posiblemente eliminado o fusionado)")
        for c in results:
            router = session.query(Router).get(c.router_id)
            print(f"  ✅ ID: {c.id} | Nombre: {c.legal_name} | IP: {c.ip_address} | Router: {router.alias if router else c.router_id} | Status: {c.status}")

    session.close()

if __name__ == "__main__":
    verify_current_state()
