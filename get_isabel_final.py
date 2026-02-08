from run import create_app
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.mikrotik.adapter import MikroTikAdapter

app = create_app()
with app.app_context():
    db = get_db()
    repo = db.get_client_repository()
    
    # Buscar en DB
    client = repo.get_filtered(search='IsabelZambrano')
    # Filter strictly for the one we modified if possible, or show all matches
    targets = [c for c in client if c.username == 'IsabelZambrano']
    
    if not targets:
        print("No se encontró el cliente en la base de datos.")
    else:
        for c in targets:
            print(f"Base de Datos - Nombre: {c.legal_name} | Usuario: {c.username} | IP: {c.ip_address} | MAC: {c.mac_address}")
            
            # Chequear Router en tiempo real
            router = db.get_router_repository().get_by_id(c.router_id)
            if router:
                adapter = MikroTikAdapter()
                if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
                    try:
                        # Buscar MAC en ARP
                        arp = adapter.get_arp_table()
                        arp_entry = next((a for a in arp if a.get('address') == c.ip_address), None)
                        if arp_entry:
                            print(f"Router (ARP) - IP: {c.ip_address} | MAC: {arp_entry.get('mac-address')}")
                        
                        # Buscar MAC en Leases
                        leases = adapter.get_dhcp_leases()
                        lease = next((l for l in leases if l.get('address') == c.ip_address), None)
                        if lease:
                            print(f"Router (Lease) - IP: {c.ip_address} | MAC: {lease.get('mac-address')}")
                            
                        # Buscar en PPP Active
                        active = adapter._api_connection.get_resource('/ppp/active').get(name=c.username)
                        if active:
                             print(f"Router (PPP Active) - IP: {active[0].get('address')} | MAC: {active[0].get('caller-id')} (Caller ID)")
                    except Exception as e:
                        print(f"Error consultando router: {e}")
                    finally:
                        adapter.disconnect()
