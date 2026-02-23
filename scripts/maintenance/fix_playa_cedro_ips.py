
import logging
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client, Router
from src.infrastructure.mikrotik.adapter import MikroTikAdapter

# Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ROUTER_HOST = '12.12.12.172'

def fix_ips():
    db = get_db()
    session = db.session
    
    # 1. Get Router
    router = session.query(Router).filter_by(host_address=ROUTER_HOST).first()
    if not router:
        logger.error("Router Playa de Cedro not found in DB")
        return

    # 2. Get All Clients for this Router (to ensure consistency)
    clients = session.query(Client).filter(
        Client.router_id == router.id
    ).all()
    
    if not clients:
        logger.info("No clients with missing IPs found.")
        return

    logger.info(f"Found {len(clients)} clients with missing IPs.")

    # 3. Connect to MikroTik
    adapter = MikroTikAdapter()
    if not adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
        logger.error("Could not connect to MikroTik")
        return

    # 4. Fetch Active Connections
    try:
        active_resource = adapter._api_connection.get_resource('/ppp/active')
        active_list = active_resource.get()
        active_map = {item.get('name'): item.get('address') for item in active_list}
        logger.info(f"Retrieved {len(active_map)} active PPPoE connections.")
        
        # 5. Get Secrets (to update them)
        secrets_resource = adapter._api_connection.get_resource('/ppp/secret')
        
        updated_count = 0
        
        for client in clients:
            ip = active_map.get(client.username)
            if ip:
                logger.info(f"Found active IP for {client.username}: {ip}")
                
                # Update DB
                client.ip_address = ip
                
                # Update MikroTik Secret (Make it static)
                try:
                    secret_item = secrets_resource.get(name=client.username)
                    if secret_item:
                        # Try 'id' first, then '.id'
                        secret_id = secret_item[0].get('id') or secret_item[0].get('.id')
                        if secret_id:
                            secrets_resource.set(id=secret_id, **{'remote-address': ip})
                            logger.info(f"Updated MikroTik secret for {client.username} with static IP {ip}")
                        else:
                            logger.error(f"Could not find ID for secret {client.username}")
                except Exception as e:
                    logger.error(f"Failed to update secret for {client.username}: {e}")
                
                updated_count += 1
            else:
                logger.warning(f"Client {client.username} is not currently connected. Cannot detect IP.")
        
        session.commit()
        logger.info(f"Successfully updated IPs for {updated_count} clients.")
        
    except Exception as e:
        logger.error(f"Error during sync: {e}")
    finally:
        adapter.disconnect()

if __name__ == "__main__":
    fix_ips()
