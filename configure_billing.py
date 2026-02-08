
import sqlite3

def configure_billing_system():
    try:
        conn = sqlite3.connect('sgubm.db')
        cursor = conn.cursor()
        
        print("🚀 Configurando sistema de facturación y zonas...")
        
        # 1. Definir Fechas de Corte y Pago (Estándar)
        # billing_day=1 (Generación), grace_period=5 (Días de gracia), cut_day=10 (Corte)
        cursor.execute("""
            UPDATE routers 
            SET billing_day = 1, grace_period = 5, cut_day = 10
        """)
        print(f"✅ Fechas de cobro estandarizadas en todos los routers (1-5-10).")
        
        # 2. Configurar Zonas según el Router
        zones = {
            1: 'AYARI',
            2: 'PUERTO VIVAS',
            3: 'GUAIMARAL',
            4: 'LOS BANCOS',
            5: 'MI JARDIN',
            6: 'GUAYANITO'
        }
        
        for r_id, zone_name in zones.items():
            cursor.execute("UPDATE routers SET zone = ? WHERE id = ?", (zone_name, r_id))
            print(f"   📍 Zona establecida para Router {r_id}: {zone_name}")
            
            # 3. Asegurar que los clientes de esta zona tengan el precio correcto
            price = 70000.0 if r_id == 2 else 90000.0
            cursor.execute("UPDATE clients SET monthly_fee = ? WHERE router_id = ?", (price, r_id))
            print(f"   💰 Precios de clientes verificados para {zone_name}: ${price:,.0f}")

        conn.commit()
        conn.close()
        print("\n✨ Configuración de infraestructura completada.")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    configure_billing_system()
