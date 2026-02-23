import sys
import os

# Ensure src is in path
sys.path.append(os.getcwd())

from src.infrastructure.database.db_manager import DatabaseManager
from src.infrastructure.database.models import Router, NetworkSegment

def migrate_segments():
    print("Iniciando migración de segmentos a campos del router...")
    try:
        db = DatabaseManager()
        session = db.session
        
        routers = session.query(Router).all()
        
        for router in routers:
            print(f"\nProcesando Router: {router.alias} (ID: {router.id})")
            
            # Obtener segmentos del router
            segments = session.query(NetworkSegment).filter(NetworkSegment.router_id == router.id).all()
            
            if not segments:
                print("  - Sin segmentos asociados en tabla NetworkSegment.")
                continue
            
            # Obtener valores actuales y convertirlos a sets para evitar duplicados
            current_pppoe_raw = router.pppoe_ranges or ""
            current_dhcp_raw = router.dhcp_ranges or ""
            
            # Split y limpiar
            current_pppoe_list = [x.strip() for x in current_pppoe_raw.split(',') if x.strip()]
            current_dhcp_list = [x.strip() for x in current_dhcp_raw.split(',') if x.strip()]
            
            # Sets para chequeo rápido
            current_pppoe_set = set(current_pppoe_list)
            current_dhcp_set = set(current_dhcp_list)
            
            new_pppoe = []
            new_dhcp = []
            
            for seg in segments:
                cidr = seg.cidr.strip()
                name = seg.name.lower()
                
                # Clasificar según nombre (heurística simple)
                is_pppoe = "pppoe" in name
                
                if is_pppoe:
                    if cidr not in current_pppoe_set:
                        new_pppoe.append(cidr)
                        current_pppoe_set.add(cidr)
                        print(f"  + Detectado PPPoE nuevo: {cidr} ({seg.name})")
                    else:
                        print(f"  = PPPoE ya existe: {cidr}")
                else:
                    if cidr not in current_dhcp_set:
                        new_dhcp.append(cidr)
                        current_dhcp_set.add(cidr)
                        print(f"  + Detectado DHCP/Queue nuevo: {cidr} ({seg.name})")
                    else:
                        print(f"  = DHCP ya existe: {cidr}")
            
            # Actualizar campos si hay cambios
            updated = False
            
            if new_pppoe:
                finals = current_pppoe_list + new_pppoe
                router.pppoe_ranges = ", ".join(finals)
                updated = True
                
            if new_dhcp:
                finals = current_dhcp_list + new_dhcp
                router.dhcp_ranges = ", ".join(finals)
                updated = True
            
            if updated:
                session.add(router)
                # session.commit() # Commit per router or all at end? All at end is safer but...
                print(f"  -> Router '{router.alias}' actualizado con nuevos rangos.")
            else:
                print(f"  -> Router '{router.alias}' sin cambios necesarios.")
                
        session.commit()
        print("\nMigración completada exitosamente. Verifique en la web.")
            
    except Exception as e:
        # session.rollback() # Rollback manual
        print(f"Error crítico durante la migración: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    migrate_segments()
