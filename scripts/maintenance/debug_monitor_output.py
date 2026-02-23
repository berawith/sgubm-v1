from src.infrastructure.database.db_manager import get_db
from src.infrastructure.mikrotik.adapter import MikroTikAdapter
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_uptime_stream(target_alias_fragment, iterations=5):
    print(f"\n🔍 Buscando router que contenga: '{target_alias_fragment}'")
    db = get_db()
    repo = db.get_router_repository()
    routers = repo.get_all()
    
    target = next((r for r in routers if target_alias_fragment.upper() in r.alias.upper()), None)
    
    if not target:
        print("❌ Router no encontrado en BD.")
        return

    print(f"🎯 Router encontrado: {target.alias} ({target.host_address})")
    
    adapter = MikroTikAdapter()
    
    if not adapter.connect(target.host_address, target.api_username, target.api_password, target.api_port, timeout=10):
        print("❌ No se pudo conectar.")
        return
        
    print(f"\n⏱️ Leyendo Uptime {iterations} veces (intervalo 1s)...")
    try:
        for i in range(iterations):
            sys_res = adapter._api_connection.get_resource('/system/resource').get()
            if sys_res:
                raw_uptime = sys_res[0].get('uptime', 'N/A')
                print(f"   [{i+1}/{iterations}] Raw Uptime: '{raw_uptime}'")
            else:
                print(f"   [{i+1}/{iterations}] Error: Respuesta vacía")
            time.sleep(1)
            
    except Exception as e:
        print(f"❌ Excepción: {e}")
    finally:
        adapter.disconnect()

if __name__ == "__main__":
    test_uptime_stream("PRINCIPAL", iterations=5)
