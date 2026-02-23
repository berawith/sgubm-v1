from src.infrastructure.mikrotik.adapter import MikroTikAdapter
from src.infrastructure.database.models import Router
from src.infrastructure.database.db_manager import get_db
from run import create_app

def scan_ranges():
    app = create_app()
    with app.app_context():
        db = get_db()
        router = db.session.query(Router).filter(Router.alias.like('%GUIMARAL%')).first()
        
        if not router:
            print("Router GUIMARAL not found in DB")
            return

        print(f"Connecting to {router.alias} ({router.host_address})...")
        adapter = MikroTikAdapter()
        if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
            # 1. Get Addresses imply networks
            try:
                addresses = adapter._api_connection.get_resource('/ip/address').get()
                print("\nIP Networks configured on Router:")
                for addr in addresses:
                    ip_net = addr.get('address')
                    network = addr.get('network')
                    interface = addr.get('interface')
                    disabled = addr.get('disabled') == 'true'
                    if not disabled:
                        print(f" - {ip_net} (Network: {network}) on {interface}")
            except Exception as e:
                print(f"Error getting addresses: {e}")
            
            # 2. Get IP Pools
            try:
                print("\nIP Pools:")
                pools = adapter._api_connection.get_resource('/ip/pool').get()
                for pool in pools:
                    print(f" - {pool.get('name')}: {pool.get('ranges')}")
            except Exception as e:
                print(f"Error getting pools: {e}")
                
            adapter.disconnect()
        else:
            print("Failed to connect to MikroTik")

if __name__ == "__main__":
    scan_ranges()
