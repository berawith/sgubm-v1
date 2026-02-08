@echo off
cd /d "c:\SGUBM-V1"
echo Iniciando prueba de servidor... > startup_debug.log
python run.py >> startup_debug.log 2>&1
