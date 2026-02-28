# 🛡️ Respaldo Automático a Google Drive (SGUBM-V1)

Este módulo permite crear una copia de seguridad segura de tu base de datos SQLite (`sgubm.db`) aún estando en modo concurrencia (WAL), comprimirla en un ZIP y subirla automáticamente a una carpeta de Google Drive configurada.

Adicionalmente, el script limpiará los respaldos con más de 7 días de antigüedad para no saturar tu nube.

## 🛠️ Instrucciones de Configuración Inicial

### 1. Requisitos
Asegúrate de haber instalado las dependencias requeridas (que ahora están en `requirements.txt`):
```bash
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

### 2. Crear las Credenciales (Service Account) en Google Cloud
Debemos crear una "Cuenta de Servicio" (un robot) que tenga permiso para subir archivos a **tu** Google Drive sin pedirte contraseñas.

1. Ve a la [Consola de Google Cloud](https://console.cloud.google.com/).
2. Crea un **Nuevo Proyecto** (ej. "SGUB-Backups").
3. Ve a **APIs y Servicios > Biblioteca** y busca **"Google Drive API"**. Dale a **Habilitar**.
4. Ve a **APIs y Servicios > Credenciales**.
5. Haz clic en **Crear Credenciales > Cuenta de Servicio**.
6. Ponle un nombre (ej. `backup-robot`).
7. Una vez creada, haz clic en el nombre de la cuenta en la lista. Ve a la pestaña **Claves (Keys)**.
8. **Agregar Clave > Crear clave nueva > Tipo JSON**. 
9. Esto descargará un archivo `.json` a tu computadora.
10. Renombra ese archivo a `credentials.json` y colócalo exactamente en esta misma carpeta (`c:\SGUBM-V1\scripts\backup\credentials.json`).

### 3. Configurar la Carpeta de Destino en Drive
1. Ve a tu Google Drive normal (`drive.google.com`).
2. Crea una carpeta llamada "Respaldos SGUB".
3. Tienes que "Compartir" esa carpeta con el robot. 
   - Abre tu archivo `credentials.json`. Busca el campo que dice `"client_email"`. Se vera algo como `backup-robot@sgub-backups.iam.gserviceaccount.com`.
   - Copia ese correo.
   - Ve a Drive, haz clic derecho en la carpeta "Respaldos SGUB" > Compartir.
   - Pega el correo del robot y ponle permisos de **Editor**.
4. Ahora, observa la URL de esa carpeta de Drive en tu navegador:
   `https://drive.google.com/drive/folders/1aBcDeFgHiJkLmNoPqRsTuVwXyZ`
5. El código alfabético al final (`1aBcDeFgHiJkLmNoPqRsTuVwXyZ`) es tu **Folder ID**.
6. Abre el archivo `gdrive_backup.py` y busca esta línea arriba del todo:
   ```python
   GDRIVE_FOLDER_ID = 'TU_ID_DE_CARPETA_DE_GOOGLE_DRIVE_AQUI'
   ```
7. Reemplaza el texto por tu Folder ID real.

### 4. Automatizar el Script (Windows Tareas / Linux Cron)
El script debe ejecutarse de forma automática todos los días a medianoche o a la madrugada.

**En Linux (Ubuntu VPS):**
Abre el editor de Cron (`crontab -e`) y añade esto para que corra a las 3:00 AM todos los días:
```bash
0 3 * * * /opt/sgubm/venv/bin/python /opt/sgubm/scripts/backup/gdrive_backup.py >> /var/log/sgubm/backup.log 2>&1
```

**En Windows (Si ejecutas localmente):**
1. Abre el "Programador de Tareas".
2. Crea una "Tarea Básica".
3. Ponle nombre "Backups SGUB" de tipo "Diario" (ej. 3:00 AM).
4. En "Acción" pon "Iniciar un programa".
5. Programa: `python`
6. Argumentos: `C:\SGUBM-V1\scripts\backup\gdrive_backup.py`

¡Y listo! Tu facturación blindada y en la nube.
