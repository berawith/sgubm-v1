
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.getcwd())
try:
    from src.infrastructure.database.models import Client
except ImportError:
    print("Error: No se pudieron importar los modelos.")
    sys.exit(1)

def investigate_mismatch():
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    print("--- INVESTIGACIÓN DE DISCREPANCIA ---")
    
    # 1. Buscar a Juan Pablo Barrios
    print("\n[1] Buscando por Nombre: 'Juan Pablo Barrios'")
    jp_clients = session.query(Client).filter(Client.legal_name.like('%Juan Pablo Barrios%')).all()
    if jp_clients:
        for c in jp_clients:
            print(f"ID: {c.id} | Nombre: {c.legal_name} | IP: {c.ip_address} | Codigo: {c.subscriber_code} | Status: {c.status}")
    else:
        print("No se encontró ningún cliente con ese nombre exacto.")

    # 2. Buscar por Código CLI-0086
    print("\n[2] Buscando por Código de Suscriptor: 'CLI-0086'")
    code_clients = session.query(Client).filter(Client.subscriber_code == 'CLI-0086').all()
    if code_clients:
        for c in code_clients:
            print(f"ID: {c.id} | Nombre: {c.legal_name} | IP: {c.ip_address} | Codigo: {c.subscriber_code} | Status: {c.status}")
    else:
        # Intentar sin el prefijo CLI- si existe
        code_clients = session.query(Client).filter(Client.subscriber_code.like('%0086')).all()
        for c in code_clients:
            print(f"ID: {c.id} | Nombre: {c.legal_name} | IP: {c.ip_address} | Codigo: {c.subscriber_code} | Status: {c.status}")

    # 3. Buscar quién más tiene la IP 77.16.10.239
    print("\n[3] Buscando todos los clientes con IP: 77.16.10.239")
    ip_clients = session.query(Client).filter(Client.ip_address.like('77.16.10.239%')).all()
    for c in ip_clients:
        print(f"ID: {c.id} | Nombre: {c.legal_name} | IP: {c.ip_address} | Codigo: {c.subscriber_code}")

    session.close()

if __name__ == "__main__":
    investigate_mismatch()
