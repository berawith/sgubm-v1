# 🚀 Guía de Despliegue SGUBM en Kamatera

## Paso 1: Crear Servidor en Kamatera

1. Ir a [kamatera.com](https://kamatera.com) y crear cuenta (30 días gratis con $100 crédito)
2. Crear un nuevo servidor con estas specs:

| Recurso | Valor |
|---------|-------|
| **OS** | Ubuntu 22.04 LTS |
| **vCPU** | 2 |
| **RAM** | 4 GB |
| **Disco** | 40 GB SSD |
| **Ubicación** | Miami (más cercano a Venezuela) |

3. Anotar la **IP pública** y **contraseña root** que te dan

---

## Paso 2: Subir el Código al Servidor

### Opción A: Con Git (Recomendado)

Desde tu PC, primero sube el código a GitHub:
```powershell
cd C:\SGUBM-V1
git init
git add .
git commit -m "Initial deployment"
git remote add origin https://github.com/TU_USUARIO/sgubm.git
git push -u origin main
```

Luego en el servidor (conectarte via SSH con PuTTY o terminal):
```bash
ssh root@IP_DEL_SERVIDOR
git clone https://github.com/TU_USUARIO/sgubm.git /opt/sgubm
```

### Opción B: Con SCP (Sin Git)

```powershell
# Desde PowerShell en tu PC:
scp -r C:\SGUBM-V1\* root@IP_DEL_SERVIDOR:/opt/sgubm/
```

---

## Paso 3: Subir la Base de Datos

```powershell
# Desde PowerShell en tu PC:
scp C:\SGUBM-V1\sgubm.db root@IP_DEL_SERVIDOR:/opt/sgubm/sgubm.db
```

---

## Paso 4: Ejecutar Instalación Automática

Conectarse al servidor y ejecutar el setup:
```bash
ssh root@IP_DEL_SERVIDOR
cd /opt/sgubm
chmod +x deploy/setup.sh
sudo bash deploy/setup.sh
```

**Esto automáticamente:**
- Instala Python 3.11, Node.js, Nginx
- Crea el entorno virtual y las dependencias
- Construye el bundle del frontend
- Configura Nginx como proxy
- Configura el servicio systemd para auto-inicio
- Abre los puertos del firewall (22, 80, 443)

---

## Paso 5: Verificar

Abrir el navegador y visitar:
```
http://IP_DEL_SERVIDOR
```

Si todo está correcto, verás el dashboard de SGUBM.

---

## Comandos Útiles en el Servidor

```bash
# Ver logs en tiempo real
journalctl -u sgubm -f

# Reiniciar la app
systemctl restart sgubm

# Ver estado
systemctl status sgubm

# Ver logs de Nginx
tail -f /var/log/sgubm/access.log
tail -f /var/log/sgubm/error.log
```

---

## Actualizar el Código (Workflow Diario)

### Desde tu PC (después de hacer cambios):
```powershell
cd C:\SGUBM-V1
git add .
git commit -m "Descripción del cambio"
git push
```

### En el servidor (aplicar cambios):
```bash
ssh root@IP_DEL_SERVIDOR 'bash /opt/sgubm/deploy/update.sh'
```

O puedes hacer el pull manualmente:
```bash
ssh root@IP_DEL_SERVIDOR
cd /opt/sgubm
git pull
source venv/bin/activate
pip install -r requirements.txt
npm run build
systemctl restart sgubm
```

---

## Archivos Creados

| Archivo | Función |
|---------|---------|
| `wsgi.py` | Punto de entrada para Gunicorn (producción) |
| `deploy/setup.sh` | Script de instalación completa |
| `deploy/update.sh` | Script de actualización rápida |
| `deploy/nginx-sgubm.conf` | Configuración de Nginx |
| `deploy/sgubm.service` | Servicio systemd (auto-inicio) |
| `requirements.txt` | Dependencias actualizadas con gunicorn/eventlet |

---

## Agregar Dominio + SSL (Opcional)

```bash
# 1. Apuntar tu dominio a la IP del servidor (DNS A Record)
# 2. Instalar Certbot
apt install certbot python3-certbot-nginx -y

# 3. Obtener certificado SSL gratis (Let's Encrypt)
certbot --nginx -d sgubm.tudominio.com

# 4. Renovación automática
certbot renew --dry-run
```
