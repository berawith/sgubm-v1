
import sys
import os
import logging
from run import create_app
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.mikrotik.adapter import MikroTikAdapter

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger('VerifyRetirement')

targets = {
    "PRINCIPAL": ["12.12.12.73", "12.12.12.98", "177.77.71.44", "177.77.72.43", "177.77.70.51", "177.77.72.31", "177.77.72.21", "177.77.73.56"],
    "MI JARDIN": ["172.16.41.19", "172.16.41.90"],
    "GUIMARAL": ["192.168.17.3"],
    "LOS BANCOS": ["77.16.91.254"]
}

app = create_app()
with app.app_context():
    db = get_db()
    router_repo = db.get_router_repository()
    routers = {r.alias: r for r in router_repo.get_all()}
    
    print("\n" + "="*60)
    print(" VERIFICACIÓN DE ESTADO POST-RETIRO (Winbox Style)")
    print("="*60)

    for alias, ips in targets.items():
        if alias not in routers: continue
        r = routers[alias]
        
        adapter = MikroTikAdapter()
        if adapter.connect(r.host_address, r.api_username, r.api_password, r.api_port):
            print(f"\n📡 ROUTER: {alias} ({r.host_address})")
            print("-" * 50)
            
            # Verificar Secrets
            secrets_res = adapter._api_connection.get_resource('/ppp/secret')
            all_secrets = secrets_res.get()
            
            # Verificar Leases
            leases_res = adapter._api_connection.get_resource('/ip/dhcp-server/lease')
            all_leases = leases_res.get()
            
            # Verificar Queues
            queues_res = adapter._api_connection.get_resource('/queue/simple')
            all_queues = queues_res.get()
            
            for ip in ips:
                # Secret Status
                s = next((s for s in all_secrets if s.get('remote-address') == ip), None)
                s_status = f"✅ [{s.get('comment')}]" if s and s.get('comment') == "GESTION" else "❌ No encontrado/Sin label"
                
                # Lease Status
                l = next((l for l in all_leases if l.get('address') == ip), None)
                l_status = f"✅ [{l.get('comment')}]" if l and l.get('comment') == "RETIRADOS" else "❌ No encontrado/Sin label"
                
                # Queue Status (Debe ser borrada)
                q = next((q for q in all_queues if ip in q.get('target', '')), None)
                q_status = "✅ Borrada" if not q else f"⚠️ SIGE ACTIVA ({q.get('name')})"
                
                print(f"IP: {ip.ljust(15)} | Secret: {s_status.ljust(12)} | Lease: {l_status.ljust(12)} | Queue: {q_status}")
            
            adapter.disconnect()
        else:
            print(f"❌ No se pudo conectar a {alias}")
