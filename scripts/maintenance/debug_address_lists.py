from src.infrastructure.database.db_manager import get_db
from src.infrastructure.mikrotik.adapter import MikroTikAdapter

db = get_db()
r = db.get_router_repository().get_by_id(6) # GUAYANITO
adapter = MikroTikAdapter()
if adapter.connect(r.host_address, r.api_username, r.api_password, r.api_port):
    addr_lists = adapter._api_connection.get_resource('/ip/firewall/address-list')
    all_entries = addr_lists.get()
    print(f"--- Address Lists on {r.alias} ---")
    for e in all_entries:
        print(f"List: {e.get('list')}, IP: {e.get('address')}, Comment: '{e.get('comment')}'")
    adapter.disconnect()
