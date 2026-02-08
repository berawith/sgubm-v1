
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.mikrotik.adapter import MikroTikAdapter
import logging

def check_keys(target_ip):
    db = get_db()
    client_repo = db.get_client_repository()
    router_repo = db.get_router_repository()
    
    clients = client_repo.get_all()
    client = next((c for c in clients if c.ip_address == target_ip), None)
    
    if not client: return
    
    router = router_repo.get_by_id(client.router_id)
    adapter = MikroTikAdapter()
    if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
        try:
            queues = adapter._api_connection.get_resource('/queue/simple')
            all_queues = queues.get()
            q_list = [q for q in all_queues if target_ip in q.get('target', '')]
            
            if q_list:
                print(f"DEBUG: Keys in queue dictionary: {list(q_list[0].keys())}")
                print(f"DEBUG: Value of .id: {q_list[0].get('.id')}")
                print(f"DEBUG: Value of id: {q_list[0].get('id')}")
            else:
                print("❌ No queue found for IP.")
        finally:
            adapter.disconnect()

if __name__ == "__main__":
    check_keys("177.77.69.4")
