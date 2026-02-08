
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
                for s in secrets:
                    name = s.get('name')
                    if name:
                        mt_map[name] = {'type': 'pppoe', 'ip': s.get('remote-address'), 'disabled': s.get('disabled') == 'true', 'id': s.get('.id')}
                for q in queues:
                    name = q.get('name')
                    if name and name not in mt_map:
                        mt_map[name] = {'type': 'queue', 'ip': q.get('target', '').split('/')[0], 'disabled': q.get('disabled') == 'true', 'id': q.get('.id')}

                # 2. Revisar Clientes en BD
                clients = session.query(Client).filter(Client.router_id == router.id).all()
                db_fixes = 0
                mt_fixes = 0
                
                report.append(f"- **Clientes analizados en BD:** {len(clients)}")
                
                for client in clients:
                    # A. Corregir IP si es distinta o nula
                    physical = mt_map.get(client.username)
                    if physical:
                        # IP Sync
                        r_ip = physical['ip']
                        if r_ip and r_ip != '0.0.0.0' and r_ip != client.ip_address:
                            client.ip_address = r_ip
                            db_fixes += 1
                        
                        # Estatus Sync
                        if client.status == 'active' and physical['disabled']:
                            adapter.restore_client_service(client.to_dict())
                            mt_fixes += 1
                        elif client.status == 'suspended' and not physical['disabled']:
                            adapter.suspend_client_service(client.to_dict())
                            mt_fixes += 1
                    
                    # B. LIVE IP Sync
                    if client.username in active:
                        act_ip = active[client.username]['ip']
                        if act_ip != client.ip_address:
                            client.ip_address = act_ip
                            db_fixes += 1

                report.append(f"- **Correcciones en BD (IPs):** {db_fixes}")
                report.append(f"- **Correcciones en Router (Estatus):** {mt_fixes}")

                # 3. Detectar Huérfanos
                db_usernames = {c.username for c in clients if c.username}
                orphans = [name for name in mt_map if name not in db_usernames and not name.startswith('Sq-')]
                
                if orphans:
                    report.append(f"- **⚠️ Usuarios Huérfanos (En Router, NO en BD):** {len(orphans)}")
                    report.append("  > Estos registros existen físicamente en Winbox pero no tienen ficha en el sistema.")
                
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
