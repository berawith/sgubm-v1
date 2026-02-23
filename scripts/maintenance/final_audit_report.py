
import os
import sys
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.getcwd())
try:
    from src.infrastructure.database.models import Client, Router
    from src.infrastructure.mikrotik.adapter import MikroTikAdapter
except ImportError:
    print("Error imports")
    sys.exit(1)

def audit_and_generate_report():
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    report = []
    report.append("# INFORME DE AUDITORÍA Y CORRECCIÓN INTEGRAL")
    report.append(f"Fecha: 2026-02-06\n")

    routers = session.query(Router).filter(Router.status == 'online').all()
    
    for router in routers:
        report.append(f"## Servidor: {router.alias} ({router.host_address})")
        adapter = MikroTikAdapter()
        
        if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
            try:
                # 1. Obtener datos masivos
                secrets = adapter._api_connection.get_resource('/ppp/secret').get()
                queues = adapter._api_connection.get_resource('/queue/simple').get()
                active = adapter.get_active_pppoe_sessions()
                
                # Mapa de MikroTik
                mt_map = {}
                name_map = {} # Reverse map for fuzzy matching
                ip_map = {}   # Map for IP matching
                
                for s in secrets:
                    name = s.get('name')
                    ip = s.get('remote-address')
                    if name:
                        entry = {'type': 'pppoe', 'ip': ip, 'disabled': s.get('disabled') == 'true', 'id': s.get('.id'), 'original_name': name}
                        mt_map[name] = entry
                        name_map[name.lower()] = name
                        if ip and ip != '0.0.0.0': ip_map[ip] = name
                        
                for q in queues:
                    name = q.get('name')
                    target = q.get('target', '').split('/')[0]
                    if name and name not in mt_map:
                        entry = {'type': 'queue', 'ip': target, 'disabled': q.get('disabled') == 'true', 'id': q.get('.id'), 'original_name': name}
                        mt_map[name] = entry
                        name_map[name.lower()] = name
                        if target and target != '0.0.0.0': ip_map[target] = name

                # 2. Revisar Clientes en BD
                clients = session.query(Client).filter(Client.router_id == router.id).all()
                db_fixes = 0
                mt_fixes = 0
                name_mismatches = 0
                
                report.append(f"- **Clientes analizados en BD:** {len(clients)}")
                
                for client in clients:
                    # Búsqueda robusta
                    physical_name = None
                    
                    # 1. Por Username directo
                    if client.username in mt_map:
                        physical_name = client.username
                    # 2. Por Legal Name (Case Insensitive)
                    elif client.legal_name and client.legal_name.lower() in name_map:
                        physical_name = name_map[client.legal_name.lower()]
                    # 3. Por IP
                    elif client.ip_address in ip_map:
                        physical_name = ip_map[client.ip_address]
                    
                    if physical_name:
                        physical = mt_map[physical_name]
                        
                        # Detectar Mismatch de Username
                        if physical_name != client.username:
                            name_mismatches += 1
                            # Nota: No corregimos username aquí, solo reportamos para el script de corrección
                        
                        # IP Sync
                        r_ip = physical['ip']
                        if r_ip and r_ip != '0.0.0.0' and r_ip != client.ip_address:
                            client.ip_address = r_ip
                            db_fixes += 1
                        
                        # Estatus Sync
                        if client.status == 'active' and physical['disabled']:
                            # adapter.restore_client_service(client.to_dict()) # Omitido en reporte de lectura
                            mt_fixes += 1
                        elif client.status == 'suspended' and not physical['disabled']:
                            # adapter.suspend_client_service(client.to_dict()) # Omitido en reporte de lectura
                            mt_fixes += 1
                    
                    # B. LIVE IP Sync
                    if client.username in active:
                        act_ip = active[client.username]['ip']
                        if act_ip != client.ip_address:
                            client.ip_address = act_ip
                            db_fixes += 1

                report.append(f"- **Correcciones en BD (IPs):** {db_fixes}")
                report.append(f"- **Diferencias de Nombre (DB vs MT):** {name_mismatches}")
                report.append(f"- **Diferencias en Router (Estatus):** {mt_fixes}")

                # 3. Detectar Huérfanos Reales
                db_usernames = {c.username for c in clients if c.username}
                db_legal_names = {c.legal_name.lower() for c in clients if c.legal_name}
                
                orphans = []
                for mt_name in mt_map:
                    if mt_name in db_usernames: continue
                    if mt_name.lower() in db_legal_names: continue
                    if mt_name.startswith('Sq-'): continue
                    
                    # Ignorar técnicos/gestión
                    if any(x in mt_name.lower() for x in ['gestion', 'tecnico', 'management', 'node']): continue
                    
                    orphans.append(mt_name)
                
                if orphans:
                    report.append(f"- **⚠️ Usuarios Huérfanos REALES (Post-Fuzzy Check):** {len(orphans)}")
                    report.append("  > Estos registros no coinciden ni por Username ni por Legal Name.")
                
            except Exception as e:
                report.append(f"- ❌ Error procesando: {e}")
            finally:
                adapter.disconnect()
        else:
            report.append("- ❌ No se pudo conectar.")
        
        report.append("\n" + "-"*40 + "\n")

    session.commit()
    
    with open('AUDITORIA_FINAL_RESUMEN.md', 'w', encoding='utf-8') as f:
        f.write("\n".join(report))
    
    print("Informe generado en AUDITORIA_FINAL_RESUMEN.md")
    session.close()

if __name__ == "__main__":
    audit_and_generate_report()
