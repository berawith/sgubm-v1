import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import traceback

# Asegurar que podemos importar los módulos
sys.path.append(os.getcwd())

from src.infrastructure.database.models import Client, Router
from src.infrastructure.database.db_manager import init_db, get_session

def test_clients():
    print("--- INICIANDO DIAGNÓSTICO DE CLIENTES ---")
    try:
        engine = init_db()
        Session = sessionmaker(bind=engine)
        session = Session()
        
        clients = session.query(Client).all()
        print(f"Total clientes encontrados: {len(clients)}")
        
        for i, client in enumerate(clients):
            print(f"\n[Cliente {client.id}]")
            print(f"  - Nombre: {client.legal_name}")
            print(f"  - Router ID: {client.router_id}")
            print(f"  - Status (Raw): {client.status} (Type: {type(client.status)})")
            
            # Probar relación
            try:
                r = client.router
                print(f"  - Relación Router: {r.alias if r else 'None'}")
            except Exception as e:
                print(f"  ! ERROR en relación Router: {e}")

            # Probar to_dict
            try:
                d = client.to_dict()
                print("  - to_dict(): OK")
            except Exception as e:
                print(f"  ! ERROR en to_dict(): {e}")
                traceback.print_exc()
                
    except Exception as e:
        print(f"!!! ERROR CRÍTICO DE BASE DE DATOS: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_clients()
