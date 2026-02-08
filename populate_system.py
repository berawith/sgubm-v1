"""
Script para poblar el sistema con datos reales de MikroTik
Sincroniza los 5 routers e importa todos los clientes
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
    print("🚀 SGUBM-V1 - POBLANDO SISTEMA CON DATOS REALES")
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
    
    total_clients_imported = 0
    total_skipped = 0
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
            
            print(f"✅ Conectado exitosamente\n")
            
            # 1. Sincronizar información del sistema
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
                
                print(f"   CPU: {update_data['cpu_usage']}%")
                print(f"   RAM: {update_data['memory_usage']}%")
                print(f"   Uptime: {update_data['uptime']}")
                print()
            
            # 2. Importar clientes
            print("👥 Importando clientes...")
            
            # Obtener métodos de gestión
            methods = adapter.detect_management_methods()
            print(f"   Métodos detectados: {', '.join(methods)}")
            
            clients_before = len(client_repo.get_by_router(router.id))
            
            imported = 0
            skipped = 0
            
            # Importar desde PPPoE si está disponible
            if 'pppoe' in methods:
                print(f"   📡 Importando desde PPPoE...")
                pppoe_secrets = adapter.get_pppoe_secrets()
                
                for secret in pppoe_secrets:
                    username = secret.get('name', '')
                    
                    # Verificar si ya existe
                    existing = client_repo.get_by_username(username)
                    if existing and existing.router_id == router.id:
                        skipped += 1
                        continue
                    
                    # Crear cliente
                    from src.infrastructure.database.models import Client
                    client = Client(
                        router_id=router.id,
                        username=username,
                        password=secret.get('password', ''),
                        ip_address=secret.get('local-address', ''),
                        plan_name=secret.get('profile', 'Default'),
                        service_type='pppoe',
                        status='ACTIVE',
                        legal_name=username.upper(),
                        monthly_fee=50.00  # Default
                    )
                    
                    client_repo.create(client)
                    imported += 1
            
            # Importar desde Simple Queues si está disponible
            if 'simple_queue' in methods:
                print(f"   📊 Importando desde Simple Queues...")
                queues = adapter.get_simple_queues()
                
                for queue in queues:
                    queue_name = queue.get('name', '')
                    target = queue.get('target', '')
                    
                    # Extraer IP del target
                    ip_address = target.split('/')[0] if '/' in target else target
                    
                    # Verificar si ya existe por IP
                    existing = client_repo.get_by_ip(ip_address)
                    if existing and existing.router_id == router.id:
                        skipped += 1
                        continue
                    
                    # Crear cliente
                    from src.infrastructure.database.models import Client
                    client = Client(
                        router_id=router.id,
                        username=queue_name,
                        ip_address=ip_address,
                        plan_name=queue.get('queue', 'Default'),
                        service_type='simple_queue',
                        status='ACTIVE',
                        legal_name=queue_name.upper(),
                        monthly_fee=50.00  # Default
                    )
                    
                    client_repo.create(client)
                    imported += 1
            
            clients_after = len(client_repo.get_by_router(router.id))
            
            print(f"   ✅ Total en BD: {clients_after} clientes")
            print(f"   📥 Importados: {imported} nuevos")
            print(f"   ⏭️  Omitidos: {skipped} existentes")
            
            total_clients_imported += imported
            total_skipped += skipped
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
            time.sleep(2)
    
    # Resumen final
    print("\n" + "="*80)
    print("📊 RESUMEN FINAL")
    print("="*80)
    print(f"✅ Routers sincronizados exitosamente: {successful_syncs}/{len(routers)}")
    print(f"❌ Routers con errores: {failed_syncs}/{len(routers)}")
    print(f"📥 Total clientes importados: {total_clients_imported}")
    print(f"⏭️  Total clientes omitidos (ya existían): {total_skipped}")
    print("="*80)
    
    # Estadísticas finales
    all_clients = client_repo.get_all()
    print(f"\n💾 Base de datos:")
    print(f"   Total de clientes en sistema: {len(all_clients)}")
    
    by_router = {}
    for client in all_clients:
        by_router[client.router_id] = by_router.get(client.router_id, 0) + 1
    
    print(f"   Distribución por router:")
    for router in routers:
        count = by_router.get(router.id, 0)
        print(f"      {router.alias}: {count} clientes")
    
    print("\n✅ ¡PROCESO COMPLETADO!")
    print("="*80)
    
    return successful_syncs, total_clients_imported


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
