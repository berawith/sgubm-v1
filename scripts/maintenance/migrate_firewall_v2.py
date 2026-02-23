"""
Script de migración Firewall v2: CORTADOS-SGUB -> IPS_BLOQUEADAS
Realiza la transición limpia de reglas y listas de direcciones.
"""
import sys
import logging
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.mikrotik.adapter import MikroTikAdapter

# Configurar logging básico para ver progreso en consola
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def migrate_routers():
    print("="*80)
    print("🚀 MIGRACIÓN DE SISTEMA DE CORTE: CORTADOS-SGUB -> IPS_BLOQUEADAS")
    print("="*80)
    print()
    
    db = get_db()
    router_repo = db.get_router_repository()
    routers = router_repo.get_all()
    
    if not routers:
        print("⚠️ No hay routers en la base de datos.")
        return

    print(f"📡 Procesando {len(routers)} routers...")
    print()
    
    for router in routers:
        print(f"🛠️ Migrando {router.alias} ({router.host_address})...")
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
                # 1. Asegurar reglas nuevas (IPS_BLOQUEADAS)
                adapter.ensure_cutoff_firewall_rules()
                
                # 2. Migrar IPs de la lista vieja a la nueva
                logger.info(f"   - Migrando Address List...")
                addr_lists = adapter._api_connection.get_resource('/ip/firewall/address-list')
                old_list = addr_lists.get(list='CORTADOS-SGUB')
                
                if old_list:
                    for entry in old_list:
                        ip = entry.get('address')
                        # Verificar si ya existe en la nueva para no duplicar
                        existing = addr_lists.get(list='IPS_BLOQUEADAS', address=ip)
                        if not existing:
                            addr_lists.add(list='IPS_BLOQUEADAS', address=ip)
                            logger.info(f"     + IP {ip} migrada a IPS_BLOQUEADAS")
                        
                        # Eliminar de la vieja
                        target_id = entry.get('id') or entry.get('.id')
                        if target_id:
                            addr_lists.remove(id=target_id)
                    print(f"   ✅ Address List migrada ({len(old_list)} entradas).")
                else:
                    print(f"   ℹ️ No se encontraron entradas en CORTADOS-SGUB.")

                # 3. Eliminar reglas de firewall antiguas
                logger.info(f"   - Limpiando reglas legacy...")
                filter_rules = adapter._api_connection.get_resource('/ip/firewall/filter')
                all_filters = filter_rules.get()
                
                removed_count = 0
                legacy_comments = ['SGUB-ALLOW-DNS', 'SGUB-DROP-CORTADOS']
                
                for r in all_filters:
                    comment = r.get('comment')
                    src_list = r.get('src-address-list') or r.get('src_address_list', '')
                    
                    # Eliminar por comentario legacy o si usa la lista vieja
                    should_remove = False
                    if comment in legacy_comments:
                        should_remove = True
                    elif src_list == 'CORTADOS-SGUB':
                        should_remove = True
                    
                    if should_remove:
                        target_id = r.get('id') or r.get('.id')
                        if target_id:
                            filter_rules.remove(id=target_id)
                            removed_count += 1
                
                if removed_count > 0:
                    print(f"   ✅ {removed_count} reglas antiguas eliminadas.")
                else:
                    print(f"   ℹ️ No se detectaron reglas antiguas.")

                adapter.disconnect()
            else:
                print(f"   ❌ ERROR: No se pudo conectar al router.")
        except Exception as e:
            print(f"   ❌ ERROR CRÍTICO: {e}")
        print("-" * 60)

    print()
    print("🏁 Migración y limpieza completada.")

if __name__ == '__main__':
    migrate_routers()
