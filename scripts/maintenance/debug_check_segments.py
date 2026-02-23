import sys
import os
sys.path.append(os.getcwd())
from run import create_app
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Router, NetworkSegment

app = create_app()

with app.app_context():
    db = get_db()
    routers = db.session.query(Router).all()
    
    print("\n--- Verificación de Segmentos de Red en BD ---")
    target_ip = "12.12.12.139"
    found = False
    
    for r in routers:
        if r.host_address == target_ip:
            found = True
            print(f"\n[OK] Router Encontrado: {r.alias} (IP: {r.host_address}, ID: {r.id})")
            segments = db.session.query(NetworkSegment).filter(NetworkSegment.router_id == r.id).all()
            if segments:
                print(f"     Segmentos declarados ({len(segments)}):")
                for s in segments:
                    print(f"     - {s.cidr}")
            else:
                print("     [!] ALERTA: Este router NO tiene segmentos de red configurados en la BD.")
                print("         (El filtrado de red no funcionará como esperas)")
                
                # Opcional: Auto-fix suggestion code here
        else:
            # Print others briefly
             print(f"Router: {r.alias} (IP: {r.host_address}) - {len(r.network_segments) if hasattr(r, 'network_segments') else 'Check manually'} segments")

    if not found:
        print(f"\n[!] ERROR: No se encontró ningún router con la IP {target_ip}")
    
    print("\n----------------------------------------------")
