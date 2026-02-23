from run import create_app
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.mikrotik.adapter import MikroTikAdapter

app = create_app()
with app.app_context():
    db = get_db()
    
    router = db.get_router_repository().get_by_id(1)
    adapter = MikroTikAdapter()
    if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
        try:
            secrets = adapter._api_connection.get_resource('/ppp/secret').get()
            print("\n--- MIKROTIK PRINCIPAL ---")
            for s in secrets:
                if 'Veracruz' in s.get('comment', '') or 'Veracruz' in s.get('name', ''):
                    print(f"Name: {s.get('name')} | IP: {s.get('remote-address')} | Comment: {s.get('comment')}")
        finally:
            adapter.disconnect()
