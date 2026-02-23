from src.infrastructure.database.db_manager import get_db
from src.infrastructure.mikrotik.adapter import MikroTikAdapter
import logging

# Configurar log
logging.basicConfig(level=logging.INFO)

def debug_traffic():
    db = get_db()
    
    # 1. Buscar router Puerto Vivas
    routers = db.get_router_repository().get_all()
    target_router = next((r for r in routers if 'PUERTO-VIVAS' in r.alias.upper()), None)
    
    if not target_router:
        print("❌ No se encontró router Puerto Vivas")
        return

    print(f"📡 Conectando a {target_router.alias} ({target_router.host_address})...")
    
    adapter = MikroTikAdapter()
    if not adapter.connect(target_router.host_address, target_router.api_username, target_router.api_password, target_router.api_port):
        print("❌ Falló conexión")
        return
        
    try:
        # 2. Buscar interfaces que contengan "Susan"
        print("\n🔍 Buscando interfaces de 'Susan'...")
        api = adapter._api_connection
        iface_res = api.get_resource('/interface')
        
        # Obtener todas y filtrar localmente (más seguro para debug)
        all_ifaces = iface_res.get()
        susans = [i for i in all_ifaces if 'Susan' in i.get('name', '')]
        
        for s in susans:
            print(f"   found: name='{s.get('name')}' type='{s.get('type')}' id='{s.get('.id')}'")
            
            # 3. Probar monitor-traffic con el nombre exacto
            print(f"   👉 Probando monitor-traffic en '{s.get('name')}'...")
            try:
                traffic = iface_res.call('monitor-traffic', {'interface': s.get('name'), 'once': 'true'})
                print(f"      RESULTADO: {traffic}")
            except Exception as e:
                print(f"      ERROR: {e}")

            # 4. Probar con pppoe-Susan (candidato manual)
            cand = f"<pppoe-{s.get('name')}>" 
            # (Solo si el nombre no tenía ya los <>)
            if '<' not in s.get('name'):
                print(f"   👉 Probando candidato forzado '{cand}'...")
                try:
                    traffic = iface_res.call('monitor-traffic', {'interface': cand, 'once': 'true'})
                    print(f"      RESULTADO CANDIDATO: {traffic}")
                except Exception as e:
                    print(f"      ERROR CANDIDATO: {e}")

    except Exception as e:
        print(f"❌ Error general: {e}")
    finally:
        adapter.disconnect()

if __name__ == "__main__":
    debug_traffic()
