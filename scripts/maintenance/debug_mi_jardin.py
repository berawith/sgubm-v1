
from src.infrastructure.mikrotik.adapter import MikroTikAdapter
import sqlite3
import logging

logging.basicConfig(level=logging.INFO)

def debug_mi_jardin():
    conn = sqlite3.connect('sgubm.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # MI JARDIN (ID 5)
    cursor.execute("SELECT * FROM routers WHERE id = 5")
    router = cursor.fetchone()
    
    if not router:
        print("❌ Router 5 not found")
        return

    adapter = MikroTikAdapter()
    print(f"📡 Connecting to {router['alias']} ({router['host_address']})...")
    
    if adapter.connect(router['host_address'], router['api_username'], router['api_password'], router['api_port']):
        print("✅ Connected!")
        
        print("\n--- PPPoE SECRETS RAW ---")
        secrets = adapter.get_all_pppoe_secrets()
        print(f"Total Secrets: {len(secrets)}")
        
        print("\n--- SIMPLE QUEUES RAW (Primeras 10) ---")
        queues = adapter.get_all_simple_queues()
        print(f"Total Queues: {len(queues)}")
        for q in queues[:10]:
            print(f"Name: {q.get('name')} | IP: {q.get('ip_address')} | Comment: {q.get('comment')}")

        print("\n--- IP ADDRESSES ---")
        try:
            ips = adapter._api_connection.get_resource('/ip/address').get()
            for ip in ips:
                print(f"Address: {ip.get('address')} | Network: {ip.get('network')} | Interface: {ip.get('interface')}")
        except:
            pass

        adapter.disconnect()
    else:
        print("❌ Connection failed")

if __name__ == "__main__":
    debug_mi_jardin()
