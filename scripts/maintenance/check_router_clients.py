from src.infrastructure.database.db_manager import DatabaseManager
from src.infrastructure.database.models import Client, Router
import os

def check_clients():
    db = DatabaseManager()
    session = db.session
    
    routers = session.query(Router).all()
    print("=== ROUTERS ===")
    for r in routers:
        count = session.query(Client).filter_by(router_id=r.id).count()
        print(f"ID: {r.id}, Alias: {r.alias}, Clients: {count}")
    
    # Check specifically for MI JARDIN (assuming alias)
    mi_jardin = session.query(Router).filter(Router.alias.like('%JARDIN%')).first()
    if mi_jardin:
        print(f"\nFound MI JARDIN ID: {mi_jardin.id}")
        clients = session.query(Client).filter_by(router_id=mi_jardin.id).limit(5).all()
        for c in clients:
            print(f" - Client: {c.legal_name}, Status: {c.status}, Balance: {c.account_balance}")

if __name__ == "__main__":
    check_clients()
