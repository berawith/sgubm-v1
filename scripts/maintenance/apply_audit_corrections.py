import os
import sys
import logging
import json
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.getcwd())
try:
    from src.infrastructure.database.models import Client, Router, AuditLog
    from src.infrastructure.mikrotik.adapter import MikroTikAdapter
except ImportError:
    print("Error imports")
    sys.exit(1)

def apply_sync_corrections():
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    print(f"🚀 Iniciando Sincronización Masiva - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    routers = session.query(Router).filter(Router.status == 'online').all()
    
    total_db_fixes = 0
    total_name_syncs = 0
    total_mt_fixes = 0

    for router in routers:
        print(f"\n📡 Procesando Router: {router.alias} ({router.host_address})")
        adapter = MikroTikAdapter()
        
        if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
            try:
                # Obtener datos de MikroTik
                secrets = adapter._api_connection.get_resource('/ppp/secret').get()
                queues = adapter._api_connection.get_resource('/queue/simple').get()
                
                mt_map = {}
                name_map = {} 
                ip_map = {}   
                
                for s in secrets:
                    name = s.get('name')
                    ip = s.get('remote-address')
                    if name:
                        mt_map[name] = {'type': 'pppoe', 'ip': ip, 'disabled': s.get('disabled') == 'true', 'id': s.get('.id')}
                        name_map[name.lower()] = name
                        if ip and ip != '0.0.0.0': ip_map[ip] = name
                for q in queues:
                    name = q.get('name')
                    target = q.get('target', '').split('/')[0]
                    if name and name not in mt_map:
                        mt_map[name] = {'type': 'queue', 'ip': target, 'disabled': q.get('disabled') == 'true', 'id': q.get('.id')}
                        name_map[name.lower()] = name
                        if target and target != '0.0.0.0': ip_map[target] = name

                # Procesar Clientes
                clients = session.query(Client).filter(Client.router_id == router.id).all()
                
                for client in clients:
                    changes = []
                    physical_name = None
                    
                    # Fuzzy match
                    if client.username in mt_map:
                        physical_name = client.username
                    elif client.legal_name and client.legal_name.lower() in name_map:
                        physical_name = name_map[client.legal_name.lower()]
                    elif client.ip_address in ip_map:
                        physical_name = ip_map[client.ip_address]
                    
                    if physical_name:
                        physical = mt_map[physical_name]
                        
                        # 1. Sync Username (SI es distinto)
                        if physical_name != client.username:
                            old_user = client.username
                            client.username = physical_name
                            changes.append(f"Username: {old_user} -> {physical_name}")
                            total_name_syncs += 1
                        
                        # 2. Sync IP
                        r_ip = physical['ip']
                        if r_ip and r_ip != '0.0.0.0' and r_ip != client.ip_address:
                            old_ip = client.ip_address
                            client.ip_address = r_ip
                            changes.append(f"IP: {old_ip} -> {r_ip}")
                            total_db_fixes += 1
                        
                        # 3. Sync MikroTik Status
                        if client.status == 'active' and physical['disabled']:
                            adapter.restore_client_service(client.to_dict())
                            changes.append("Status: MT_Disabled -> MT_Restored")
                            total_mt_fixes += 1
                        elif client.status == 'suspended' and not physical['disabled']:
                            adapter.suspend_client_service(client.to_dict())
                            changes.append("Status: MT_Active -> MT_Suspended")
                            total_mt_fixes += 1

                        if changes:
                            print(f"   ✅ Sincronizado: {client.legal_name} | {', '.join(changes)}")
                            # Log Audit
                            audit = AuditLog(
                                category='system',
                                operation='sync_correction',
                                entity_type='client',
                                entity_id=client.id,
                                username='AntigravityAI',
                                description=f"Corrección automática de sincronización: {', '.join(changes)}",
                                timestamp=datetime.now()
                            )
                            session.add(audit)

            except Exception as e:
                print(f"   ❌ Error en router {router.alias}: {e}")
            finally:
                adapter.disconnect()
        else:
            print(f"   ❌ Falló conexión a {router.alias}")

    session.commit()
    print(f"\n✨ Sincronización Finalizada.")
    print(f"   - IPs Corregidas: {total_db_fixes}")
    print(f"   - Usernames Sincronizados: {total_name_syncs}")
    print(f"   - Estatus MikroTik Corregidos: {total_mt_fixes}")
    session.close()

if __name__ == "__main__":
    apply_sync_corrections()
