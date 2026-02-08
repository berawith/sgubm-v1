from run import create_app
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.mikrotik.adapter import MikroTikAdapter
import logging

# Desactivar logs ruidosos para ver solo el resultado
logging.getLogger('src.infrastructure.mikrotik.adapter').setLevel(logging.ERROR)

app = create_app()
with app.app_context():
    db = get_db()
    routers = db.get_router_repository().get_all()
    
    search_term = "IsabelZambrano"
    search_ip = "177.77.72.14"
    
    print(f"\n🔍 Buscando '{search_term}' y '{search_ip}' en todos los routers...\n")
    
    for router in routers:
        print(f"📡 Router: {router.alias} ({router.host_address})")
        adapter = MikroTikAdapter()
        if not adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
            print(f"  ❌ No se pudo conectar.")
            continue
            
        try:
            # 1. Buscar en PPP Secrets
            secrets = adapter._api_connection.get_resource('/ppp/secret').get()
            s_found = [s for s in secrets if search_term.lower() in s.get('name', '').lower() or search_ip == s.get('remote-address')]
            for s in s_found:
                print(f"  [SECRET] Name: {s.get('name')} | Service: {s.get('service')} | Remote-IP: {s.get('remote-address')} | Profile: {s.get('profile')} | Comment: {s.get('comment')}")
            
            # 2. Buscar en DHCP Leases
            leases = adapter.get_dhcp_leases()
            l_found = [l for l in leases if search_term.lower() in l.get('host-name', '').lower() or search_term.lower() in l.get('comment', '').lower() or search_ip == l.get('address')]
            for l in l_found:
                 print(f"  [LEASE] Address: {l.get('address')} | MAC: {l.get('mac-address')} | Host: {l.get('host-name')} | Status: {l.get('status')} | Comment: {l.get('comment')}")
                 
            # 3. Buscar en Simple Queues
            queues = adapter._api_connection.get_resource('/queue/simple').get()
            q_found = [q for q in queues if search_term.lower() in q.get('name', '').lower() or search_ip in q.get('target', '')]
            for q in q_found:
                print(f"  [QUEUE] Name: {q.get('name')} | Target: {q.get('target')} | Max-Limit: {q.get('max-limit')} | Comment: {q.get('comment')}")

            if not s_found and not l_found and not q_found:
                print("  (-) No se encontraron coincidencias en este router.")

        except Exception as e:
            print(f"  ❌ Error: {e}")
        finally:
            adapter.disconnect()
        print("-" * 30)
