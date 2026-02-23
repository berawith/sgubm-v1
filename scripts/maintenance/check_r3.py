
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client

def check_r3():
    db = get_db()
    session = db.session
    clients = session.query(Client).filter(Client.router_id == 3).all()
    
    total_debt = 0
    suspended_count = 0
    for c in clients:
        if c.status != 'deleted' and (c.account_balance or 0) > 0:
            total_debt += c.account_balance
        if c.status == 'suspended':
            suspended_count += 1
            
    print(f"Router 3 (GUIMARAL): Total Clients: {len(clients)}, Suspended: {suspended_count}, Total Debt: {total_debt}")

if __name__ == "__main__":
    check_r3()
