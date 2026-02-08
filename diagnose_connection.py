import logging
import socket
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.mikrotik.adapter import MikroTikAdapter

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_router_connection(target_alias_fragment):
    print(f"\n🔍 Buscando router que contenga: '{target_alias_fragment}'")
    db = get_db()
    repo = db.get_router_repository()
    routers = repo.get_all()
    
    target = next((r for r in routers if target_alias_fragment.upper() in r.alias.upper()), None)
    
    if not target:
        print("❌ Router no encontrado en BD.")
        return

    print(f"🎯 Router encontrado: {target.alias} ({target.host_address})")
    print(f"   User: {target.api_username}")
    print(f"   Port: {target.api_port}")
    
    adapter = MikroTikAdapter()
    
    print("\n📡 Iniciando prueba de conexión (single thread)...")
    try:
        # Probamos conexión con el wrapper
        start_timeout = socket.getdefaulttimeout()
        print(f"   Timeout global inicial: {start_timeout}")
        
        success = adapter.connect(
            target.host_address, 
            target.api_username, 
            target.api_password, 
            target.api_port,
            timeout=10
        )
        
        if success:
            print("✅ ¡CONEXIÓN EXITOSA!")
            try:
                # Intentar leer recursos básicos
                sys_res = adapter._api_connection.get_resource('/system/resource').get()
                print(f"   System Resource: {sys_res[0] if sys_res else 'Empty'}")
                print("   Disconnecting...")
                adapter.disconnect()
            except Exception as e:
                print(f"⚠️ Conectó pero falló al leer data: {e}")
        else:
            print("❌ La conexión retornó False (sin excepción, pero falló).")

    except Exception as e:
        print(f"❌ EXCEPCIÓN AL CONECTAR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_router_connection("GUIMARAL")
    test_router_connection("LOS BANCOS")
