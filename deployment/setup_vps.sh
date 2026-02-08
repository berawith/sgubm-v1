#!/bin/bash

# Script de instalación automática para SGUBM en Ubuntu 22.04/24.04

echo "🚀 Iniciando instalación de dependencias para SGUBM..."

# 1. Actualizar sistema
sudo apt update && sudo apt upgrade -y

# 2. Instalar Python, Nginx y herramientas de red
sudo apt install -y python3-pip python3-venv nginx git wireguard wireguard-tools

# 3. Preparar directorio
sudo mkdir -p /var/www/sgubm
sudo chown -R $USER:$USER /var/www/sgubm

puts "✅ Directorio /var/www/sgubm creado. Ahora sube los archivos aquí."
puts "   (Usa WinSCP o FileZilla desde tu PC)"

echo "💡 PASOS SIGUIENTES:"
echo "1. Sube todo el código a /var/www/sgubm"
echo "2. Crea el entorno virtual: python3 -m venv venv"
echo "3. Instala dependencias: ./venv/bin/pip install -r requirements.txt"
echo "4. Instala Gunicorn: ./venv/bin/pip install gunicorn eventlet"
echo "5. Configura WireGuard en /etc/wireguard/wg0.conf"
