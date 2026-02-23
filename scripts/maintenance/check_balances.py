import os
import sys

# Add src to path
sys.path.append(os.getcwd())

from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client

def check_inconsistencies():
    db = get_db()
    
    # Clientes con saldo 0 o menos que NO están activos
    inconsistent_active = db.session.query(Client).filter(
        Client.account_balance <= 0,
        Client.status != 'active'
    ).all()
    
    print(f"--- Clientes con Saldo <= 0 que NO están activos ({len(inconsistent_active)}) ---")
    for c in inconsistent_active:
        print(f"ID: {c.id} | Name: {c.legal_name} | Balance: {c.account_balance} | Status: {c.status}")

    # Clientes con saldo > 0 que están activos
    inconsistent_suspended = db.session.query(Client).filter(
        Client.account_balance > 0,
        Client.status == 'active'
    ).all()
    
    print(f"\n--- Clientes con Saldo > 0 que están ACTIVOS ({len(inconsistent_suspended)}) ---")
    for c in inconsistent_suspended:
        print(f"ID: {c.id} | Name: {c.legal_name} | Balance: {c.account_balance} | Status: {c.status}")

if __name__ == "__main__":
    check_inconsistencies()
