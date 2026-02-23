
import shutil
import os
import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_backup():
    # Rutas
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    db_path = 'sgubm.db'
    backup_dir = 'backups'
    backup_filename = f"sgubm_backup_FULL_BEFORE_SYNC_{timestamp}.db"
    backup_path = os.path.join(backup_dir, backup_filename)
    
    # Crear directorio si no existe
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
        
    try:
        # Copiar base de datos
        if os.path.exists(db_path):
            shutil.copy2(db_path, backup_path)
            logger.info(f"✅ Copia de seguridad creada exitosamente: {backup_path}")
            
            # Copiar config .env también por seguridad
            if os.path.exists('.env'):
                shutil.copy2('.env', os.path.join(backup_dir, f".env.backup_{timestamp}"))
                logger.info("✅ Archivo .env respaldado.")
                
            return True
        else:
            logger.error(f"❌ No se encontró la base de datos en {db_path}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error creando backup: {e}")
        return False

if __name__ == "__main__":
    create_backup()
