import logging
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.mikrotik.adapter import MikroTikAdapter
from run import create_app

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def ensure_basic_plans():
    """
    Recorre todos los routers y asegura que exista el plan básico de 15Mbps
    """
    app = create_app()
    with app.app_context():
        db = get_db()
        router_repo = db.get_router_repository()
        routers = router_repo.get_all()
        
        PLAN_NAME = "Plan_Basico_15M"
        RATE_LIMIT = "15M/15M"
        
        print(f"\n🚀 Iniciando provisión de planes básicos ({PLAN_NAME} - {RATE_LIMIT})...")
        print("-" * 60)
        
        for router in routers:
            print(f"📡 Verificando Router: {router.alias} ({router.host_address})...")
            
            if router.status != 'online':
                print(f"   ⚠️ Router offline o estado desconocido. Saltando...")
                continue
                
            adapter = MikroTikAdapter()
            try:
                # Conectar con timeout corto
                if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port, timeout=5):
                    # Crear/Actualizar Perfil
                    success = adapter.create_ppp_profile(PLAN_NAME, RATE_LIMIT)
                    
                    if success:
                        print(f"   ✅ Perfil '{PLAN_NAME}' asegurado correctamente.")
                    else:
                        print(f"   ❌ Fallo al crear/actualizar perfil.")
                    
                    adapter.disconnect()
                else:
                    print(f"   ❌ No se pudo conectar al router.")
            except Exception as e:
                print(f"   ❌ Error de conexión: {e}")
            
            print("-" * 60)
            
        print("\n✅ Proceso completado.")

if __name__ == "__main__":
    ensure_basic_plans()
