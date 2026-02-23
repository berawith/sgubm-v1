#!/bin/bash
# ============================================================
# SGUBM - PASO 2: Configurar App (Ejecutar DESPUÉS de subir archivos)
# ============================================================
set -e
cd /opt/sgubm

echo "========================================="
echo "  SGUBM - PASO 2: Configurando App"
echo "========================================="

# 1. Entorno virtual Python
echo "🐍 Creando entorno virtual..."
python3 -m venv venv
source venv/bin/activate

# 2. Dependencias Python
echo "📦 Instalando dependencias Python..."
pip install --upgrade pip
pip install -r requirements.txt

# 3. Dependencias Node + Build
echo "📦 Instalando dependencias Node..."
npm install
echo "🔨 Construyendo bundle frontend..."
npm run build

# 4. Nginx
echo "🌐 Configurando Nginx..."
cp deploy/nginx-sgubm.conf /etc/nginx/sites-available/sgubm
ln -sf /etc/nginx/sites-available/sgubm /etc/nginx/sites-enabled/sgubm
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

# 5. Systemd Service
echo "⚙️  Configurando servicio..."
cp deploy/sgubm.service /etc/systemd/system/sgubm.service

# Ajustar servicio para usar root (simplificar permisos)
sed -i 's/User=sgubm/User=root/' /etc/systemd/system/sgubm.service
sed -i 's/Group=sgubm/Group=root/' /etc/systemd/system/sgubm.service

systemctl daemon-reload
systemctl enable sgubm
systemctl start sgubm

echo ""
echo "========================================="
echo "  ✅ INSTALACIÓN COMPLETADA"
echo "========================================="
echo ""
systemctl status sgubm --no-pager -l
echo ""
echo "  🌐 Accede a: http://45.126.125.87"
echo ""
echo "  📌 Comandos útiles:"
echo "  - Ver logs:    journalctl -u sgubm -f"
echo "  - Reiniciar:   systemctl restart sgubm"
echo "  - Estado:      systemctl status sgubm"
echo ""
