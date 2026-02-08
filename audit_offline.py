import sys
import os
import argparse
import logging
from datetime import datetime
import json
import ipaddress

# Setup path to import modules
sys.path.append(os.getcwd())

from run import create_app
from src.infrastructure.config.settings import get_config
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.mikrotik.adapter import MikroTikAdapter

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('network_audit.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('NetworkAuditor')

class NetworkAuditor:
    def __init__(self, router):
        self.router = router
        self.adapter = MikroTikAdapter()
        # Conexión perezosa en connect()
        self.connected = False
        
        # Opcional: Cargar rangos desde BD o configuración
        self.network_ranges = ["0.0.0.0/0"] 
    
    def connect(self):
        try:
            # Usar atributos correctos del modelo Router (SQLAlchemy)
            connected = self.adapter.connect(
                host=self.router.host_address,
                username=self.router.api_username,
                password=self.router.api_password,
                port=self.router.api_port or 8728
            )
            if connected:
                self.connected = True
                logger.info(f"Connected to router {self.router.alias} ({self.router.host_address})")
            return connected
        except Exception as e:
            logger.error(f"Failed to connect to {self.router.alias}: {e}")
            return False

    def close(self):
        if self.connected:
            self.adapter.disconnect()

    def audit_offline_clients(self):
        """
        Implementa la logica avanzada de deteccion de offline:
        Offline = (DHCP Waiting) AND (IP not in Active PPP) AND (ARP Failed or No ARP)
        """
        if not self.connected: return []

        logger.info("Starting audit...")
        
        # 1. Obtener Leases Waiting
        try:
            waiting_leases = self.adapter.get_waiting_leases()
            logger.info(f"Found {len(waiting_leases)} waiting DHCP leases")
        except Exception as e:
            logger.error(f"Error fetching waiting leases: {e}")
            waiting_leases = []

        # 2. Obtener PPP Active IPs
        active_ppp_ips = self.adapter.get_ppp_active_ips()
        logger.info(f"Found {len(active_ppp_ips)} active PPP IPs")

        # 3. Obtener ARP Failed IPs
        failed_arp_ips = self.adapter.get_failed_arp_ips()
        logger.info(f"Found {len(failed_arp_ips)} failed ARP IPs")

        # 4. Obtener tabla ARP completa para chequear existencia
        valid_arp_entries = self.adapter.get_arp_table()
        valid_arp_ips = {entry.get('address') for entry in valid_arp_entries if entry.get('address')}

        confirmed_offline = []

        for lease in waiting_leases:
            ip = lease.get('address')
            if not ip: continue

            # Chequeo 1: Es PPP activo?
            if ip in active_ppp_ips:
                continue

            # Chequeo 2: ARP
            if ip in valid_arp_ips:
                continue
            
            # Info extra
            arp_status = 'failed' if ip in failed_arp_ips else 'none'
            
            confirmed_offline.append({
                'id': lease.get('.id'),
                'ip': ip,
                'mac': lease.get('mac-address'),
                'hostname': lease.get('host-name', 'N/A'),
                'server': lease.get('server', ''),
                'arp_status': arp_status,
                'comment': lease.get('comment', '')
            })

        logger.info(f"Confirmed {len(confirmed_offline)} TRULY offline clients after filters")
        return confirmed_offline

def get_active_routers():
    """Fetch active routers from DB using Repository"""
    try:
        db = get_db()
        repo = db.get_router_repository()
        routers = repo.get_all()
        # Filtramos activos si el repositorio devuelve todos
        return [r for r in routers if getattr(r, 'status', 'active') != 'disabled'] 
    except Exception as e:
        logger.error(f"Error fetching routers: {e}")
        return []

def main():
    parser = argparse.ArgumentParser(description='SGUBM Advanced Network Auditor')
    parser.add_argument('--clean', action='store_true', help='Remove confirmed offline leases')
    parser.add_argument('--json', action='store_true', help='Export results to JSON')
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        routers = get_active_routers()
        if not routers:
            logger.warning("No active routers found in database.")
            return

        all_results = {}

        for router in routers:
            alias = getattr(router, 'alias', 'Unknown')
            logger.info(f"--- Auditing Router: {alias} ---")
            
            auditor = NetworkAuditor(router)
            if auditor.connect():
                offline_clients = auditor.audit_offline_clients()
                
                all_results[alias] = offline_clients

                # Reporte en consola
                if offline_clients:
                    print(f"\n[Router: {alias}] - {len(offline_clients)} Offline Clients Found:")
                    print(f"{'IP Address':<16} | {'MAC':<18} | {'Hostname':<20} | {'ARP':<8}")
                    print("-" * 70)
                    for c in offline_clients:
                        print(f"{c['ip']:<16} | {c['mac']:<18} | {c['hostname'][:20]:<20} | {c['arp_status']:<8}")
                    print("-" * 70)
                else:
                    print(f"\n[Router: {alias}] - Cleaner than a whistle! No offline ghosts found.")

                # Cleaning
                if args.clean and offline_clients:
                    print(f"\nCleaning {len(offline_clients)} leases for {alias}...")
                    count = 0
                    for c in offline_clients:
                        if auditor.adapter.remove_dhcp_lease(c['id']):
                            count += 1
                    print(f"Removed {count} leases.")
                
                auditor.close()

        if args.json:
            filename = f"network_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w') as f:
                json.dump(all_results, f, indent=2)
            print(f"\nFull report saved to {filename}")


if __name__ == "__main__":
    main()
