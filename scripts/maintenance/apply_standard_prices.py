
import sqlite3

def apply_standard_pricing():
    try:
        conn = sqlite3.connect('sgubm.db')
        cursor = conn.cursor()
        
        print("🚀 Aplicando estandarización de precios...")
        
        # 1. PUERTO VIVAS (ID 2) -> 70.000
        cursor.execute("UPDATE clients SET monthly_fee = 70000.0 WHERE router_id = 2")
        pviv_count = cursor.rowcount
        print(f"✅ PUERTO VIVAS: {pviv_count} clientes actualizados a $70,000")
        
        # 2. TODOS LOS DEMÁS -> 90.000 (Excluyendo ID 2)
        cursor.execute("UPDATE clients SET monthly_fee = 90000.0 WHERE router_id != 2")
        others_count = cursor.rowcount
        print(f"✅ OTROS ROUTERS: {others_count} clientes actualizados a $90,000")
        
        conn.commit()
        conn.close()
        print("\n✨ Proceso completado exitosamente.")
        
    except Exception as e:
        print(f"❌ Error al aplicar precios: {e}")

if __name__ == "__main__":
    apply_standard_pricing()
