
from run import create_app
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.mikrotik.adapter import MikroTikAdapter
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('RetireClients')

# Clientes detectados como offline para ser retirados
targets = {
    "PRINCIPAL": ["12.12.12.73", "12.12.12.98", "177.77.71.44", "177.77.72.43", "177.77.70.51", "177.77.72.31", "177.77.72.21", "177.77.73.56"],
    "GUIMARAL": ["192.168.17.3"],
    "LOS BANCOS": ["77.16.91.254"],
    "MI JARDIN": ["172.16.41.19", "172.16.41.90"]
}

app = create_app()
with app.app_context():
    db = get_db()
    client_repo = db.get_client_repository()
    router_repo = db.get_router_repository()
    
    routers = {r.alias: r for r in router_repo.get_all()}
    
    for router_alias, ips in targets.items():
        if router_alias not in routers:
            logger.warning(f"Router {router_alias} no encontrado en la base de datos.")
            continue
            
        router = routers[router_alias]
        logger.info(f"--- Procesando Retiros en {router_alias} ---")
        
        adapter = MikroTikAdapter()
        if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
            for ip in ips:
                # 1. Buscar en Sistema (DB) y obtener metadatos
                db_clients = client_repo.get_all()
                target_client = next((c for c in db_clients if c.ip_address == ip and c.router_id == router.id), None)
                mac_address = target_client.mac_address if target_client else None
                
                if target_client:
                    client_repo.delete(target_client.id)
                    logger.info(f"  [DB] Cliente {target_client.legal_name} ({ip}) [MAC: {mac_address or 'N/A'}] eliminado del sistema.")
                else:
                    logger.info(f"  [DB] IP {ip} no estaba en el sistema.")

                # 2. Borrar Simple Queue en MikroTik
                try:
                    queues = adapter._api_connection.get_resource('/queue/simple')
                    all_q = queues.get()
                    # Buscar por IP o por Nombre de Usuario si lo tenemos
                    q_found = [q for q in all_q if ip in q.get('target', '')]
                    if not q_found and target_client:
                        q_found = [q for q in all_q if q.get('name') == target_client.username]
                    
                    for q in q_found:
                        qid = q.get('.id') or q.get('id')
                        queues.remove(id=qid)
                        logger.info(f"  [MikroTik] Simple Queue '{q.get('name')}' eliminada.")
                except Exception as e:
                    logger.error(f"  [MikroTik] Error en Queue para {ip}: {e}")

                # 3. PPPoE Secret: No eliminar, marcar como GESTION
                try:
                    secrets = adapter._api_connection.get_resource('/ppp/secret')
                    s_found = []
                    all_secrets = secrets.get()
                    
                    # Prioridad 1: Por Nombre de Usuario
                    if target_client:
                        s_found = [s for s in all_secrets if s.get('name') == target_client.username]
                    
                    # Prioridad 2: Por IP (remote-address)
                    if not s_found:
                        s_found = [s for s in all_secrets if s.get('remote-address') == ip]
                    
                    for s in s_found:
                        sid = s.get('.id') or s.get('id')
                        secrets.set(id=sid, comment="GESTION")
                        logger.info(f"  [MikroTik] PPPoE Secret '{s.get('name')}' marcado como GESTION.")
                except Exception as e:
                    logger.error(f"  [MikroTik] Error marcando Secret para {ip}: {e}")

                # 4. Limpiar Address Lists (Cortados, etc)
                try:
                    addr_lists = adapter._api_connection.get_resource('/ip/firewall/address-list')
                    entries = addr_lists.get(address=ip)
                    if entries:
                        for entry in entries:
                            eid = entry.get('.id') or entry.get('id')
                            addr_lists.remove(id=eid)
                            logger.info(f"  [MikroTik] IP {ip} eliminada de Address List '{entry.get('list')}'")
                except Exception as e:
                    logger.error(f"  [MikroTik] Error limpiando Address List para {ip}: {e}")

                # 5. Marcar DHCP Lease como RETIRADOS (Uso de MAC si existe)
                try:
                    leases = adapter._api_connection.get_resource('/ip/dhcp-server/lease')
                    l_found = []
                    
                    # Prioridad 1: Por MAC (Mucho más fiable para leases)
                    if mac_address:
                        all_l = leases.get()
                        l_found = [l for l in all_l if l.get('mac-address', '').lower() == mac_address.lower()]
                    
                    # Prioridad 2: Por IP
                    if not l_found:
                        l_found = leases.get(address=ip)
                    
                    for l in l_found:
                        lid = l.get('.id') or l.get('id')
                        leases.set(id=lid, comment="RETIRADOS")
                        logger.info(f"  [MikroTik] DHCP Lease para {l.get('address')} ({l.get('mac-address')}) marcado como RETIRADOS.")
                except Exception as e:
                    logger.error(f"  [MikroTik] Error en DHCP Lease para {ip}: {e}")

            adapter.disconnect()
        else:
            logger.error(f"No se pudo conectar a {router_alias}")
