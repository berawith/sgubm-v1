
import logging
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from src.infrastructure.database.db_manager import get_db
from src.infrastructure.mikrotik.adapter import MikroTikAdapter
from src.infrastructure.database.models import Router

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("DynamicPPIAudit")

def audit_dynamic_secrets():
    db = get_db()
    session = db.session
    
    try:
        routers = session.query(Router).all()
        
        logger.info("AUDITORIA DE SECRETOS PPPoE DINÁMICOS")
        logger.info("=====================================")
        
        total_dynamic = 0
        
        for router in routers:
            logger.info(f"📡 Revisando Router: {router.alias}")
            
            adapter = MikroTikAdapter()
            if not adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
                logger.error(f"  ❌ No conectado.")
                continue
                
            try:
                # 1. Obtener Secrets
                secrets = adapter._api_connection.get_resource('/ppp/secret').get()
                
                # 2. Obtener Active (para ver qué IP tienen actualmente)
                active = adapter._api_connection.get_resource('/ppp/active').get()
                active_map = {a.get('name'): a.get('address') for a in active}
                
                router_dynamic_count = 0
                
                for s in secrets:
                    name = s.get('name')
                    remote_addr = s.get('remote-address')
                    
                    # Si NO tiene IP remota definida, es dinámico
                    if not remote_addr:
                        router_dynamic_count += 1
                        total_dynamic += 1
                        
                        current_ip = active_map.get(name, "Desconectado")
                        print(f"  ⚠️  [DINÁMICO] Usuario: {name:<20} | IP Actual: {current_ip}")
                
                if router_dynamic_count == 0:
                    logger.info("  ✅ Todos los secretos tienen IP estática asignada.")
                else:
                    logger.warning(f"  🚨 Se encontraron {router_dynamic_count} secretos dinámicos.")
                    
            except Exception as e:
                logger.error(f"Error en router {router.alias}: {e}")
            finally:
                adapter.disconnect()
                
        logger.info("=====================================")
        logger.info(f"TOTAL SECRETOS DINÁMICOS: {total_dynamic}")

    except Exception as e:
        logger.error(f"Error general: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    audit_dynamic_secrets()
