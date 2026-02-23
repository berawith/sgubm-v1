
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.mikrotik.adapter import MikroTikAdapter
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_client_sync(target_ip):
    db = get_db()
    client_repo = db.get_client_repository()
    router_repo = db.get_router_repository()
    
    # 1. Buscar en BD
    clients = client_repo.get_all()
    client = next((c for c in clients if c.ip_address == target_ip), None)
    
    if not client:
        print(f"❌ Cliente con IP {target_ip} NO encontrado en la base de datos.")
        return
    
    print(f"✅ Cliente encontrado en BD:")
    print(f"   ID: {client.id}")
    print(f"   Username: {client.username}")
    print(f"   Legal Name: {client.legal_name}")
    print(f"   Router ID: {client.router_id}")
    print(f"   Service Type: {client.service_type}")
    
    # 2. Conectar a MikroTik
    router = router_repo.get_by_id(client.router_id)
    if not router:
        print(f"❌ Router ID {client.router_id} no encontrado.")
        return
        
    print(f"🔌 Conectando a Router: {router.alias} ({router.host_address})...")
    adapter = MikroTikAdapter()
    if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
        try:
            # Buscar Simple Queue by IP
            print(f"🔍 Buscando Simple Queue para {target_ip}...")
            queues = adapter._api_connection.get_resource('/queue/simple')
            
            # Buscar por target
            all_queues = queues.get()
            q_by_ip = [q for q in all_queues if target_ip in q.get('target', '')]
            
            if q_by_ip:
                print(f"💡 Encontrada(s) {len(q_by_ip)} queue(s) en MikroTik para esa IP:")
                for q in q_by_ip:
                    print(f"   - Name: {q.get('name')}")
                    print(f"   - Comment: {q.get('comment')}")
                    print(f"   - Target: {q.get('target')}")
            else:
                print(f"❌ No se encontró Simple Queue para la IP {target_ip} en MikroTik.")
                
            # Buscar por username de la BD
            print(f"🔍 Buscando Simple Queue con nombre '{client.username}'...")
            q_by_name = queues.get(name=client.username)
            if q_by_name:
                print(f"✅ Se encontró queue con nombre exacto {client.username}")
            else:
                print(f"❌ NO se encontró queue con nombre '{client.username}'")

        finally:
            adapter.disconnect()
    else:
        print("❌ Error al conectar al router.")

if __name__ == "__main__":
    check_client_sync("177.77.69.4")
