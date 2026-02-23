#!/bin/bash
# ============================================================
# SGUBM - Script de Despliegue para Kamatera (Ubuntu 22.04)
# Ejecutar como root: sudo bash deploy/setup.sh
# ============================================================
set -e

APP_DIR="/opt/sgubm"
APP_USER="sgubm"
LOG_DIR="/var/log/sgubm"

echo "========================================="
echo "  SGUBM - Instalación en Servidor"
echo "========================================="

# 1. Actualizar sistema
echo "📦 [1/8] Actualizando sistema..."
apt update && apt upgrade -y

# 2. Instalar dependencias del sistema
echo "📦 [2/8] Instalando dependencias..."
apt install -y python3.11 python3.11-venv python3-pip \
    nginx curl git ufw \
    nodejs npm

# 3. Crear usuario del sistema
echo "👤 [3/8] Creando usuario sgubm..."
if ! id "$APP_USER" &>/dev/null; then
    useradd --system --shell /bin/false --home $APP_DIR $APP_USER
fi

# 4. Crear directorio de logs
echo "📁 [4/8] Creando directorios..."
mkdir -p $LOG_DIR
chown $APP_USER:$APP_USER $LOG_DIR

# 5. Configurar la aplicación
echo "🔧 [5/8] Configurando aplicación..."
if [ ! -d "$APP_DIR" ]; then
    echo "⚠️  Directorio $APP_DIR no existe."
    echo "   Debes clonar el repositorio primero:"
    echo "   git clone <tu-repo> $APP_DIR"
    echo ""
    echo "   O copiar los archivos manualmente:"
    echo "   scp -r C:\\SGUBM-V1\\* root@<IP>:$APP_DIR/"
    exit 1
fi

cd $APP_DIR

# Crear entorno virtual
echo "🐍 Creando entorno virtual..."
python3.11 -m venv venv
source venv/bin/activate

# Instalar dependencias Python
echo "📦 Instalando dependencias Python..."
pip install --upgrade pip
pip install -r requirements.txt

# Instalar dependencias Node y construir bundle
echo "📦 Instalando dependencias Node y construyendo bundle..."
npm install
npm run build

# Permisos
chown -R $APP_USER:$APP_USER $APP_DIR

# 6. Configurar Nginx
echo "🌐 [6/8] Configurando Nginx..."
cp deploy/nginx-sgubm.conf /etc/nginx/sites-available/sgubm
ln -sf /etc/nginx/sites-available/sgubm /etc/nginx/sites-enabled/sgubm
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

# 7. Configurar Systemd
echo "⚙️  [7/8] Configurando servicio systemd..."
cp deploy/sgubm.service /etc/systemd/system/sgubm.service
systemctl daemon-reload
systemctl enable sgubm
systemctl start sgubm

# 8. Configurar Firewall
echo "🔥 [8/8] Configurando firewall..."
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS (futuro)
ufw --force enable

echo ""
echo "========================================="
echo "  ✅ INSTALACIÓN COMPLETADA"
echo "========================================="
echo ""
echo "  Estado del servicio:"
systemctl status sgubm --no-pager -l
echo ""
echo "  📌 Comandos útiles:"
echo "  - Ver logs:    journalctl -u sgubm -f"
echo "  - Reiniciar:   systemctl restart sgubm"
echo "  - Detener:     systemctl stop sgubm"
echo "  - Estado:      systemctl status sgubm"
echo ""
echo "  🌐 Acceder: http://$(curl -s ifconfig.me)"
echo ""
