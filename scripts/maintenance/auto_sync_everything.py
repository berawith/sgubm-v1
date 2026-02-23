
import logging
import sys
import os
import ipaddress

# Añadir el directorio raíz al path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from src.infrastructure.database.db_manager import get_db
from src.infrastructure.mikrotik.adapter import MikroTikAdapter
from src.infrastructure.database.models import Client, Router

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AutoSync")

def is_valid_ip(ip):
    if not ip or ip == '0.0.0.0' or ip == 'None':
        return False
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

def normalize_mac(mac):
    if not mac: return None
    return mac.upper().strip()

def auto_sync_everything():
    db = get_db()
    session = db.session
    
    try:
        routers = session.query(Router).all()
        total_missing_ip = 0
        total_missing_mac = 0
        total_fixed_ip = 0
        total_fixed_mac = 0
        
        # Contar inicialmente faltantes
        clients_all = session.query(Client).all()
        for c in clients_all:
            if not is_valid_ip(c.ip_address): total_missing_ip += 1
            if not c.mac_address: total_missing_mac += 1
            
        logger.info(f"INICIO: Faltan {total_missing_ip} IPs y {total_missing_mac} MACs.")
        
        for router in routers:
            logger.info(f"📡 Analizando Router: {router.alias} ...")
            
            # Obtener clientes asociados a este router
            clients = session.query(Client).filter(Client.router_id == router.id).all()
            if not clients: continue
            
            adapter = MikroTikAdapter()
            if not adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
                logger.error(f"  ❌ Falló conexión con {router.alias}")
                continue
            
            try:
                # 1. Cargar TODA la data relevante del MikroTik en memoria (Cache)
                logger.info("  Descargando tablas del router...")
                
                # A. PPPoE Active (IP, MAC, Username)
                ppp_active = adapter._api_connection.get_resource('/ppp/active').get()
                active_map = {} # username -> {ip, mac}
                for item in ppp_active:
                    name = item.get('name')
                    if name:
                        active_map[name.lower()] = {
                            'ip': item.get('address'),
                            'mac': item.get('caller-id')
                        }
                
                # B. PPPoE Secrets (Remote Address, Username)
                ppp_secrets = adapter._api_connection.get_resource('/ppp/secret').get()
                secret_map = {} # username -> remote_address
                for item in ppp_secrets:
                    name = item.get('name')
                    if name:
                        secret_map[name.lower()] = item.get('remote-address')
                        
                # C. Simple Queues (Target, Username/Name)
                queues = adapter._api_connection.get_resource('/queue/simple').get()
                queue_map = {} # username -> target
                for item in queues:
                    name = item.get('name')
                    target = item.get('target')
                    if name and target:
                        # Target puede ser "192.168.1.50/32", limpiamos
                        clean_target = target.split('/')[0]
                        queue_map[name.lower()] = clean_target
                        
                # D. DHCP Leases (By IP -> MAC, Username -> MAC)
                dhcp_leases = adapter.get_dhcp_leases()
                lease_ip_map = {} # IP -> MAC
                lease_user_map = {} # Username -> MAC
                for item in dhcp_leases:
                    mac = item.get('mac-address')
                    ip = item.get('address')
                    host = item.get('host-name')
                    comment = item.get('comment')
                    
                    if ip and mac: lease_ip_map[ip] = mac
                    if mac:
                        if host: lease_user_map[host.lower()] = mac
                        if comment: lease_user_map[comment.lower()] = mac
                        
                # E. ARP Table (IP -> MAC)
                arp_table = adapter.get_arp_table()
                arp_map = {}
                for item in arp_table:
                    ip = item.get('address')
                    mac = item.get('mac-address')
                    if ip and mac: arp_map[ip] = mac
                
                logger.info(f"  Datos cargados: {len(ppp_active)} Active, {len(ppp_secrets)} Secrets, {len(queues)} Queues.")

                # 2. Procesar Clientes
                changes_in_router = 0
                for client in clients:
                    updated = False
                    uname = client.username.lower() if client.username else ""
                    
                    # --- FIX IP ADDRESS ---
                    if not is_valid_ip(client.ip_address):
                        new_ip = None
                        source = ""
                        
                        # Estrategia 1: PPPoE Active
                        if uname in active_map and active_map[uname]['ip']:
                            new_ip = active_map[uname]['ip']
                            source = "PPPoE Active"
                        
                        # Estrategia 2: PPPoE Secret
                        if not new_ip and uname in secret_map and secret_map[uname]:
                            new_ip = secret_map[uname]
                            source = "PPPoE Secret"
                            
                        # Estrategia 3: Simple Queue Target
                        if not new_ip:
                            # Probar con username
                            if uname in queue_map:
                                new_ip = queue_map[uname]
                                source = "Queue(User)"
                            # Probar con Legal Name si falla
                            elif client.legal_name and client.legal_name.lower() in queue_map:
                                new_ip = queue_map[client.legal_name.lower()]
                                source = "Queue(Name)"
                                
                        if new_ip:
                            old_val = client.ip_address
                            client.ip_address = new_ip
                            updated = True
                            total_fixed_ip += 1
                            logger.info(f"    [IP FIX] {client.legal_name}: {old_val} -> {new_ip} ({source})")

                    # --- FIX MAC ADDRESS ---
                    if not client.mac_address:
                        new_mac = None
                        source = ""
                        current_ip = client.ip_address # Usar la IP corregida si aplica
                        
                        # Estrategia 1: PPPoE Active (Caller ID) - LA MEJOR
                        if uname in active_map and active_map[uname]['mac']:
                            new_mac = active_map[uname]['mac']
                            source = "PPPoE CallerID"
                            
                        # Estrategia 2: DHCP Leases (por IP)
                        if not new_mac and current_ip in lease_ip_map:
                            new_mac = lease_ip_map[current_ip]
                            source = "DHCP Lease(IP)"
                            
                        # Estrategia 3: ARP Table (por IP)
                        if not new_mac and current_ip in arp_map:
                            new_mac = arp_map[current_ip]
                            source = "ARP(IP)"
                            
                        # Estrategia 4: DHCP Leases (por Username)
                        if not new_mac and uname in lease_user_map:
                            new_mac = lease_user_map[uname]
                            source = "DHCP Lease(User)"
                            
                        if new_mac:
                            client.mac_address = normalize_mac(new_mac)
                            updated = True
                            total_fixed_mac += 1
                            logger.info(f"    [MAC FIX] {client.legal_name}: {new_mac} ({source})")
                            
                    if updated:
                        changes_in_router += 1
                
                if changes_in_router > 0:
                    session.commit()
                    logger.info(f"  ✅ Router {router.alias} procesado: {changes_in_router} clientes actualizados.")
                else:
                    logger.info(f"  Router {router.alias} sin cambios necesarios.")
                    
            except Exception as e:
                logger.error(f"  ❌ Error procesando router {router.alias}: {e}")
                session.rollback()
            finally:
                adapter.disconnect()
                
        logger.info("="*50)
        logger.info(f"RESUMEN FINAL:")
        logger.info(f"IPs Corregidas : {total_fixed_ip}")
        logger.info(f"MACs Corregidas: {total_fixed_mac}")
        logger.info("="*50)

    except Exception as e:
        logger.error(f"Error crítico en script: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    auto_sync_everything()
