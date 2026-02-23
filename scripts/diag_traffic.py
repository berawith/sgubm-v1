
import sys
import os
import json
import logging

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.infrastructure.mikrotik.adapter import MikroTikAdapter
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Router, Client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def diagnostic():
    db = get_db()
    session = db.session
    
    # 1. Get first online router
    router = session.query(Router).first()
    if not router:
        print("No routers found in DB")
        return

    print(f"Connecting to router: {router.alias} ({router.host_address})")
    adapter = MikroTikAdapter()
    if not adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
        print("Failed to connect to router")
        return

    # 2. Get some clients
    clients = session.query(Client).filter(Client.router_id == router.id).limit(10).all()
    if not clients:
        print("No clients found for this router")
        adapter.disconnect()
        return

    print(f"Checking traffic for {len(clients)} clients...")
    
    # Simulate MonitoringManager logic
    client_ids = [c.id for c in clients]
    
    # A. Check Queues
    print("\n--- Simple Queues ---")
    queue_stats = adapter._api_connection.get_resource('/queue/simple').get()
    print(f"Found {len(queue_stats)} simple queues total")
    
    for client in clients:
        matching_q = None
        for q in queue_stats:
            name = q.get('name', '').lower()
            target = q.get('target', '')
            ip = target.split('/')[0] if '/' in target else target
            
            if name == client.username.lower() or ip == client.ip_address:
                matching_q = q
                break
        
        if matching_q:
            print(f"Client {client.id} - {client.username} ({client.ip_address}): Found Queue '{matching_q.get('name')}', Rate: {matching_q.get('rate')}")
        else:
            print(f"Client {client.id} - {client.username} ({client.ip_address}): No Queue found")

    # B. Check PPPoE
    print("\n--- PPPoE Active Sessions ---")
    active_sessions = adapter.get_active_pppoe_sessions()
    print(f"Found {len(active_sessions)} active PPPoE sessions")
    
    for client in clients:
        if client.username in active_sessions:
            print(f"Client {client.username}: Active PPPoE Session found. Uptime: {active_sessions[client.username].get('uptime')}")
        else:
            # Case insensitive check
            found = False
            for user in active_sessions:
                if user.lower() == client.username.lower():
                    print(f"Client {client.username}: Active PPPoE Session found (Case Mismatch: {user}). Uptime: {active_sessions[user].get('uptime')}")
                    found = True
                    break
            if not found:
                print(f"Client {client.username}: No active PPPoE session")

    # C. Check Interfaces Traffic
    print("\n--- Interface Traffic Monitoring ---")
    all_ifaces = adapter._api_connection.get_resource('/interface').get()
    iface_names_lower = {i.get('name').lower(): i.get('name') for i in all_ifaces if i.get('name')}
    print(f"Found {len(iface_names_lower)} interfaces in total:")
    for n in sorted(iface_names_lower.values()):
        print(f"  - {n}")
    
    patterns_tested = []
    for client in clients:
        user = client.username.lower()
        patterns = [user, f"<{user}>", f"pppoe-{user}", f"<pppoe-{user}>"]
        for p in patterns:
            if p in iface_names_lower:
                real_p = iface_names_lower[p]
                patterns_tested.append(p)
                print(f"Client {user}: Matched interface pattern '{real_p}' (requested as '{p}')")

    if patterns_tested:
        print(f"Monitoring traffic for matched interfaces (using adapter.get_bulk_traffic): {patterns_tested}")
        traffic = adapter.get_bulk_traffic(patterns_tested)
        print("Traffic results:")
        print(json.dumps(traffic, indent=2))
    else:
        print("No interface patterns matched any existing interfaces")

    adapter.disconnect()
    session.close()

if __name__ == "__main__":
    diagnostic()
