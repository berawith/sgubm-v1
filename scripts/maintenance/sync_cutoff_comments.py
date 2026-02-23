"""
Script de sincronización de comentarios en Address List:
Coloca el nombre del cliente en el comentario de IPS_BLOQUEADAS.
"""
import logging
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.mikrotik.adapter import MikroTikAdapter

# Configuración de logs
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def sync_comments():
    print("="*80)
    print("📝 SINCRONIZACIÓN DE COMENTARIOS (Nombres de Clientes en IPS_BLOQUEADAS)")
    print("="*80)
    print()
    
    db = get_db()
    client_repo = db.get_client_repository()
    router_repo = db.get_router_repository()
    
    # 1. Obtener todos los clientes suspendidos/cortados para mapear IP -> Nombre
    all_clients = client_repo.get_all()
    ip_to_name = {c.ip_address: c.legal_name for c in all_clients if c.ip_address}
    
    routers = router_repo.get_all()
    
    for router in routers:
        print(f"🛠️ Procesando {router.alias} ({router.host_address})...")
        adapter = MikroTikAdapter()
        try:
            connected = adapter.connect(
                host=router.host_address,
                username=router.api_username,
                password=router.api_password,
                port=router.api_port,
                timeout=15
            )
            
            if connected:
                addr_lists = adapter._api_connection.get_resource('/ip/firewall/address-list')
                blocked_entries = addr_lists.get(list='IPS_BLOQUEADAS')
                
                updated_count = 0
                for entry in blocked_entries:
                    ip = entry.get('address')
                    current_comment = entry.get('comment', '')
                    
                    if ip in ip_to_name:
                        target_name = ip_to_name[ip]
                        
                        # Si el comentario es diferente al nombre, lo actualizamos
                        if current_comment != target_name:
                            target_id = entry.get('id') or entry.get('.id')
                            if target_id:
                                addr_lists.set(id=target_id, comment=target_name)
                                updated_count += 1
                                # logger.info(f"     ✅ {ip} -> {target_name}")
                
                print(f"   ✅ {updated_count} comentarios actualizados.")
                adapter.disconnect()
            else:
                print(f"   ❌ ERROR: No se pudo conectar.")
        except Exception as e:
            print(f"   ❌ ERROR CRÍTICO: {e}")
        print("-" * 60)

    print()
    print("🏁 Sincronización de comentarios finalizada.")

if __name__ == '__main__':
    sync_comments()
