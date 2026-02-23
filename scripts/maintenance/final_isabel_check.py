from run import create_app
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.mikrotik.adapter import MikroTikAdapter

app = create_app()
with app.app_context():
    db = get_db()
    
    print("\n🔍 EXAMEN DETALLADO DE MIKROTIK (PRINCIPAL)\n")
    
    router = db.get_router_repository().get_by_id(1) # Asumimos PRINCIPAL es ID 1
    adapter = MikroTikAdapter()
    if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
        try:
            secrets = adapter._api_connection.get_resource('/ppp/secret').get()
            
            print("--- TODOS LOS SECRETOS QUE CONTIENEN 'Isabel' ---")
            for s in secrets:
                if 'Isabel' in s.get('name', ''):
                    print(f"Name: {s.get('name')} | IP: {s.get('remote-address')} | Comment: {s.get('comment')}")
            
            print("\n--- TODOS LOS SECRETOS CON IP 10.10.80.6 ---")
            for s in secrets:
                if s.get('remote-address') == '10.10.80.6':
                    print(f"Name: {s.get('name')} | IP: {s.get('remote-address')} | Comment: {s.get('comment')}")
                    
            print("\n--- TODOS LOS SECRETOS CON IP 177.77.72.14 ---")
            for s in secrets:
                if s.get('remote-address') == '177.77.72.14':
                    print(f"Name: {s.get('name')} | IP: {s.get('remote-address')} | Comment: {s.get('comment')}")

        finally:
            adapter.disconnect()
