
import sqlite3
from datetime import datetime

def initialize_debt():
    try:
        conn = sqlite3.connect('sgubm.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        print("🔧 INICIALIZANDO DEUDA PARA CLIENTES NUEVOS")
        print("="*60)
        
        # 1. Identificar clientes activos con balance 0
        cursor.execute("""
            SELECT id, legal_name, monthly_fee, router_id 
            FROM clients 
            WHERE status = 'active' AND (account_balance = 0 OR account_balance IS NULL)
        """)
        clients = cursor.fetchall()
        
        if not clients:
            print("✅ No se encontraron clientes activos con balance $0.")
            conn.close()
            return

        print(f"📦 Encontrados {len(clients)} clientes para inicializar.")
        
        updated_count = 0
        total_added_debt = 0
        
        for client in clients:
            fee = client['monthly_fee'] or 0
            if fee > 0:
                cursor.execute("""
                    UPDATE clients 
                    SET account_balance = ? 
                    WHERE id = ?
                """, (fee, client['id']))
                updated_count += 1
                total_added_debt += fee
        
        conn.commit()
        print(f"✅ Se han inicializado {updated_count} clientes.")
        print(f"💰 Deuda total cargada: ${total_added_debt:,.0f}")
        print("="*60)
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error en la inicialización: {e}")

if __name__ == "__main__":
    initialize_debt()
