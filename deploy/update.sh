#!/bin/bash
# ============================================================
# SGUBM - Script de Actualización Rápida
# Ejecutar desde tu PC: ssh root@<IP> 'bash /opt/sgubm/deploy/update.sh'
# ============================================================
set -e

APP_DIR="/opt/sgubm"

echo "🔄 Actualizando SGUBM..."
cd $APP_DIR

# Pull latest changes
echo "📥 Descargando cambios..."
git pull origin main

# Activate venv
source venv/bin/activate

# Install any new Python dependencies
echo "📦 Actualizando dependencias Python..."
pip install -r requirements.txt --quiet

# Rebuild frontend bundle
echo "🔨 Reconstruyendo bundle..."
npm install --silent
npm run build

# Fix permissions
chown -R sgubm:sgubm $APP_DIR

# Restart service
echo "♻️  Reiniciando servicio..."
systemctl restart sgubm

echo "✅ Actualización completada."
echo "   Estado: $(systemctl is-active sgubm)"
