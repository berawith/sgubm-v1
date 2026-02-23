
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.getcwd())
try:
    from src.infrastructure.database.models import Client, Router
except ImportError:
    sys.exit(1)

def list_suspicious_clients():
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    print("--- LISTA DE CLIENTES FILTRADA ---")
    clients = session.query(Client).filter(Client.legal_name.ilike('%Grabiela%')).all()
    for c in clients:
        r = session.query(Router).get(c.router_id)
        print(f"ID: {c.id} | Name: {c.legal_name} | IP: {c.ip_address} | Router: {r.alias if r else 'NA'} | Status: {c.status}")

    print("\n--- CLIENTE ROMAN PERNIA ---")
    clients = session.query(Client).filter(Client.legal_name.ilike('%Roman Pernia%')).all()
    for c in clients:
        r = session.query(Router).get(c.router_id)
        print(f"ID: {c.id} | Name: {c.legal_name} | IP: {c.ip_address} | Router: {r.alias if r else 'NA'} | Status: {c.status}")

    session.close()

if __name__ == "__main__":
    list_suspicious_clients()
