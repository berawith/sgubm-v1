"""
Script de Sincronización Global de Comentarios:
Pone el nombre del cliente en CUALQUIER Address List donde aparezca su IP.
"""
import logging
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.mikrotik.adapter import MikroTikAdapter

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def global_sync_comments():
    print("="*80)
    print("📝 SINCRONIZACIÓN GLOBAL DE COMENTARIOS EN TODAS LAS LISTAS")
    print("="*80)
    print()
    
    db = get_db()
    client_repo = db.get_client_repository()
    router_repo = db.get_router_repository()
    
    # Mapeo IP -> Nombre
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
                all_entries = addr_lists.get()
                
                updated_count = 0
                for entry in all_entries:
                    ip = entry.get('address')
                    current_comment = entry.get('comment', '').strip()
                    list_name = entry.get('list', '')
                    
                    if ip in ip_to_name:
                        target_name = ip_to_name[ip]
                        
                        # Si el comentario actual no es el nombre, lo actualizamos
                        if current_comment != target_name:
                            target_id = entry.get('id') or entry.get('.id')
                            if target_id:
                                addr_lists.set(id=target_id, comment=target_name)
                                updated_count += 1
                                # logger.info(f"     ✅ [{list_name}] {ip} -> {target_name}")
                
                print(f"   ✅ {updated_count} comentarios actualizados en total.")
                adapter.disconnect()
            else:
                print(f"   ❌ ERROR: No se pudo conectar.")
        except Exception as e:
            print(f"   ❌ ERROR CRÍTICO: {e}")
        print("-" * 60)

    print()
    print("🏁 Sincronización global terminada.")

if __name__ == '__main__':
    global_sync_comments()
