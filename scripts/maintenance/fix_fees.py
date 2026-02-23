from datetime import datetime
from datetime import datetime
from src.infrastructure.database.db_manager import get_db

def fix_fees():
    print("Iniciando actualización de tarifas...")
    db = get_db()
    router_repo = db.get_router_repository()
    client_repo = db.get_client_repository()
    
    # 1. Encontrar router Puerto Vivas
    routers = router_repo.get_all()
    target_router = None
    for r in routers:
        if 'PUERTO-VIVAS' in r.alias.upper():
            target_router = r
            break
            
    if not target_router:
        print("No se encontró el router de Puerto Vivas")
        return

    print(f"Router encontrado: {target_router.alias} (ID {target_router.id})")
    
    # 2. Obtener clientes de ese router
    clients = client_repo.get_by_router(target_router.id)
    print(f"Encontrados {len(clients)} clientes.")
    
    # 3. Actualizar tarifa
    count = 0
    for client in clients:
        # ClientRepo usa la session interna del manager
        client_repo.update(client.id, {'monthly_fee': 70000.0})
        count += 1
            
    print(f"¡Actualizados {count} clientes a $70,000!")

if __name__ == "__main__":
    try:
        fix_fees()
    except Exception as e:
        print(f"Error: {e}")
