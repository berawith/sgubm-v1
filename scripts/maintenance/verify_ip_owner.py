
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.getcwd())
from src.infrastructure.database.models import Client

def verify_ip_owner(ip):
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    clients = session.query(Client).filter(Client.ip_address.like(f"{ip}%")).all()
    
    if not clients:
        print(f"No se encontró nadie con la IP {ip}")
    else:
        for c in clients:
            print(f"ID: {c.id} | Nombre: {c.legal_name} | IP: {c.ip_address} | Router: {c.router_id}")

    session.close()

if __name__ == "__main__":
    verify_ip_owner("77.16.10.239")
