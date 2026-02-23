"""
Script para regularizar FelixAlvarado:
1. Restaurar desde papelera (cambiar status de 'deleted' a 'active')
2. Mover al router VERACRUZ (ID 8)
3. Actualizar IP a la nueva (10.10.80.14)
"""

import sqlite3
from datetime import datetime

conn = sqlite3.connect('sgubm.db')
cursor = conn.cursor()

# Parámetros
CLIENT_ID = 69
NEW_ROUTER_ID = 8  # VERACRUZ
NEW_IP = "10.10.80.14"

print("\n" + "="*80)
print("REGULARIZANDO FELIXALVARADO")
print("="*80 + "\n")

# Mostrar estado actual
cursor.execute("SELECT legal_name, status, router_id, ip_address FROM clients WHERE id = ?", (CLIENT_ID,))
current = cursor.fetchone()

print("📋 Estado ANTES:")
print(f"   Nombre: {current[0]}")
print(f"   Estado: {current[1]}")
print(f"   Router ID: {current[2]}")
print(f"   IP: {current[3]}")
print()

# Confirmar acción
print("⚠️  ACCIÓN A REALIZAR:")
print(f"   ✓ Restaurar cliente (deleted → active)")
print(f"   ✓ Mover a router VERACRUZ (ID {NEW_ROUTER_ID})")
print(f"   ✓ Actualizar IP a {NEW_IP}")
print()

respuesta = input("¿Deseas continuar? (SI/no): ").strip().upper()

if respuesta == "SI":
    # Actualizar cliente
    cursor.execute("""
        UPDATE clients
        SET 
            status = 'active',
            router_id = ?,
            ip_address = ?,
            updated_at = ?
        WHERE id = ?
    """, (NEW_ROUTER_ID, NEW_IP, datetime.now(), CLIENT_ID))
    
    conn.commit()
    
    # Verificar cambios
    cursor.execute("SELECT legal_name, status, router_id, ip_address FROM clients WHERE id = ?", (CLIENT_ID,))
    updated = cursor.fetchone()
    
    print("\n✅ CLIENTE ACTUALIZADO:")
    print(f"   Nombre: {updated[0]}")
    print(f"   Estado: {updated[1]}")
    print(f"   Router ID: {updated[2]}")
    print(f"   IP: {updated[3]}")
    print()
    
    print("📡 SIGUIENTE PASO:")
    print("   Ahora debes SINCRONIZAR el router VERACRUZ desde el dashboard para:")
    print("   1. Crear el secret PPPoE para FelixAlvarado")
    print("   2. Configurar el queue correspondiente")
    print()
    print("   ⚠️  IMPORTANTE: El router VERACRUZ tiene problemas de credenciales API.")
    print("   Antes de sincronizar, verifica que la contraseña API esté correcta.")
    
else:
    print("\n❌ Operación cancelada")

conn.close()
