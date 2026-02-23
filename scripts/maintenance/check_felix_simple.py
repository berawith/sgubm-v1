"""
Script simplificado para verificar FelixAlvarado
"""

import sqlite3

conn = sqlite3.connect('sgubm.db')
cursor = conn.cursor()

# Primero ver estructura de la tabla
cursor.execute("PRAGMA table_info(clients)")
columns = cursor.fetchall()

print("\n" + "="*80)
print("COLUMNAS DE LA TABLA CLIENTS")
print("="*80)
for col in columns:
    print(f"  {col[1]} ({col[2]})")

# Buscar todos los clientes con Felix o Alvarado
cursor.execute("SELECT * FROM clients WHERE legal_name LIKE '%Felix%' OR legal_name LIKE '%Alvarado%'")
clients = cursor.fetchall()

print("\n" + "="*80)
print("CLIENTE(S) FELIX ALVARADO")
print("="*80 + "\n")

if clients:
    # Obtener nombres de columnas
    col_names = [description[0] for description in cursor.description]
    
    for client in clients:
        for i, value in enumerate(client):
            print(f"  {col_names[i]}: {value}")
        print("-" * 80)
else:
    print("❌ No se encontró el cliente")

# Buscar router VERACRUZ
cursor.execute("SELECT id, alias, host_address FROM routers WHERE UPPER(alias) LIKE '%VERACRUZ%'")
veracruz = cursor.fetchone()

if veracruz:
    print(f"\n📡 Router VERACRUZ:")
    print(f"   ID: {veracruz[0]}")
    print(f"   Alias: {veracruz[1]}")
    print(f"   Host: {veracruz[2]}")

conn.close()
