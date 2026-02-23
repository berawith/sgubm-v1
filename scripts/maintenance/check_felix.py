"""
Script para verificar el estado de FelixAlvarado en la base de datos
"""

import sqlite3

conn = sqlite3.connect('sgubm.db')
cursor = conn.cursor()

# Buscar cliente FelixAlvarado
cursor.execute("""
    SELECT 
        id,
        subscriber_code,
        legal_name,
        ip_address,
        router_id,
        status,
        is_deleted,
        deleted_at
    FROM clients
    WHERE legal_name LIKE '%Felix%' OR legal_name LIKE '%Alvarado%'
""")

clients = cursor.fetchall()

print("\n" + "="*80)
print("CLIENTE FELIX ALVARADO")
print("="*80 + "\n")

if not clients:
    print("❌ No se encontró el cliente FelixAlvarado")
else:
    for c in clients:
        print(f"🆔 Cliente ID: {c[0]}")
        print(f"   Código: {c[1]}")
        print(f"   Nombre: {c[2]}")
        print(f"   IP: {c[3]}")
        print(f"   Router ID: {c[4]}")
        print(f"   Estado: {c[5]}")
        print(f"   ¿Eliminado?: {c[6]}")
        if c[7]:
            print(f"   Fecha Eliminación: {c[7]}")
        print("-" * 80)

# Verificar información del router actual
if clients and clients[0][4]:
    router_id = clients[0][4]
    cursor.execute("""
        SELECT alias, host_address
        FROM routers
        WHERE id = ?
    """, (router_id,))
    
    router = cursor.fetchone()
    if router:
        print(f"\n📡 Router Actual: {router[0]} ({router[1]})")
    else:
        print(f"\n⚠️ Router ID {router_id} no encontrado")

# Verificar router VERACRUZ
cursor.execute("""
    SELECT id, alias, host_address
    FROM routers
    WHERE UPPER(alias) LIKE '%VERACRUZ%'
""")

veracruz = cursor.fetchone()
if veracruz:
    print(f"\n📡 Router VERACRUZ:")
    print(f"   ID: {veracruz[0]}")
    print(f"   Alias: {veracruz[1]}")
    print(f"   Host: {veracruz[2]}")

conn.close()
