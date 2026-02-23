
import logging
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from src.infrastructure.database.db_manager import get_db
from src.infrastructure.mikrotik.adapter import MikroTikAdapter
from src.infrastructure.database.models import Router

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("FixDynamicPPPoE")

def fix_dynamic_secrets():
    db = get_db()
    session = db.session
    
    try:
        routers = session.query(Router).all()
        
        logger.info("FIJANDO IPs EN SECRETOS PPPoE DINÁMICOS")
        logger.info("=======================================")
        
        total_fixed = 0
        
        for router in routers:
            logger.info(f"📡 Analizando Router: {router.alias}")
            
            adapter = MikroTikAdapter()
            if not adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
                logger.error(f"  ❌ No conectado.")
                continue
                
            try:
                # 1. Obtener Secrets
                secrets = adapter._api_connection.get_resource('/ppp/secret')
                secret_list = secrets.get()
                
                # 2. Obtener Active
                active = adapter._api_connection.get_resource('/ppp/active').get()
                active_map = {a.get('name'): a.get('address') for a in active}
                
                router_fixed_count = 0
                
                for s in secret_list:
                    name = s.get('name')
                    remote_addr = s.get('remote-address')
                    
                    # Si NO tiene IP remota definida, buscamos su IP actual y la fijamos
                    if not remote_addr:
                        current_ip = active_map.get(name)
                        
                        if current_ip:
                            sid = s.get('.id') or s.get('id')
                            if sid:
                                logger.info(f"  🔧 Fijando IP para {name}: {current_ip}")
                                secrets.set(id=sid, **{'remote-address': current_ip})
                                router_fixed_count += 1
                                total_fixed += 1
                        else:
                            logger.warning(f"  ⚠️  Usuario {name} no tiene IP fija ni sesión activa. No se puede fijar.")
                
                if router_fixed_count > 0:
                    logger.info(f"  ✅ Router {router.alias}: {router_fixed_count} IPs fijadas permanentemente.")
                else:
                    logger.info(f"  Router {router.alias}: Sin cambios necesarios.")
                    
            except Exception as e:
                logger.error(f"Error en router {router.alias}: {e}")
            finally:
                adapter.disconnect()
                
        logger.info("=======================================")
        logger.info(f"TOTAL IPs FIJADAS: {total_fixed}")

    except Exception as e:
        logger.error(f"Error general: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    fix_dynamic_secrets()
