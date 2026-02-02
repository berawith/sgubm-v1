from src.infrastructure.database.db_manager import get_db
from src.infrastructure.mikrotik.adapter import MikroTikAdapter
import logging
import time

logging.basicConfig(level=logging.INFO)

def run_check():
    print("🚀 Iniciando diagnóstico...")
    db = get_db()
    routers = db.get_router_repository().get_all()
    target_router = next((r for r in routers if 'PUERTO-VIVAS' in r.alias.upper()), None)
    
    if not target_router:
        print("❌ Router no encontrado")
        return

    adapter = MikroTikAdapter()
    print(f"📡 Conectando a {target_router.alias}...")
    conn = adapter.connect(target_router.host_address, target_router.api_username, target_router.api_password, target_router.api_port)
    if not conn:
        print("❌ Falló conexión")
        return

    try:
        api = adapter._api_connection
        
        # 1. Obtener Interfaces (Test de velocidad y cantidad)
        print("\n--- TEST: Obtener TODAS las interfaces ---")
        start = time.time()
        # Intentamos obtener solo nombres si la librería lo soporta, sino todo
        # routeros_api no soporta 'attributes' en get(), trae todo el objeto.
        all_ifaces = api.get_resource('/interface').get() 
        duration = time.time() - start
        
        print(f"✅ Descargadas {len(all_ifaces)} interfaces en {duration:.2f}s")
        
        if len(all_ifaces) == 0:
            print("❌ CERO interfaces encontradas. Algo está mal.")
            return

        names = [i.get('name') for i in all_ifaces]
        pppoe_count = sum(1 for n in names if '<pppoe' in n)
        print(f"   Dynamic PPPoE count: {pppoe_count}")
        print(f"   Sample names: {names[:5]}")

        # 2. Active Sessions
        print("\n--- TEST: Active Sessions ---")
        active = adapter.get_active_pppoe_sessions()
        active_users = list(active.keys())
        print(f"✅ {len(active_users)} usuarios activos: {active_users[:5]}")

        # 3. Match Manual
        print("\n--- TEST: Matching ---")
        matched = []
        for user in active_users[:5]:
            c1 = user
            c2 = f"<pppoe-{user}>"
            if c1 in names:
                print(f"   ✅ Match directo: {user} -> {c1}")
                matched.append(c1)
            elif c2 in names:
                print(f"   ✅ Match dinámico: {user} -> {c2}")
                matched.append(c2)
            else:
                print(f"   ❌ NO ENCONTRADO INTERFAZ PARA: {user} (Probado: {c1}, {c2})")

        if matched:
            print(f"\n--- TEST: Monitor Traffic en {len(matched)} interfaces ---")
            iface_str = ",".join(matched)
            print(f"   Query: {iface_str}")
            res = api.get_resource('/interface').call('monitor-traffic', {'interface': iface_str, 'once': 'true'})
            print(f"✅ Traffic response items: {len(res)}")
            print(res[0])
        else:
            print("⚠️ No hay interfaces para probar tráfico.")

    except Exception as e:
        print(f"\n❌ EXCEPCIÓN: {e}")
        import traceback
        traceback.print_exc()
    finally:
        adapter.disconnect()

if __name__ == "__main__":
    run_check()
