
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.mikrotik.adapter import MikroTikAdapter
from src.infrastructure.database.models import Client, Router, NetworkSegment
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

def sync_router_clients(router_id):
    db = get_db()
    router = db.get_router_repository().get_by_id(router_id)
    if not router: return
    
    segments = db.session.query(NetworkSegment).filter(NetworkSegment.router_id == router_id).all()
    allowed_networks = [ip_network(s.cidr, strict=False) for s in segments]
    
    print(f"\n--- Syncing {router.alias} ---")
    adapter = MikroTikAdapter()
    if not adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
        print("❌ Connection failed")
        return

    # Fetch data
    all_sq = adapter.get_all_simple_queues() if router_id != 4 else []
    all_ppp = adapter.get_all_pppoe_secrets()
    all_profiles = adapter.get_ppp_profiles()
    all_pools = adapter.get_ip_pools()
    
    pool_map = {p.get('name'): p.get('ranges') for p in all_pools}
    allowed_profiles = set()
    for p in all_profiles:
        remote = p.get('remote-address')
        if remote and is_ip_allowed(remote, allowed_networks):
            allowed_profiles.add(p.get('name'))
        elif pool_map.get(remote):
            first = pool_map[remote].split(',')[0].split('-')[0]
            if is_ip_allowed(first, allowed_networks):
                allowed_profiles.add(p.get('name'))

    existing_usernames = {c.username.lower() for c in db.get_client_repository().get_all()}
    
    imported = 0
    
    # 1. Simple Queues
    for q in all_sq:
        name = q.get('name', '')
        ip = q.get('ip_address', '')
        if name.lower() not in existing_usernames and is_ip_allowed(ip, allowed_networks):
            total = len(db.get_client_repository().get_all())
            db.get_client_repository().create({
                'router_id': router_id,
                'subscriber_code': f"CLT-{total + 1:04d}",
                'legal_name': name,
                'username': name,
                'ip_address': ip,
                'monthly_fee': 90000.0,
                'plan_name': 'SQ Plan',
                'service_type': 'simple_queue',
                'status': 'active'
            })
            imported += 1

    # 2. PPPoE
    for s in all_ppp:
        name = s.get('name', '')
        if name.lower() not in existing_usernames:
            if is_ip_allowed(s.get('remote_address'), allowed_networks) or s.get('profile') in allowed_profiles:
                total = len(db.get_client_repository().get_all())
                db.get_client_repository().create({
                    'router_id': router_id,
                    'subscriber_code': f"CLT-{total + 1:04d}",
                    'legal_name': name,
                    'username': name,
                    'password': s.get('password', ''),
                    'ip_address': s.get('remote_address', ''),
                    'monthly_fee': 90000.0,
                    'plan_name': s.get('profile', ''),
                    'service_type': 'pppoe',
                    'status': 'active'
                })
                imported += 1
                
    print(f"✨ Imported {imported} new clients for {router.alias}")
    adapter.disconnect()

if __name__ == "__main__":
    for rid in [5]: # Mi Jardín
        sync_router_clients(rid)
    db = get_db()
    db.remove_session()
