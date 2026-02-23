import sqlite3

# Connect to database
conn = sqlite3.connect('sgubm.db')
cursor = conn.cursor()

# Query all routers with their status
result = cursor.execute('''
    SELECT id, alias, host_address, api_port, status, last_error 
    FROM routers 
    ORDER BY id
''').fetchall()

print("=" * 80)
print("ESTADO DE TODOS LOS ROUTERS")
print("=" * 80)
for r in result:
    print(f"\n🔧 Router ID: {r[0]}")
    print(f"   Alias: {r[1]}")
    print(f"   Host: {r[2]}:{r[3]}")
    print(f"   Estado: {r[4]}")
    if r[5]:
        print(f"   Último Error: {r[5]}")

print("\n" + "=" * 80)

# Count by status
status_counts = cursor.execute('''
    SELECT status, COUNT(*) 
    FROM routers 
    GROUP BY status
''').fetchall()

print("\nRESUMEN:")
for status, count in status_counts:
    print(f"  {status}: {count} router(s)")

conn.close()
