"""
Script para configurar reglas de Firewall de corte en todos los routers online
"""
import sys
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.mikrotik.adapter import MikroTikAdapter

def setup_all_firewalls():
    print("="*80)
    print("🛡️ CONFIGURACIÓN DE FIREWALL DE CORTE (SGUB-CORTADOS)")
    print("="*80)
    print()
    
    db = get_db()
    router_repo = db.get_router_repository()
    routers = router_repo.get_all()
    
    if not routers:
        print("⚠️ No hay routers en la base de datos.")
        return

    print(f"📡 Se encontraron {len(routers)} routers en la base de datos.")
    print()
    
    for router in routers:
        print(f"⚙️ Configurando {router.alias} ({router.host_address})...")
        adapter = MikroTikAdapter()
        try:
            connected = adapter.connect(
                host=router.host_address,
                username=router.api_username,
                password=router.api_password,
                port=router.api_port,
                timeout=10
            )
            
            if connected:
                success = adapter.ensure_cutoff_firewall_rules()
                if success:
                    print(f"   ✅ Reglas configuradas exitosamente.")
                else:
                    print(f"   ❌ Fallo al aplicar algunas reglas.")
                adapter.disconnect()
            else:
                print(f"   ❌ No se pudo conectar.")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        print("-" * 40)

    print()
    print("✅ Proceso de mantenimiento finalizado.")

if __name__ == '__main__':
    setup_all_firewalls()
