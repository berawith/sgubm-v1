import logging
import sys
import os

# Añadir el directorio raíz al path para importar los módulos correctamente
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from src.infrastructure.database.db_manager import get_db
from src.infrastructure.mikrotik.adapter import MikroTikAdapter
from src.infrastructure.database.models import Client, Router

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def sync_all_mac_addresses():
    db = get_db()
    session = db.session
    
    try:
        routers = session.query(Router).all()
        total_updated = 0
        total_missing = session.query(Client).filter((Client.mac_address == None) | (Client.mac_address == '')).count()
        
        logger.info(f"Iniciando sincronización masiva de MACs. Clientes sin MAC detectados: {total_missing}")
        
        for router in routers:
            logger.info(f"Procesando Router: {router.alias} ({router.host_address})")
            
            # Obtener clientes del router que no tienen MAC
            clients = session.query(Client).filter(
                Client.router_id == router.id,
                ((Client.mac_address == None) | (Client.mac_address == ''))
            ).all()
            
            if not clients:
                logger.info(f"No hay clientes sin MAC para el router {router.alias}")
                continue
                
            adapter = MikroTikAdapter()
            if not adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
                logger.error(f"No se pudo conectar al router {router.alias}")
                continue
            
            try:
                # 1. Obtener datos del Router
                leases = adapter.get_dhcp_leases()
                arp_table = adapter.get_arp_table()
                
                # Crear diccionario de búsqueda IP -> MAC
                ip_to_mac = {}
                for l in leases:
                    if l.get('address') and l.get('mac-address'):
                        ip_to_mac[l.get('address')] = l.get('mac-address')
                
                for a in arp_table:
                    ip = a.get('address')
                    mac = a.get('mac-address')
                    if ip and mac and ip not in ip_to_mac:
                         ip_to_mac[ip] = mac
                
                # Crear diccionario de búsqueda Username -> MAC (vía Leases)
                user_to_mac = {}
                for l in leases:
                    mac = l.get('mac-address')
                    if not mac: continue
                    
                    # Intentar buscar por host-name o comment
                    host = l.get('host-name', '')
                    comment = l.get('comment', '')
                    if host: user_to_mac[host.lower()] = mac
                    if comment: user_to_mac[comment.lower()] = mac

                # 2. Actualizar clientes
                router_updates = 0
                for client in clients:
                    found_mac = None
                    
                    # A. Intentar por IP
                    if client.ip_address and client.ip_address in ip_to_mac:
                        found_mac = ip_to_mac[client.ip_address]
                    
                    # B. Intentar por Username si no se halló por IP
                    if not found_mac and client.username:
                        found_mac = user_to_mac.get(client.username.lower())
                    
                    if found_mac:
                        client.mac_address = found_mac
                        router_updates += 1
                        total_updated += 1
                        logger.info(f"  [+] MAC encontrada para {client.legal_name}: {found_mac}")
                
                if router_updates > 0:
                    session.commit()
                    logger.info(f"  Finalizado {router.alias}: {router_updates} MACs actualizadas.")
                else:
                    logger.info(f"  Finalizado {router.alias}: No se hallaron MACs coincidentes.")
                    
            except Exception as e:
                logger.error(f"Error procesando datos del router {router.alias}: {e}")
                session.rollback()
            finally:
                adapter.disconnect()
                
        logger.info(f"Sincronización finalizada satisfactoriamente.")
        logger.info(f"Total de clientes actualizados: {total_updated}")
        logger.info(f"Clientes restantes sin MAC: {total_missing - total_updated}")
        
    except Exception as e:
        logger.error(f"Error general en el script: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    sync_all_mac_addresses()
