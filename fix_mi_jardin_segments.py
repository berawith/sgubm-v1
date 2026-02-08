
import sqlite3

def fix_mi_jardin_segments():
    try:
        conn = sqlite3.connect('sgubm.db')
        cursor = conn.cursor()
        
        print("🛠️ Corrigiendo segmentos para Mi Jardín...")
        
        # Eliminar el segmento anterior de prueba si existe
        cursor.execute("DELETE FROM network_segments WHERE router_id = 5 AND cidr = '172.16.50.0/24'")
        
        # Agregar los segmentos reales detectados
        segments = [
            ('MI JARDIN AIRE', '172.16.41.0/24', 5),
            ('MI JARDIN PPPoE', '10.10.10.0/24', 5)
        ]
        
        for name, cidr, rid in segments:
            # Evitar duplicados
            cursor.execute("SELECT id FROM network_segments WHERE cidr = ? AND router_id = ?", (cidr, rid))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO network_segments (name, cidr, router_id) VALUES (?, ?, ?)", (name, cidr, rid))
                print(f"✅ Agregado: {cidr}")
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    fix_mi_jardin_segments()
