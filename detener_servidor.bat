@echo off
echo 🛑 Deteniendo el servidor SGUBM...
taskkill /f /im python.exe /t >nul 2>&1
taskkill /f /im pythonw.exe /t >nul 2>&1
echo ✅ Servidor detenido exitosamente.
pause
