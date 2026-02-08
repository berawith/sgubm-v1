from run import create_app
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.mikrotik.adapter import MikroTikAdapter

app = create_app()
with app.app_context():
    db = get_db()
    
    ip_to_check = "10.10.80.6"
    print(f"\n🔍 Investigando la IP {ip_to_check}...\n")
    
    # 1. Buscar en la Base de Datos
    client_repo = db.get_client_repository()
    db_clients = client_repo.get_all()
    client_in_db = next((c for c in db_clients if c.ip_address == ip_to_check), None)
    
    if client_in_db:
        print(f"🏠 En Base de Datos:")
        print(f"   Nombre: {client_in_db.legal_name}")
        print(f"   Usuario: {client_in_db.username}")
        print(f"   MAC: {client_in_db.mac_address}")
        print(f"   Router ID: {client_in_db.router_id}")
    else:
        print(f"🏠 En Base de Datos: No se encontró ningún cliente con la IP {ip_to_check}")

    # 2. Buscar en MikroTik
    routers = db.get_router_repository().get_all()
    for router in routers:
        adapter = MikroTikAdapter()
        if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
            try:
                secrets = adapter._api_connection.get_resource('/ppp/secret').get()
                found = [s for s in secrets if s.get('remote-address') == ip_to_check]
                if found:
                    print(f"📡 En MikroTik ({router.alias}):")
                    for s in found:
                        print(f"   [SECRET] Name: {s.get('name')} | Profile: {s.get('profile')} | Comment: {s.get('comment')}")
                
                leases = adapter._api_connection.get_resource('/ip/dhcp-server/lease').get(address=ip_to_check)
                for l in leases:
                    print(f"   [LEASE] MAC: {l.get('mac-address')} | Host: {l.get('host-name')} | Status: {l.get('status')}")
            finally:
                adapter.disconnect()
