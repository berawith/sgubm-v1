
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client, Router

def count_clients_by_router():
    db = get_db()
    router_repo = db.get_router_repository()
    client_repo = db.get_client_repository()
    
    routers = router_repo.get_all()
    clients = client_repo.get_all()
    
    # Create a mapping of router ID to its alias
    router_map = {r.id: r.alias for r in routers}
    
    # Initialize counts
    counts = {r.id: 0 for r in routers}
    counts[None] = 0 # For clients without router
    
    # Count
    for client in clients:
        if client.status == 'deleted':
            continue
        if client.router_id in counts:
            counts[client.router_id] += 1
        else:
            counts[None] += 1
            
    # Print results
    print("-" * 40)
    print(f"{'Router':<25} | {'Clientes':<10}")
    print("-" * 40)
    
    total = 0
    for r_id, count in counts.items():
        name = router_map.get(r_id, "Desconocido/Sin Router")
        print(f"{name:<25} | {count:<10}")
        total += count
        
    print("-" * 40)
    print(f"{'TOTAL':<25} | {total:<10}")
    print("-" * 40)

if __name__ == "__main__":
    count_clients_by_router()
