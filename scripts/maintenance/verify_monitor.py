from src.infrastructure.database.db_manager import get_db
from src.infrastructure.mikrotik.adapter import MikroTikAdapter
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VerifyMonitor")

def run_check():
    db = get_db()
    routers = db.get_router_repository().get_all()
    target_router = next((r for r in routers if 'PUERTO-VIVAS' in r.alias.upper()), None)
    
    if not target_router:
        print("❌ Router no encontrado")
        return

    adapter = MikroTikAdapter()
    print(f"📡 Conectando a {target_router.alias}...")
    if not adapter.connect(target_router.host_address, target_router.api_username, target_router.api_password, target_router.api_port):
        print("❌ Falló conexión")
        return

    try:
        # 1. Active Sessions
        print("\n--- 1. BUSCANDO SESIONES ACTIVAS (/ppp/active) ---")
        active = adapter.get_active_pppoe_sessions()
        print(f"✅ Se encontraron {len(active)} sesiones activas.")
        for user, info in list(active.items())[:5]: # Mostrar 5 ejemplos
            print(f"   User: {user} | IP: {info['ip']} | Uptime: {info['uptime']}")

        if not active:
            print("⚠️ PROBABLE CAUSA: No hay sesiones activas devueltas. ¿Permisos API? ¿Nadie conectado?")
        
        # 2. Interfaces Reales
        print("\n--- 2. BUSCANDO INTERFACES REALES (/interface) ---")
        api = adapter._api_connection
        iface_res = api.get_resource('/interface')
        all_ifaces = iface_res.get(attributes='name')
        real_names = [i.get('name') for i in all_ifaces if i.get('name')]
        print(f"✅ Se encontraron {len(real_names)} interfaces totales.")
        
        # Filtrar pppoe
        pppoe_ifaces = [n for n in real_names if '<pppoe' in n]
        print(f"   De ellas, {len(pppoe_ifaces)} son dinámicas PPPoE (ej: {pppoe_ifaces[:2]})")

        # 3. Simular match
        print("\n--- 3. SIMULANDO MATCH Y TRÁFICO ---")
        users_to_check = list(active.keys())[:5] # Tomar los primeros 5 usuarios activos
        print(f"Probando tráfico para: {users_to_check}")
        
        traffic = adapter.get_bulk_traffic(users_to_check)
        print(f"\n📊 RESULTADO TRÁFICO BULK:")
        print(traffic)
        
        if not traffic:
            print("❌ El tráfico devolvió vacío. La lógica de validación o el comando fallaron.")
        else:
            print("✅ ¡El tráfico funciona en el backend!")

    except Exception as e:
        print(f"❌ Error fatal en script: {e}")
    finally:
        adapter.disconnect()

if __name__ == "__main__":
    run_check()
