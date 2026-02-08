"""
Script simplificado para sincronizar métricas de routers
Ya que hay 293 clientes existentes, solo actualizamos datos de routers
"""
import sys
import time
from datetime import datetime
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.mikrotik.adapter import MikroTikAdapter
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    print("="*80)
    print("🚀 SGUBM-V1 - SINCRONIZANDO ROUTERS")
    print("="*80)
    print()
    
    db = get_db()
    router_repo = db.get_router_repository()
    client_repo = db.get_client_repository()
    
    # Obtener todos los routers
    routers = router_repo.get_all()
    
    if not routers:
        print("❌ No hay routers configurados en la base de datos")
        return
    
    print(f"📡 Encontrados {len(routers)} routers en la base de datos\n")
    
    successful_syncs = 0
    failed_syncs = 0
    
    for i, router in enumerate(routers, 1):
        print(f"\n{'='*80}")
        print(f"Router {i}/{len(routers)}: {router.alias}")
        print(f"IP: {router.host_address}:{router.api_port}")
        print(f"{'='*80}\n")
        
        adapter = MikroTikAdapter()
        
        try:
            # Conectar al router
            print(f"🔌 Conectando...")
            connected = adapter.connect(
                host=router.host_address,
                username=router.api_username,
                password=router.api_password,
                port=router.api_port,
                timeout=10
            )
            
            if not connected:
                print(f"❌ FALLÓ la conexión al router {router.alias}")
                failed_syncs += 1
                continue
            
            print(f"✅ Conectado exit osamente\n")
            
            # Sincronizar información del sistema
            print("📊 Sincronizando información del sistema...")
            system_info = adapter.get_system_info()
            
            if system_info:
                update_data = {
                    'cpu_usage': int(system_info.get('cpu_load', 0)),
                    'memory_usage': system_info.get('memory_usage', 0),
                    'uptime': system_info.get('uptime', 'Unknown'),
                    'last_sync': datetime.now(),
                    'status': 'online'
                }
                router_repo.update(router.id, update_data)
                
                print(f"   ✅ CPU: {update_data['cpu_usage']}%")
                print(f"   ✅ RAM: {update_data['memory_usage']}%")
                print(f"   ✅ Uptime: {update_data['uptime']}")
                print(f"   ✅ Versión: {system_info.get('version', 'N/A')}")
                print()
            
            # Detectar métodos de gestión
            print("🔍 Detectando métodos de gestión...")
            methods = adapter.detect_management_methods()
            print(f"   Métodos detectados: {', '.join(methods) if methods else 'Ninguno'}\n")
            
            # Contar clientes de este router
            clients_count = len(client_repo.get_by_router(router.id))
            print(f"💾 Clientes en BD para este router: {clients_count}\n")
            
            successful_syncs += 1
            
            adapter.disconnect()
            print(f"   🔌 Desconectado\n")
            
        except Exception as e:
            logger.error(f"Error procesando router {router.alias}: {e}")
            print(f"❌ ERROR: {e}\n")
            failed_syncs += 1
            
            if adapter and adapter._api_connection:
                adapter.disconnect()
        
        # Pequeña pausa entre routers
        if i < len(routers):
            time.sleep(1)
    
    # Resumen final
    print("\n" + "="*80)
    print("📊 RESUMEN FINAL")
    print("="*80)
    print(f"✅ Routers sincronizados exitosamente: {successful_syncs}/{len(routers)}")
    print(f"❌ Routers con errores: {failed_syncs}/{len(routers)}")
    
    # Estadísticas finales
    all_clients = client_repo.get_all()
    print(f"\n💾 Base de datos:")
    print(f"   Total de clientes en sistema: {len(all_clients)}")
    
    from collections import defaultdict
    by_router = defaultdict(int)
    for client in all_clients:
        by_router[client.router_id] += 1
    
    print(f"\n   Distribución por router:")
    for router in routers:
        count = by_router.get(router.id, 0)
        icon = "✅" if count > 0 else "⚠️"
        print(f"      {icon} {router.alias}: {count} clientes")
    
    print("\n" + "="*80)
    print("✅ ¡SINCRONIZACIÓN COMPLETADA!")
    print("="*80)
    
    return successful_syncs, len(all_clients)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Proceso interrumpido por el usuario")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
