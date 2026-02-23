
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.mikrotik.adapter import MikroTikAdapter
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_client_sync(target_ip):
    db = get_db()
    client_repo = db.get_client_repository()
    router_repo = db.get_router_repository()
    
    # 1. Buscar en BD
    clients = client_repo.get_all()
    client = next((c for c in clients if c.ip_address == target_ip), None)
    
    if not client:
        print(f"❌ Cliente con IP {target_ip} NO encontrado en la base de datos.")
        return
    
    # 2. Conectar a MikroTik
    router = router_repo.get_by_id(client.router_id)
    if not router:
        print(f"❌ Router ID {client.router_id} no encontrado.")
        return
        
    print(f"🔌 Conectando a Router: {router.alias} ({router.host_address})...")
    adapter = MikroTikAdapter()
    if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
        try:
            print(f"🚀 Ejecutando sincronización forzada para {client.legal_name}...")
            # Usamos el username actual de la BD como 'current' para que el adapter lo intente buscar, 
            # pero el adapter ahora tiene el fallback por IP si falla.
            success = adapter.update_client_service(client.username, client.to_dict())
            
            if success:
                print("✅ Sincronización exitosa.")
                
                # Verificar resultado
                print("👀 Verificando estado final en MikroTik...")
                queues = adapter._api_connection.get_resource('/queue/simple')
                all_queues = queues.get()
                clean_ip = target_ip.split('/')[0]
                q_list = [q for q in all_queues if clean_ip in q.get('target', '')]
                
                if q_list:
                    print(f"   - Name en MikroTik: {q_list[0].get('name')}")
                    print(f"   - Comment en MikroTik: {q_list[0].get('comment')}")
                else:
                    print("❌ No se encontró la queue tras el update.")
            else:
                print("❌ La sincronización falló.")

        finally:
            adapter.disconnect()
    else:
        print("❌ Error al conectar al router.")

if __name__ == "__main__":
    fix_client_sync("177.77.69.4")
