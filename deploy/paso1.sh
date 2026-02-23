#!/bin/bash
# ============================================================
# SGUBM - INSTALACIÓN COMPLETA (Copiar y pegar en PuTTY)
# ============================================================
set -e
echo "========================================="
echo "  SGUBM - PASO 1: Preparando Servidor"
echo "========================================="

# 1. Actualizar sistema
echo "📦 Actualizando sistema..."
apt update -y && apt upgrade -y

# 2. Instalar Python, Node, Nginx, Git
echo "📦 Instalando dependencias..."
apt install -y python3 python3-venv python3-pip nginx curl git unzip
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs

# 3. Crear directorios
echo "📁 Creando directorios..."
mkdir -p /opt/sgubm /var/log/sgubm

# 4. Configurar firewall
echo "🔥 Configurando firewall..."
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo ""
echo "========================================="
echo "  ✅ PASO 1 COMPLETO"
echo "========================================="
echo ""
echo "  Ahora ejecuta DESDE TU PC (PowerShell):"
echo ""
echo "  scp -r C:\SGUBM-V1\* root@45.126.125.87:/opt/sgubm/"
echo ""
echo "  Después de subir los archivos, ejecuta el PASO 2:"
echo "  bash /opt/sgubm/deploy/paso2.sh"
echo ""
