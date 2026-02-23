"""
Script para verificar y asegurar que FelixAlvarado tenga servicio en VERACRUZ
1. Obtener detalles del plan PV-3100
2. Verificar si existe queue en Router 8
3. Si no existe, crearla
"""

import sqlite3
import sys
import os

# Ajustar path para importar módulos del proyecto
sys.path.append(os.getcwd())

from src.infrastructure.mikrotik.adapter import MikroTikAdapter

def get_plan_details(cursor, plan_name):
    # Intentar buscar por nombre en internet_plans
    # download_speed/upload_speed están en kbps en la BD
    try:
        cursor.execute("SELECT download_speed, upload_speed FROM internet_plans WHERE name = ?", (plan_name,))
        plan = cursor.fetchone()
        if plan:
            # Convertir kbps a bps para el calculo posterior
            return (plan[0] * 1000, plan[1] * 1000)
    except Exception as e:
        print(f"⚠️ Error consultando plan: {e}")
    
    # Fallback default (15M)
    return (15 * 1024 * 1024, 15 * 1024 * 1024)

def main():
    conn = sqlite3.connect('sgubm.db')
    cursor = conn.cursor()

    # Datos del cliente
    CLIENT_IP = "10.10.80.14"
    CLIENT_NAME = "FelixAlvarado" # O un nombre sanitizado
    PLAN_NAME = "PV-3100"
    ROUTER_ID = 8

    # Obtener credenciales router
    cursor.execute("SELECT host_address, api_username, api_password, api_port FROM routers WHERE id = ?", (ROUTER_ID,))
    router = cursor.fetchone()
    
    if not router:
        print("❌ Router VERACRUZ no encontrado en BD")
        return

    host, user, password, port = router
    
    # Obtener velocidad plan
    plan_down, plan_up = get_plan_details(cursor, PLAN_NAME)
    max_limit = f"{int(plan_up/1000)}k/{int(plan_down/1000)}k" # MikroTik format: upload/download
    # Si es > 1M, mejor usar M? MikroTik acepta k o M.
    if plan_down >= 1000000:
        max_limit = f"{int(plan_up/1000000)}M/{int(plan_down/1000000)}M"

    print(f"🔧 Verificando servicio para {CLIENT_NAME} ({CLIENT_IP}) en {host}")
    print(f"   Plan: {PLAN_NAME} -> Limit: {max_limit}")

    adapter = MikroTikAdapter()
    try:
        connected = adapter.connect(host, user, password, port)
        if not connected:
            print("❌ No se pudo conectar al router. Verifica credenciales (aunque el usuario dijo que ya estaba arreglado).")
            return

        # Verificar Queues
        api = adapter._api_connection
        queues = api.get_resource('/queue/simple').get()
        
        found = False
        for q in queues:
            target = q.get('target', '')
            if CLIENT_IP in target:
                print(f"✅ Queue encontrada:")
                print(f"   Nombre: {q.get('name')}")
                print(f"   Target: {q.get('target')}")
                print(f"   Max Limit: {q.get('max-limit')}")
                found = True
                break
        
        if not found:
            print("⚠️ Queue NO encontrada. Creando...")
            
            queue_payload = {
                'name': CLIENT_NAME,
                'target': f"{CLIENT_IP}/32",
                'max-limit': max_limit,
                'comment': "Regularized via Assistant"
            }
            
            try:
                api.get_resource('/queue/simple').add(**queue_payload)
                print("✅ Queue creada exitosamente!")
            except Exception as e:
                print(f"❌ Error creando queue: {e}")
        else:
            print("✅ El cliente ya tiene servicio configurado.")

        adapter.disconnect()

    except Exception as e:
        print(f"❌ Error general: {e}")

    conn.close()

if __name__ == "__main__":
    main()
