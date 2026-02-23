
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client

def check_clients_r2():
    db = get_db()
    session = db.session
    # Router 2 is PUERTO VIVAS
    clients = session.query(Client).filter(Client.router_id == 2).all()
    
    print(f"--- Clients in Router 2 (PUERTO VIVAS) ---")
    total_debt = 0
    for c in clients:
        print(f"ID: {c.id}, Code: {c.subscriber_code}, Name: {c.legal_name}, Status: {c.status}, Balance: {c.account_balance}")
        if c.status != 'deleted' and (c.account_balance or 0) > 0:
            total_debt += c.account_balance
            
    print(f"\nCalculated Total Debt: {total_debt}")
    print(f"Total Clients found: {len(clients)}")

if __name__ == "__main__":
    check_clients_r2()
