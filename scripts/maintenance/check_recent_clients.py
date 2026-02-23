
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client
from datetime import datetime

def check_recent_clients():
    db = get_db()
    session = db.session
    # Get clients added today (or recently)
    clients = session.query(Client).order_by(Client.id.desc()).limit(20).all()
    
    print(f"--- 20 Most Recently Added Clients ---")
    for c in clients:
        print(f"ID: {c.id}, Code: {c.subscriber_code}, Name: {c.legal_name}, Status: {c.status}, RouterID: {c.router_id}, Balance: {c.account_balance}")

if __name__ == "__main__":
    check_recent_clients()
