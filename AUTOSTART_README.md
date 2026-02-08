# 🚀 Configuración de Inicio Automático - SGUBM

Este documento explica cómo configurar SGUBM para que se inicie automáticamente cuando arranca Windows.

## 📋 Archivos Importantes

- **`SGUBM_Silencioso.vbs`** - Ejecuta el launcher sin mostrar ventanas
- **`launcher.bat`** - Script que inicia el servidor y abre el navegador
- **`setup_autostart.ps1`** - Configura el inicio automático (USAR ESTE)
- **`remove_autostart.ps1`** - Elimina el inicio automático

## 🎯 Configuración Actual

El servidor SGUBM ahora está configurado para:

✅ **Permanecer activo indefinidamente** (no se apaga automáticamente)
✅ **Iniciar en una ventana minimizada** (puedes ver logs si es necesario)
✅ **Abrir automáticamente el navegador** en http://localhost:5000

## 🔧 Instalación del Inicio Automático

### Opción 1: Usando el Script Automatizado (RECOMENDADO)

1. **Haz clic derecho** en el archivo `setup_autostart.ps1`
2. Selecciona **"Ejecutar con PowerShell"**
3. Si aparece un mensaje de seguridad, acepta
4. El script te pedirá permisos de administrador
5. Sigue las instrucciones en pantalla
6. ¡Listo! El sistema se iniciará automáticamente

### Opción 2: Manual (Usando el Programador de Tareas)

1. Presiona `Win + R` y escribe `taskschd.msc`
2. Click en "Crear tarea básica"
3. Nombre: `SGUBM_AutoStart`
4. Trigger: "Al iniciar sesión"
5. Acción: "Iniciar un programa"
6. Programa: `wscript.exe`
7. Argumentos: `"c:\SGUBM-V1\SGUBM_Silencioso.vbs"`
8. Finalizar

## 🛑 Cómo Detener el Servidor

### Desde la barra de tareas:
- Busca la ventana minimizada "SGUBM Server"
- Ciérrala

### Desde PowerShell/CMD:
```powershell
# Encontrar el proceso
Get-Process python | Where-Object {$_.Path -like "*SGUBM*"}

# Detenerlo (reemplaza PID con el número real)
Stop-Process -Id <PID>
```

### Desde el Administrador de Tareas:
- Presiona `Ctrl + Shift + Esc`
- Busca "python.exe" (puede haber varios)
- Identifica el de SGUBM (verifica la línea de comandos)
- Click derecho → "Finalizar tarea"

## ❌ Desinstalar el Inicio Automático

### Opción 1: Usando el Script
1. **Haz clic derecho** en `remove_autostart.ps1`
2. Selecciona **"Ejecutar con PowerShell"**
3. Confirma la eliminación

### Opción 2: Manual
```powershell
# Desde PowerShell como administrador:
Unregister-ScheduledTask -TaskName "SGUBM_AutoStart" -Confirm:$false
```

## 🔄 Inicio Manual (Sin Auto-inicio)

Si prefieres iniciar manualmente el servidor:

1. **Doble click** en `launcher.bat`
   - Se abre una ventana minimizada con el servidor
   - El navegador se abre automáticamente

2. **Desde terminal** (para ver todos los logs):
   ```cmd
   cd c:\SGUBM-V1
   python run.py
   ```

## 🐛 Solución de Problemas

### El servidor no inicia automáticamente
1. Verifica que la tarea existe:
   ```powershell
   Get-ScheduledTask -TaskName "SGUBM_AutoStart"
   ```
2. Verifica el estado de la tarea en el Programador de Tareas
3. Revisa los logs en `c:\SGUBM-V1\server_log.txt` (si existe)

### El navegador no se abre
- El servidor puede tardar 8-10 segundos en iniciar
- Abre manualmente: http://localhost:5000

### Error "Puerto 5000 en uso"
- Otro proceso está usando el puerto 5000
- Detén el proceso anterior o cambia el puerto en `run.py`

### Ver logs del servidor
- La ventana minimizada contiene todos los logs
- Busca "SGUBM Server" en la barra de tareas
- Click para maximizar y ver los logs

## 📊 Verificar que está funcionando

```powershell
# Ver si el servidor está corriendo
Get-Process python | Where-Object {$_.CommandLine -like "*run.py*"}

# Probar la conexión
Invoke-WebRequest -Uri http://localhost:5000 -UseBasicParsing
```

## 🔐 Seguridad

- El servidor se ejecuta con los permisos de tu usuario
- Solo es accesible desde tu computadora (localhost)
- Para acceso desde la red, modifica `host='0.0.0.0'` en `run.py`

## 📞 Soporte

Si encuentras problemas:
1. Revisa los logs en la consola minimizada
2. Ejecuta `python run.py` manualmente para ver errores
3. Verifica que todas las dependencias estén instaladas: `pip install -r requirements.txt`

---

**Última actualización**: 2026-02-05
