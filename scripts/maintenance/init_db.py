"""
Script de Inicialización de Base de Datos CON DATOS REALES
Crea la base de datos y agrega los 5 servidores del usuario
"""
from src.infrastructure.database.models import init_db, RouterStatus, ClientStatus, PaymentStatus
from src.infrastructure.database.db_manager import get_db
from datetime import datetime, timedelta

def init_database():
    """Inicializa la base de datos con DATOS REALES"""
    
    print("🔧 Inicializando base de datos...")
    
    # Inicializar BD
    from src.infrastructure.config.settings import get_config
    config = get_config()
    engine = init_db(config.database.connection_string)
    
    print(f"✅ Base de datos creada: {config.database.connection_string}")
    
    # Obtener repositorios
    db = get_db()
    router_repo = db.get_router_repository()
    client_repo = db.get_client_repository()
    payment_repo = db.get_payment_repository()
    
    # Crear ROUTERS REALES del usuario
    print("\n📡 Creando routers REALES...")
    
    routers_data = [
        {
            'alias': 'PRINCIPAL-AYARI',
            'host_address': '12.12.12.1',
            'api_username': 'admin',
            'api_password': 'b1382285**',
            'api_port': 8738,
            'zone': 'Principal',
            'status': RouterStatus.OFFLINE,
            'notes': 'Gestión: Simple Queues y PPPoE. Rangos: 177.77.69-74.0/26'
        },
        {
            'alias': 'PRINCIPAL-PUERTO-VIVAS',
            'host_address': '12.12.12.53',
            'api_username': 'admin',
            'api_password': 'b1382285**',
            'api_port': 8728,
            'zone': 'Puerto Vivas',
            'status': RouterStatus.OFFLINE,
            'notes': 'Gestión: PPPoE. Rango: 10.25.80.0/24'
        },
        {
            'alias': 'PRINCIPAL-GUAIMARAL',
            'host_address': '12.12.12.216',
            'api_username': 'admin',
            'api_password': 'b1382285**',
            'api_port': 8728,
            'zone': 'Guaimaral',
            'status': RouterStatus.OFFLINE,
            'notes': 'Gestión: PPPoE. Rango: 172.16.10.0/24'
        },
        {
            'alias': 'PRINCIPAL-LOS-BANCOS',
            'host_address': '12.12.12.122',
            'api_username': 'admin',
            'api_password': 'b1382285**',
            'api_port': 8728,
            'zone': 'Los Bancos',
            'status': RouterStatus.OFFLINE,
            'notes': 'Gestión: PPPoE. Rango: 77.16.10.0/24'
        },
        {
            'alias': 'PRINCIPAL-MI-JARDIN',
            'host_address': '12.12.12.39',
            'api_username': 'admin',
            'api_password': 'b1382285**',
            'api_port': 8728,
            'zone': 'Mi Jardín',
            'status': RouterStatus.OFFLINE,
            'notes': 'Gestión: Simple Queues y PPPoE. Rangos: 10.10.10.0/24, 172.16.41.0/24'
        }
    ]
    
    routers = []
    for data in routers_data:
        router = router_repo.create(data)
        routers.append(router)
        print(f"  ✅ {router.alias} - {router.host_address}:{router.api_port}")
    
    print(f"\n📊 Resumen:")
    print(f"  • Routers creados: {len(routers)}")
    print(f"  • Todos configurados con credenciales reales")
    print(f"  • Estado inicial: OFFLINE (cambiar a ONLINE al sincronizar)")
    
    print(f"\n✅ Base de datos inicializada con DATOS REALES!")
    print(f"\n🚀 Próximos pasos:")
    print(f"  1. Abre http://localhost:5000")
    print(f"  2. Ve al módulo 'Routers'")
    print(f"  3. Click en 'Sincronizar' para conectar con cada router")
    print(f"  4. Importa clientes desde cada router")
    
    print(f"\n📡 Endpoints disponibles:")
    print(f"  • GET  /api/routers - Listar todos los routers")
    print(f"  • POST /api/routers/<id>/sync - Sincronizar router")
    print(f"  • POST /api/routers/sync-all - Sincronizar TODOS")
    print(f"  • POST /api/clients/import-from-router/<id> - Importar clientes")


if __name__ == '__main__':
    try:
        init_database()
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise
