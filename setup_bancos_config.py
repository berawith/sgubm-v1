
import sqlite3
import sys

def setup_bancos_segment():
    try:
        conn = sqlite3.connect('sgubm.db')
        cursor = conn.cursor()
        
        # 1. Verificar si el router existe por IP
        cursor.execute("SELECT id, alias FROM routers WHERE host_address = '12.12.12.122' OR alias LIKE '%BANCOS%'")
        router = cursor.fetchone()
        
        if not router:
            print("❌ Error: Router 12.12.12.122 (BANCOS) no encontrado en la base de datos.")
            return

        router_id = router[0]
        alias = router[1]
        print(f"✅ Encontrado Router ID {router_id}: {alias}")

        # 2. Agregar el segmento de red
        cidr = '77.16.10.0/24'
        name = 'BANCOS SERVIDOR'
        
        # Evitar duplicados
        cursor.execute("SELECT id FROM network_segments WHERE router_id = ? AND cidr = ?", (router_id, cidr))
        if cursor.fetchone():
            print(f"ℹ️ El segmento {cidr} ya existe para este router.")
        else:
            cursor.execute("INSERT INTO network_segments (router_id, name, cidr) VALUES (?, ?, ?)", 
                         (router_id, name, cidr))
            print(f"✅ Segmento {cidr} ({name}) agregado exitosamente.")

        conn.commit()
        conn.close()
        print("Done.")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    setup_bancos_segment()
