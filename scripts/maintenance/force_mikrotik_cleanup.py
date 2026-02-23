
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
    from src.infrastructure.database.models import Client, Router
    from src.infrastructure.mikrotik.adapter import MikroTikAdapter
except ImportError:
    print("Error: No se pudieron importar los módulos. Ejecuta desde la raíz del proyecto.")
    sys.exit(1)

def force_fix_address_lists():
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    # 1. Obtener todos los clientes que DEBERÍAN estar activos
    # (Status 'active' en BD)
    active_clients = session.query(Client).filter(Client.status == 'active').all()
    logger.info(f"Revisando {len(active_clients)} clientes activos en BD para limpieza de MikroTik...")

    # 2. Agrupar por router para eficiencia
    router_map = {}
    for c in active_clients:
        if c.router_id:
            if c.router_id not in router_map:
                router_map[c.router_id] = []
            router_map[c.router_id].append(c)

    for router_id, clients in router_map.items():
        router = session.query(Router).get(router_id)
        if not router or router.status != 'online':
            logger.warning(f"Router {router_id} offline o no encontrado. Saltando.")
            continue

        logger.info(f"--- Conectando a Router: {router.alias} ({router.host_address}) ---")
        adapter = MikroTikAdapter()
        if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
            try:
                # Obtener la lista de bloqueados actual del router
                addr_lists = adapter._api_connection.get_resource('/ip/firewall/address-list')
                all_blocked = addr_lists.get(list='IPS_BLOQUEADAS')
                
                if not all_blocked:
                    logger.info(f"   ✅ No hay nadie bloqueado en {router.alias}.")
                    adapter.disconnect()
                    continue

                # Mapa de IPs bloqueadas en el router para búsqueda rápida
                # IP -> Entry ID
                blocked_ips = {}
                for entry in all_blocked:
                    # Guardamos la IP limpia (sin máscara)
                    clean_ip = entry.get('address', '').split('/')[0]
                    entry_id = entry.get('.id') or entry.get('id')
                    blocked_ips[clean_ip] = entry_id

                fixed_count = 0
                for client in clients:
                    if not client.ip_address: continue
                    
                    client_ip = client.ip_address.split('/')[0]
                    if client_ip in blocked_ips:
                        # ¡ERROR ENCONTRADO! El cliente está activo en BD pero bloqueado en Router
                        logger.warning(f"   ⚠️ Reparando: {client.legal_name} ({client_ip}) estaba en IPS_BLOQUEADAS")
                        eid = blocked_ips[client_ip]
                        addr_lists.remove(id=eid)
                        fixed_count += 1
                
                logger.info(f"   ✅ Finalizado: {fixed_count} clientes restaurados en {router.alias}.")
                
            except Exception as e:
                logger.error(f"   ❌ Error procesando router {router.alias}: {e}")
            finally:
                adapter.disconnect()

    session.close()

if __name__ == "__main__":
    force_fix_address_lists()
