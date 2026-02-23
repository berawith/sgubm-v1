
import sqlite3

def fix_segments():
    try:
        conn = sqlite3.connect('sgubm.db')
        cursor = conn.cursor()
        
        print("🛠️ Configurando segmentos faltantes...")
        
        # 1. MI JARDIN (Router 5) -> 172.16.50.0/24
        cursor.execute("INSERT INTO network_segments (name, cidr, router_id) VALUES (?, ?, ?)", 
                       ('MI JARDIN MGMT', '172.16.50.0/24', 5))
        
        # 2. LOS BANCOS (Router 4) -> 77.16.10.0/24 (PPPoE Pool)
        cursor.execute("INSERT INTO network_segments (name, cidr, router_id) VALUES (?, ?, ?)", 
                       ('LOS BANCOS PPPoE', '77.16.10.0/24', 4))
        
        conn.commit()
        conn.close()
        print("✅ Segmentos agregados exitosamente.")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    fix_segments()
