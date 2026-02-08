import os
import sys
from dotenv import load_dotenv
sys.path.append(os.getcwd())
load_dotenv()

from src.infrastructure.database.db_manager import get_db, DatabaseManager
from src.infrastructure.mikrotik.adapter import MikroTikAdapter

def inspect():
    db = get_db()
    
    # Get a router
    router = db.get_router_repository().get_all()[0]
    print(f"Connecting to router: {router.host_address}")

    adapter = MikroTikAdapter()
    if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
        print("Connected!")
        
        # DHCP Leases
        print("\n--- DHCP LEASES (Sample) ---")
        leases = adapter._api_connection.get_resource('/ip/dhcp-server/lease').get()
        if leases:
            print(f"Keys available: {list(leases[0].keys())}")
            # Print sample with last-seen
            for l in leases[:5]:
                print(f"IP: {l.get('address')}, Last Seen: {l.get('last-seen')}, Status: {l.get('status')}")
        else:
            print("No leases found.")

        # PPP Secrets
        print("\n--- PPP SECRETS (Sample) ---")
        secrets = adapter._api_connection.get_resource('/ppp/secret').get()
        if secrets:
            print(f"Keys available: {list(secrets[0].keys())}")
            for s in secrets[:5]:
                print(f"User: {s.get('name')}, Last Logged Out? {s.get('last-logged-out')} (Check keys)")
        else:
            print("No secrets found.")

        adapter.disconnect()
    else:
        print("Failed to connect.")

if __name__ == "__main__":
    inspect()
