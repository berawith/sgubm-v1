import os
import sys
import re
import logging
from datetime import datetime

# Añadir el directorio raíz al path para poder importar src
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client, Router
from src.infrastructure.mikrotik.adapter import MikroTikAdapter

# Configurar logging sin emojis para evitar problemas de encoding
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('reactivation.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

def reactivate_clients():
    filename = "clientes_que_estaban_cortados.txt"
    if not os.path.exists(filename):
        logger.error(f"Archivo {filename} no encontrado.")
        return

    logger.info(f"Leyendo archivo {filename}...")
    
    with open(filename, "r", encoding="utf-8") as f:
        content = f.read()

    # Regex para extraer el nombre de usuario entre (@ y )
    usernames = re.findall(r"\(@(.*?)\)", content)
    
    if not usernames:
        logger.warning("No se encontraron nombres de usuario en el archivo.")
        return

    logger.info(f"Detectados {len(usernames)} posibles nombres de usuario.")

    db = get_db()
    session = db.session
    
    success_count = 0
    not_found_count = 0
    forced_restore_count = 0
    error_count = 0

    # Cache de adaptadores por router
    router_adapters = {}

    try:
        for username in usernames:
            try:
                # Buscar cliente por username
                client = session.query(Client).filter(Client.username == username).first()
                
                if not client:
                    not_found_count += 1
                    continue

                is_already_active = (client.status == 'active')

                # 1. Asegurar estado 'active' en Base de Datos
                if client.status != 'active':
                    client.status = 'active'
                    session.commit()
                
                # 2. Sincronizar con MikroTik (Siempre, para asegurar que esté habilitado)
                if client.router_id:
                    router = session.query(Router).get(client.router_id)
                    if router and router.status == 'online':
                        try:
                            # Conectar al router si no está en cache
                            if router.id not in router_adapters:
                                new_adapter = MikroTikAdapter()
                                if new_adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
                                    router_adapters[router.id] = new_adapter
                                else:
                                    logger.error(f"No se pudo conectar al router {router.alias}")
                                    error_count += 1
                                    continue
                            
                            current_adapter = router_adapters[router.id]
                            logger.info(f"Restaurando servicio en MikroTik: {client.username} (Router: {router.alias})")
                            current_adapter.restore_client_service(client.to_dict())
                            
                            if is_already_active:
                                forced_restore_count += 1
                            else:
                                success_count += 1
                                
                        except Exception as e_mt:
                            logger.error(f"Error en MikroTik para {client.username}: {e_mt}")
                            error_count += 1
                    else:
                        logger.warning(f"Router {client.router_id} fuera de línea o no encontrado.")
                        error_count += 1
                else:
                    logger.warning(f"Cliente {client.username} no tiene router_id asignado.")
                    success_count += 1

            except Exception as e_inner:
                logger.error(f"Error procesando {username}: {e_inner}")
                error_count += 1
                session.rollback()

        # Desconectar todos los adaptadores
        for r_id, adp in router_adapters.items():
            adp.disconnect()

        logger.info("-" * 50)
        logger.info("Resumen de Reactivacion:")
        logger.info(f"   - Reactivados (eran suspended): {success_count}")
        logger.info(f"   - Asegurados (ya eran active): {forced_restore_count}")
        logger.info(f"   - No encontrados en DB: {not_found_count}")
        logger.info(f"   - Errores: {error_count}")
        logger.info("-" * 50)

    except Exception as e:
        logger.error(f"Error critico en el script: {e}")
    finally:
        db.remove_session()

if __name__ == "__main__":
    reactivate_clients()
