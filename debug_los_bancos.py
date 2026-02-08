
from src.infrastructure.mikrotik.adapter import MikroTikAdapter
import sqlite3
import logging

logging.basicConfig(level=logging.INFO)

def debug_los_bancos():
    conn = sqlite3.connect('sgubm.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get LOS BANCOS (ID 4)
    cursor.execute("SELECT * FROM routers WHERE id = 4")
    router = cursor.fetchone()
    
    if not router:
        print("❌ Router 4 not found in DB")
        return

    adapter = MikroTikAdapter()
    print(f"📡 Connecting to {router['alias']} ({router['host_address']})...")
    
    if adapter.connect(router['host_address'], router['api_username'], router['api_password'], router['api_port']):
        print("✅ Connected!")
        
        print("\n--- PPPoE SECRETS RAW ---")
        secrets = adapter.get_all_pppoe_secrets()
        print(f"Total Secrets: {len(secrets)}")
        
        for s in secrets[:10]: # Check first 10
            print(f"Name: {s.get('name')} | Remote: {s.get('remote_address')} | Local: {s.get('local_address')} | Profile: {s.get('profile')} | Comment: {s.get('comment')}")
            
        print("\n--- IP ADDRESSES ---")
        try:
            ips = adapter._api_connection.get_resource('/ip/address').get()
            for ip in ips:
                print(f"Address: {ip.get('address')} | Network: {ip.get('network')} | Interface: {ip.get('interface')}")
        except:
            pass
            
        print("\n--- IP POOLS ---")
        try:
            pools = adapter._api_connection.get_resource('/ip/pool').get()
            for p in pools:
                print(f"Name: {p.get('name')} | Ranges: {p.get('ranges')}")
        except:
            pass

        print("\n--- PPP PROFILES ---")
        try:
            profiles = adapter._api_connection.get_resource('/ppp/profile').get()
            for p in profiles:
                print(f"Name: {p.get('name')} | Local: {p.get('local-address')} | Remote: {p.get('remote-address')}")
        except:
            pass

        adapter.disconnect()
    else:
        print("❌ Connection failed")

if __name__ == "__main__":
    debug_los_bancos()
