
import shutil
import os
import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_restore_point():
    # Rutas
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    restore_point_name = f"RESTORE_POINT_{timestamp}"
    backup_base = 'backups'
    restore_dir = os.path.join(backup_base, restore_point_name)
    
    # Directorios y archivos a respaldar
    to_backup = {
        'directories': ['src'],
        'files': ['.env', 'requirements.txt', 'package.json', 'webpack.config.js', 'sgubm.db', 'sgubm_audit.db', 'sgubm_temp.db']
    }
    
    # Crear directorios si no existen
    if not os.path.exists(backup_base):
        os.makedirs(backup_base)
    if not os.path.exists(restore_dir):
        os.makedirs(restore_dir)
        
    logger.info(f"🚀 Iniciando creación de punto de restauración: {restore_point_name}")
    
    try:
        # Respaldar directorios
        for d in to_backup['directories']:
            if os.path.exists(d):
                dest = os.path.join(restore_dir, d)
                shutil.copytree(d, dest, dirs_exist_ok=True)
                logger.info(f"✅ Directorio '{d}' respaldado.")
            else:
                logger.warning(f"⚠️ Directorio '{d}' no encontrado, saltando.")

        # Respaldar archivos
        for f in to_backup['files']:
            if os.path.exists(f):
                shutil.copy2(f, restore_dir)
                logger.info(f"✅ Archivo '{f}' respaldado.")
            else:
                # Buscar en subdirectorios si no está en raíz (ej. DBs)
                if f.endswith('.db'):
                    db_internal = os.path.join('src', 'infrastructure', 'database', f)
                    if os.path.exists(db_internal):
                        shutil.copy2(db_internal, restore_dir)
                        logger.info(f"✅ Archivo '{f}' respaldado desde infrastructure/database.")
                        continue
                logger.warning(f"⚠️ Archivo '{f}' no encontrado.")

        # Crear Manifiesto
        manifest_content = f"""PUNTO DE RESTAURACIÓN TOTAL - SGUBM-V1
Fecha: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Nombre: {restore_point_name}

Contenido:
- Código Fuente (directorio src/)
- Bases de Datos (sgubm.db, sgubm_audit.db, etc.)
- Configuración (.env, requirements.txt, kit de construcción)

Este es un respaldo manual completo solicitado por el usuario.
"""
        with open(os.path.join(restore_dir, 'MANIFEST.txt'), 'w', encoding='utf-8') as m:
            m.write(manifest_content)
            
        logger.info(f"✨ Punto de restauración finalizado exitosamente en: {restore_dir}")
        print(f"\n✅ PUNTO DE RESTAURACIÓN CREADO: {restore_dir}")
        return True
            
    except Exception as e:
        logger.error(f"❌ Error fatal creando punto de restauración: {e}")
        return False

if __name__ == "__main__":
    create_restore_point()
