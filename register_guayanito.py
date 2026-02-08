
import sqlite3
import sys

def register_guayanito():
    try:
        conn = sqlite3.connect('sgubm.db')
        cursor = conn.cursor()
        
        # 1. Registrar el Router
        router_data = {
            'alias': 'GUAYANITO',
            'host_address': '12.12.12.72',
            'api_username': 'admin',
            'api_password': 'b1382285**',
            'api_port': 8728,
            'ssh_port': 22,
            'zone': 'GUAYANITO',
            'status': 'offline',
            'notes': 'Gestiona por DHCP + ARP + Simple Queues'
        }
        
        # Verificar si ya existe
        cursor.execute("SELECT id FROM routers WHERE host_address = ?", (router_data['host_address'],))
        existing = cursor.fetchone()
        
        if existing:
            router_id = existing[0]
            print(f"ℹ️ El router GUAYANITO ({router_data['host_address']}) ya existe con ID: {router_id}. Actualizando...")
            cursor.execute("""
                UPDATE routers 
                SET alias = ?, api_username = ?, api_password = ?, api_port = ?, ssh_port = ?, zone = ?, notes = ?
                WHERE id = ?
            """, (router_data['alias'], router_data['api_username'], router_data['api_password'], 
                  router_data['api_port'], router_data['ssh_port'], router_data['zone'], 
                  router_data['notes'], router_id))
        else:
            cursor.execute("""
                INSERT INTO routers (alias, host_address, api_username, api_password, api_port, ssh_port, zone, status, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (router_data['alias'], router_data['host_address'], router_data['api_username'], 
                  router_data['api_password'], router_data['api_port'], router_data['ssh_port'], 
                  router_data['zone'], router_data['status'], router_data['notes']))
            router_id = cursor.lastrowid
            print(f"✅ Router GUAYANITO creado exitosamente con ID: {router_id}")

        # 2. Agregar el Segmento de Red (IP de gestión interna)
        cidr = '172.16.47.0/24'
        segment_name = 'Gestión Interna GUAYANITO'
        
        cursor.execute("SELECT id FROM network_segments WHERE router_id = ? AND cidr = ?", (router_id, cidr))
        if cursor.fetchone():
            print(f"ℹ️ El segmento {cidr} ya existe para este router.")
        else:
            cursor.execute("INSERT INTO network_segments (router_id, name, cidr) VALUES (?, ?, ?)", 
                         (router_id, segment_name, cidr))
            print(f"✅ Segmento {cidr} ({segment_name}) agregado exitosamente.")

        conn.commit()
        conn.close()
        print("\nRegistro completado.")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    register_guayanito()
