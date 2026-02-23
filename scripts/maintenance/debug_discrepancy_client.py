
from src.infrastructure.database.db_manager import get_db

def find_active_debtor():
    db = get_db()
    repo = db.get_client_repository()
    clients = repo.get_all()
    
    found = False
    for c in clients:
        status = str(c.status).lower()
        balance = c.account_balance or 0
        if status == 'active' and balance > 0:
            print(f"CLIENTE ENCONTRADO:")
            print(f"  Nombre: {c.legal_name}")
            print(f"  ID: {c.id}")
            print(f"  Saldo: {balance}")
            print(f"  IP: {c.ip_address}")
            found = True
            
    if not found:
        print("No se encontró ningún cliente Activo con saldo > 0.")

if __name__ == "__main__":
    find_active_debtor()
