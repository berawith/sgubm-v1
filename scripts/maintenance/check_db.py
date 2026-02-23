from src.infrastructure.database.db_manager import get_db
import json

def check_status():
    db = get_db()
    router_repo = db.get_router_repository()
    client_repo = db.get_client_repository()
    
    routers = router_repo.get_all()
    clients = client_repo.get_all()
    
    print("--- Routers in DB ---")
    for r in routers:
        print(f"ID: {r.id} | Alias: {r.alias} | Host: {r.host_address} | Status: {r.status} | Last Sync: {r.last_sync}")
        
    print("\n--- Clients Count per Router ---")
    counts = {}
    for c in clients:
        counts[c.router_id] = counts.get(c.router_id, 0) + 1
    
    for rid, count in counts.items():
        print(f"Router ID {rid}: {count} clients")

if __name__ == "__main__":
    check_status()
