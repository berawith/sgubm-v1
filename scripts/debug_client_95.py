
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client, Router

def check_client():
    db = get_db()
    client = db.session.query(Client).get(95)
    if not client:
        print("Client 95 not found!")
        return
    
    print(f"Client 95 found: {client.legal_name}")
    print(f"Status: {client.status}")
    print(f"Router ID: {client.router_id}")
    print(f"IP: {client.ip_address}")
    
    router = db.session.query(Router).get(client.router_id)
    if router:
        print(f"Router found: {router.host_address} ({router.status})")
    else:
        print(f"Router {client.router_id} NOT found!")

if __name__ == "__main__":
    check_client()
