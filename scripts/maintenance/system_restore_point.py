
import shutil
import os
import datetime
import zipfile
import logging

# Configuración de logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("backup_process.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def create_system_restore_point():
    """
    Crea un punto de restauración completo del sistema SGUBM.
    Incluye bases de datos, código fuente y configuraciones críticas.
    """
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_root = 'backups'
    point_dir = os.path.join(backup_root, f"RESTORE_POINT_{timestamp}")
    
    # Archivos y carpetas críticas
    CORE_FILES = ['sgubm.db', 'sgubm_audit.db', 'sgubm_temp.db', '.env', 'package.json', 'webpack.config.js', 'requirements.txt']
    CORE_DIRS = ['src', 'config']
    EXCLUDE_DIRS = ['node_modules', '__pycache__', '.git', '.gemini', 'backups', 'dist']

    try:
        # 1. Crear directorio del punto de restauración
        if not os.path.exists(point_dir):
            os.makedirs(point_dir)
            logger.info(f"📁 Directorio de respaldo creado: {point_dir}")

        # 2. Respaldar Bases de Datos y Archivos Raíz
        for file in CORE_FILES:
            if os.path.exists(file):
                shutil.copy2(file, point_dir)
                logger.info(f"✅ Archivo respaldado: {file}")
            else:
                logger.warning(f"⚠️ Archivo no encontrado (omitido): {file}")

        # 3. Crear ZIP de Código Fuente y Directorios Críticos
        zip_filename = os.path.join(point_dir, f"sgubm_source_{timestamp}.zip")
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root_dir in CORE_DIRS:
                if not os.path.exists(root_dir):
                    continue
                    
                for root, dirs, files in os.walk(root_dir):
                    # Omitir carpetas excluidas
                    dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
                    
                    for file in files:
                        file_path = os.path.join(root, file)
                        # Omitir archivos extremadamente grandes si es necesario (ej: logs de 40MB)
                        if os.path.getsize(file_path) > 10 * 1024 * 1024: # >10MB
                             continue
                             
                        zipf.write(file_path, os.path.relpath(file_path, os.path.join(root_dir, '..')))
        
        logger.info(f"📦 Código fuente comprimido exitosamente: {zip_filename}")

        # 4. Crear un resumen del punto de restauración
        with open(os.path.join(point_dir, 'RESTORATION_KEY.txt'), 'w', encoding='utf-8') as f:
            f.write(f"PUNTO DE RESTAURACIÓN COMPLETO - SGUBM ULTRA\n")
            f.write(f"Fecha: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"ID: {timestamp}\n")
            f.write(f"------------------------------------------\n")
            f.write(f"Este respaldo contiene el estado estable del sistema después de las correcciones definitivas.\n")

        print(f"\n🚀 PUNTO DE RESPALDO CREADO EXITOSAMENTE EN: {point_dir}\n")
        return True

    except Exception as e:
        logger.error(f"❌ Error crítico durante el respaldo: {e}")
        return False

if __name__ == "__main__":
    create_system_restore_point()
