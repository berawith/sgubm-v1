import os
import sqlite3
import shutil
import zipfile
from datetime import datetime
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ==========================================
# CONFIGURACIÓN
# ==========================================
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'sgubm.db')
BACKUP_DIR = os.path.join(os.path.dirname(__file__), 'temp')
CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), 'credentials.json')
GDRIVE_FOLDER_ID = 'TU_ID_DE_CARPETA_DE_GOOGLE_DRIVE_AQUI' # <- REEMPLAZAR
RETENTION_DAYS = 7 # Cuántos backups mantener en Google Drive

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Scopes requeridos por Google Drive
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def create_local_backup():
    """Crea una copia segura de la base de datos (seguro para WAL mode) y la comprime."""
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
        
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_db_path = os.path.join(BACKUP_DIR, f'sgubm_backup_{timestamp}.db')
    zip_path = os.path.join(BACKUP_DIR, f'sgubm_backup_{timestamp}.zip')
    
    logger.info(f"💾 Iniciando backup local de: {DB_PATH}")
    
    try:
        # Usar la API de backup de SQLite para asegurar consistencia (especial para WAL)
        src_conn = sqlite3.connect(DB_PATH)
        dst_conn = sqlite3.connect(backup_db_path)
        with dst_conn:
            src_conn.backup(dst_conn)
        dst_conn.close()
        src_conn.close()
        
        # Comprimir el archivo en un ZIP con contraseña si lo deseas (aquí es sin contraseña)
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(backup_db_path, os.path.basename(backup_db_path))
            
        # Limpiar el archivo .db temporal, dejando solo el .zip
        os.remove(backup_db_path)
        
        logger.info(f"✅ Backup local comprimido creado: {zip_path}")
        return zip_path
        
    except Exception as e:
        logger.error(f"❌ Error creando backup local: {e}")
        return None

def upload_to_gdrive(file_path):
    """Sube el archivo comprimido a Google Drive."""
    if not os.path.exists(CREDENTIALS_FILE):
        logger.error(f"❌ Archivo de credenciales no encontrado: {CREDENTIALS_FILE}")
        logger.error("=> Lee el archivo README.md para saber cómo obtener credentials.json")
        return False
        
    if GDRIVE_FOLDER_ID == 'TU_ID_DE_CARPETA_DE_GOOGLE_DRIVE_AQUI':
        logger.error("❌ Debes configurar el GDRIVE_FOLDER_ID en el código del script.")
        return False

    try:
        logger.info("☁️ Autenticando con Google Drive...")
        creds = service_account.Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        service = build('drive', 'v3', credentials=creds)
        
        file_name = os.path.basename(file_path)
        file_metadata = {
            'name': file_name,
            'parents': [GDRIVE_FOLDER_ID]
        }
        
        media = MediaFileUpload(file_path, mimetype='application/zip', resumable=True)
        
        logger.info(f"⬆️ Subiendo {file_name} a Google Drive...")
        uploaded_file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        
        logger.info(f"✅ Archivo subido exitosamente. File ID: {uploaded_file.get('id')}")
        return service
        
    except Exception as e:
        logger.error(f"❌ Error subiendo a Google Drive: {e}")
        return None

def clean_old_backups(service):
    """Elimina backups más antiguos que RETENTION_DAYS."""
    if not service:
        return
        
    try:
        logger.info(f"🧹 Buscando backups antiguos (>{RETENTION_DAYS} días)...")
        # Fecha límite
        from datetime import timedelta
        cutoff_date = (datetime.now() - timedelta(days=RETENTION_DAYS)).isoformat() + "Z"
        
        # Buscar archivos en la carpeta
        query = f"'{GDRIVE_FOLDER_ID}' in parents and createdTime < '{cutoff_date}' and name contains 'sgubm_backup_'"
        results = service.files().list(q=query, spaces='drive', fields='files(id, name, createdTime)').execute()
        items = results.get('files', [])
        
        if not items:
            logger.info("✨ No hay backups antiguos para eliminar.")
        else:
            for item in items:
                logger.info(f"🗑️ Eliminando backup antiguo: {item['name']}")
                service.files().delete(fileId=item['id']).execute()
                
    except Exception as e:
        logger.error(f"❌ Error limpiando backups antiguos: {e}")

def run_backup_routine():
    logger.info("="*50)
    logger.info("🚀 INICIANDO RUTINA DE RESPALDO SGUBM-V1")
    logger.info("="*50)
    
    zip_path = create_local_backup()
    if zip_path:
        service = upload_to_gdrive(zip_path)
        if service:
            clean_old_backups(service)
            
        # Limpiar archivo temporal local después de subir (éxito o fallo)
        if os.path.exists(zip_path):
            os.remove(zip_path)
            logger.info("🧹 Archivo comprimido local eliminado después de procesar.")
            
    logger.info("="*50)
    logger.info("🏁 RUTINA DE RESPALDO FINALIZADA")
    logger.info("="*50)

if __name__ == '__main__':
    run_backup_routine()
