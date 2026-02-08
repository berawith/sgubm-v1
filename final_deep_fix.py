
import os
import sys
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Añadir el path del proyecto para importar modelos
sys.path.append(os.getcwd())

try:
    from src.infrastructure.database.models import Client, Router, InternetPlan
    from src.infrastructure.mikrotik.adapter import MikroTikAdapter
except ImportError:
    print("Error: No se pudieron importar los módulos.")
    sys.exit(1)

def deep_audit_and_fix():
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    print("="*100)
    print(f"{'AUDITORÍA INTEGRAL Y CORRECCIÓN DE CLIENTES':^100}")
    print("="*100)

    # 1. Obtener todos los routers online
    routers = session.query(Router).filter(Router.status == 'online').all()
    
    for router in routers:
        print(f"\n📡 PROCESANDO SERVIDOR: {router.alias}...")
        adapter = MikroTikAdapter()
        
        if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
            try:
                # A. Obtener datos reales del router
                secrets = adapter._api_connection.get_resource('/ppp/secret').get()
                queues = adapter._api_connection.get_resource('/queue/simple').get()
                active = adapter.get_active_pppoe_sessions()
                
                # B. Mapear datos del router para búsqueda rápida
                router_data_by_name = {}
                for s in secrets:
                    name = s.get('name')
                    if name:
                        router_data_by_name[name] = {
                            'type': 'pppoe',
                            'ip': s.get('remote-address'),
                            'comment': s.get('comment'),
                            'disabled': s.get('disabled') == 'true'
                        }
                
                for q in queues:
                    name = q.get('name')
                    if name:
                        # Si ya existe por secret, priorizamos o combinamos
                        router_data_by_name[name] = router_data_by_name.get(name, {
                            'type': 'queue',
                            'ip': q.get('target', '').split('/')[0],
                            'comment': q.get('comment'),
                            'disabled': q.get('disabled') == 'true'
                        })

                # C. Revisar clientes de la BD en este router
                clients = session.query(Client).filter(Client.router_id == router.id).all()
                print(f"   Analizando {len(clients)} clientes en base de datos...")

                for client in clients:
                    needs_update = False
                    
                    # 1. Corregir IP si está vacía y el router la tiene
                    if not client.ip_address and client.username in router_data_by_name:
                        r_ip = router_data_by_name[client.username]['ip']
                        if r_ip and r_ip != '0.0.0.0':
                            client.ip_address = r_ip
                            needs_update = True
                            print(f"   ✅ [IP] {client.legal_name[:20]:<20} -> Detectada: {r_ip}")

                    # 2. Corregir IP si está en sesión activa (tiempo real)
                    if client.username in active:
                        act_ip = active[client.username]['ip']
                        if act_ip != client.ip_address:
                            client.ip_address = act_ip
                            needs_update = True
                            print(f"   ✅ [IP-LIVE] {client.legal_name[:20]:<20} -> Sesión Activa: {act_ip}")

                    # 3. Sincronizar Estatus (Si está activo en BD pero bloqueado en MikroTik)
                    if client.status == 'active' and client.username in router_data_by_name:
                        if router_data_by_name[client.username]['disabled']:
                            # Forzar restauración
                            adapter.restore_client_service(client.to_dict())
                            print(f"   ✅ [SERVICE] {client.legal_name[:20]:<20} -> Rehabilitado en Router (Estaba Disabled)")

                    # 4. Limpieza de nombres basura en comentarios del MikroTik
                    # (Esto no afecta la BD pero ayuda al usuario a ver orden en Winbox)
                
                # D. Detectar "Huérfanos" (Están en MikroTik pero no en BD)
                # Esto es proactivo para avisar al usuario
                db_usernames = {c.username for c in clients if c.username}
                orphans = []
                for r_name in router_data_by_name:
                    if r_name not in db_usernames and not r_name.startswith('Sq-'):
                        orphans.append(r_name)
                
                if orphans:
                    print(f"   ⚠️ Encontrados {len(orphans)} usuarios en MikroTik que no están registrados en el Sistema.")

            except Exception as e:
                print(f"   ❌ Error en auditoría de {router.alias}: {e}")
            finally:
                adapter.disconnect()

    # Guardar cambios
    session.commit()
    print("\n" + "="*100)
    print(f"{'PROCESO DE CORRECCIÓN FINALIZADO':^100}")
    print("="*100)
    session.close()

if __name__ == "__main__":
    deep_audit_and_fix()
