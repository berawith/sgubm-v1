
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.mikrotik.adapter import MikroTikAdapter
from src.infrastructure.database.models import Client, Router
from ipaddress import ip_network, ip_address
import logging

logging.basicConfig(level=logging.INFO)

def is_ip_allowed(ip_str, allowed_networks):
    if not ip_str: return False
    clean_ip = ip_str.split('/')[0]
    if not clean_ip or clean_ip == '0.0.0.0': return False
    try:
        addr = ip_address(clean_ip)
        return any(addr in net for net in allowed_networks)
    except: return False

def import_los_bancos():
    db = get_db()
    router_repo = db.get_router_repository()
    client_repo = db.get_client_repository()
    
    router_id = 4
    router = router_repo.get_by_id(router_id)
    if not router:
        print("❌ Router 4 not found")
        return

    # Get allowed segments
    cursor = db.session.connection().connection.cursor() # Get raw sqlite connection if possible, or just use repo
    db_session = db.session
    from src.infrastructure.database.models import NetworkSegment
    segments = db_session.query(NetworkSegment).filter(NetworkSegment.router_id == router_id).all()
    allowed_networks = [ip_network(s.cidr, strict=False) for s in segments]
    
    print(f"📡 Router: {router.alias}")
    print(f"📜 Segments: {[s.cidr for s in segments]}")

    adapter = MikroTikAdapter()
    if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
        print("✅ Connected!")
        
        all_pppoe_secrets = adapter.get_all_pppoe_secrets()
        all_profiles = adapter.get_ppp_profiles()
        all_pools = adapter.get_ip_pools()
        
        pool_map = {p.get('name'): p.get('ranges') for p in all_pools}
        allowed_profiles = set()
        
        for p in all_profiles:
            p_name = p.get('name')
            remote = p.get('remote-address')
            if remote and is_ip_allowed(remote, allowed_networks):
                allowed_profiles.add(p_name)
                continue
            pool_range = pool_map.get(remote)
            if pool_range:
                first_part = pool_range.split(',')[0]
                first_ip = first_part.split('-')[0]
                if is_ip_allowed(first_ip, allowed_networks):
                    allowed_profiles.add(p_name)

        print(f"✅ Allowed Profiles: {allowed_profiles}")
        
        # Get existing clients to avoid duplicates
        existing_usernames = {c.username.lower() for c in client_repo.get_all()}
        
        imported_count = 0
        for s in all_pppoe_secrets:
            name = s.get('name', '')
            profile = s.get('profile', '')
            remote_ip = s.get('remote_address', '')
            
            if name.lower() in existing_usernames:
                continue
                
            if is_ip_allowed(remote_ip, allowed_networks) or profile in allowed_profiles:
                # Create Client
                total = len(client_repo.get_all())
                client_data = {
                    'router_id': router_id,
                    'subscriber_code': f"CLT-{total + 1:04d}",
                    'legal_name': name,
                    'username': name,
                    'password': s.get('password', ''),
                    'ip_address': remote_ip,
                    'monthly_fee': 90000.0,
                    'plan_name': profile,
                    'download_speed': s.get('download_speed', ''),
                    'upload_speed': s.get('upload_speed', ''),
                    'service_type': 'pppoe',
                    'status': 'active' if not s.get('disabled') else 'suspended',
                    'mikrotik_id': s.get('mikrotik_id', '')
                }
                client_repo.create(client_data)
                print(f"✨ Imported: {name}")
                imported_count += 1
                
        print(f"\n🚀 Done! {imported_count} clients imported for Los Bancos.")
        adapter.disconnect()
        db.remove_session()
    else:
        print("❌ Connection failed")

if __name__ == "__main__":
    import_los_bancos()
