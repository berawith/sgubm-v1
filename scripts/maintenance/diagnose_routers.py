"""
Script de Diagnóstico de Conectividad para Routers MikroTik
Verifica conectividad de red y acceso a API para routers offline
"""

import subprocess
import socket
import sys
from datetime import datetime

# Routers a diagnosticar
ROUTERS = [
    {"id": 5, "alias": "MI JARDIN", "host": "12.12.12.39", "port": 8728},
    {"id": 8, "alias": "VERACRUZ", "host": "12.12.12.50", "port": 8728}
]

def print_header(text):
    print("\n" + "="*80)
    print(f"  {text}")
    print("="*80)

def test_ping(host):
    """Prueba conectividad ICMP (ping)"""
    try:
        # Windows usa -n, Linux usa -c
        result = subprocess.run(
            ["ping", "-n", "4", host],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            # Extraer estadísticas
            output = result.stdout
            if "Recibidos = " in output:
                # Formato Windows
                lines = output.split('\n')
                for line in lines:
                    if "Recibidos = " in line or "Perdidos = " in line:
                        print(f"     {line.strip()}")
                    if "Mínimo = " in line:
                        print(f"     {line.strip()}")
            return True
        else:
            print("     ❌ Host no responde a ping")
            return False
    except subprocess.TimeoutExpired:
        print("     ❌ Timeout - Host no alcanzable")
        return False
    except Exception as e:
        print(f"     ❌ Error al hacer ping: {e}")
        return False

def test_port(host, port):
    """Prueba si el puerto TCP está abierto"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print(f"     ✅ Puerto {port} ABIERTO")
            return True
        else:
            print(f"     ❌ Puerto {port} CERRADO o filtrado")
            return False
    except socket.timeout:
        print(f"     ❌ Timeout al conectar al puerto {port}")
        return False
    except Exception as e:
        print(f"     ❌ Error al probar puerto: {e}")
        return False

def test_mikrotik_api(host, port, username="admin"):
    """Intenta establecer conexión con la API de MikroTik"""
    print(f"     🔌 Intentando conexión API MikroTik...")
    try:
        # Importar el adapter si está disponible
        sys.path.insert(0, 'c:\\SGUBM-V1')
        from src.infrastructure.mikrotik.adapter import MikroTikAdapter
        
        adapter = MikroTikAdapter()
        # Se necesitará la contraseña, que no podemos obtener del script
        # Solo hacemos prueba básica de socket
        print(f"     ⚠️  No se puede probar credenciales sin contraseña")
        return None
    except Exception as e:
        print(f"     ❌ Error al importar adapter: {e}")
        return False

def main():
    print_header("🔍 DIAGNÓSTICO DE CONECTIVIDAD DE ROUTERS MIKROTIK")
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = []
    
    for router in ROUTERS:
        print_header(f"Router: {router['alias']} (ID {router['id']})")
        print(f"Host: {router['host']}:{router['port']}")
        
        result = {
            "router": router,
            "ping": False,
            "port": False,
            "api": None
        }
        
        # Prueba 1: Ping
        print("\n  📡 Prueba 1: ICMP Ping")
        result["ping"] = test_ping(router['host'])
        
        # Prueba 2: Puerto TCP
        print(f"\n  🔌 Prueba 2: Puerto TCP {router['port']}")
        result["port"] = test_port(router['host'], router['port'])
        
        # Prueba 3: API MikroTik (limitada)
        print(f"\n  🔐 Prueba 3: API MikroTik")
        result["api"] = test_mikrotik_api(router['host'], router['port'])
        
        results.append(result)
    
    # Resumen
    print_header("📊 RESUMEN DE DIAGNÓSTICO")
    
    for res in results:
        r = res['router']
        print(f"\n🔧 {r['alias']} ({r['host']}:{r['port']})")
        print(f"   Ping:   {'✅ OK' if res['ping'] else '❌ FALLO'}")
        print(f"   Puerto: {'✅ ABIERTO' if res['port'] else '❌ CERRADO'}")
        
        # Diagnóstico
        if not res['ping']:
            print("   📋 Diagnóstico: Router no alcanzable por red")
            print("      • Verifica que el router esté encendido")
            print("      • Verifica cables de red y switches")
            print("      • Verifica que la IP sea correcta")
        elif not res['port']:
            print("   📋 Diagnóstico: Router alcanzable pero puerto API cerrado")
            print("      • El servicio API podría estar deshabilitado")
            print("      • Firewall podría estar bloqueando el puerto 8728")
            print("      • Verifica configuración: /ip service en MikroTik")
        else:
            print("   📋 Diagnóstico: Conectividad OK - Posible problema de credenciales")
            print("      • Verifica usuario y contraseña en la base de datos")
            print("      • Verifica permisos del usuario API en MikroTik")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    main()
