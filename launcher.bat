@echo off
:: Moverse al directorio del proyecto
cd /d "c:\SGUBM-V1"

:: Iniciar el sistema en segundo plano sin ventana (Usamos la ruta absoluta por seguridad)
start /b "" "C:\Python314\python.exe" run.py

:: Esperar 10 segundos a que el servidor Flask inicie completamente
timeout /t 10 /nobreak >nul

:: Abrir el navegador en la dirección del sistema
start http://localhost:5000

:: Finalizar el script
exit
