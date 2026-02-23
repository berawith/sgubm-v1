"""
Script para verificar todos los routers VERACRUZ en la base de datos
"""

import sqlite3

# Conectar a la base de datos
conn = sqlite3.connect('sgubm.db')
cursor = conn.cursor()

# Buscar todos los routers que contengan "VERACRUZ" en su alias
cursor.execute("""
    SELECT 
        id,
        alias,
        host_address,
        api_port,
        api_username,
        status,
        last_error,
        created_at,
        updated_at
    FROM routers
    WHERE UPPER(alias) LIKE '%VERACRUZ%'
    ORDER BY id DESC
""")

routers = cursor.fetchall()

print("\n" + "="*80)
print("ROUTERS VERACRUZ EN LA BASE DE DATOS")
print("="*80 + "\n")

if not routers:
    print("❌ No se encontraron routers con el nombre VERACRUZ\n")
else:
    for r in routers:
        print(f"🔧 Router ID: {r[0]}")
        print(f"   Alias: {r[1]}")
        print(f"   Host: {r[2]}:{r[3]}")
        print(f"   Username: {r[4]}")
        print(f"   Estado: {r[5]}")
        if r[6]:
            print(f"   Último Error: {r[6]}")
        print(f"   Creado: {r[7]}")
        print(f"   Actualizado: {r[8]}")
        print("-" * 80)

print(f"\nTotal de routers VERACRUZ encontrados: {len(routers)}")


# Fin del script
print("\n" + "="*80)

