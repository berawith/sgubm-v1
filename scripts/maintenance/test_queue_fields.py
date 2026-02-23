"""
Script de prueba para ver qué campos devuelve Simple Queues
"""
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.mikrotik.adapter import MikroTikAdapter

db = get_db()
router_repo = db.get_router_repository()

# Obtener router ID 1
router = router_repo.get_by_id(1)

if not router:
    print("❌ Router no encontrado")
    exit(1)

adapter = MikroTikAdapter()

try:
    connected = adapter.connect(
        host=router.host_address,
        username=router.api_username,
        password=router.api_password,
        port=router.api_port,
        timeout=5
    )
    
    if not connected:
        print("❌ No se pudo conectar al router")
        exit(1)
    
    print(f"✅ Conectado al router {router.alias} ({router.host_address})\n")
    
    # Obtener Simple Queues
    queues = adapter._api_connection.get_resource('/queue/simple').get()
    
    if not queues:
        print("❌ No hay queues en el router")
        exit(1)
    
    # Mostrar los primeros 3 clientes
    print(f"Total Simple Queues: {len(queues)}\n")
    print("="*80)
    
    for i, queue in enumerate(queues[:3]):
        print(f"\n🔹 Queue #{i+1}: {queue.get('name', 'SIN NOMBRE')}")
        print("-" * 80)
        
        # Mostrar TODOS los campos
        for key, value in sorted(queue.items()):
            print(f"  {key:25} = {value}")
        
        print("="*80)
    
    adapter.disconnect()
    print("\n✅ Desconectado")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
