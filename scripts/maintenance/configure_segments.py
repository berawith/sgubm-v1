"""
Script para configurar segmentos de red de forma fácil
Permite declarar qué rangos de IP pertenecen a cada router
"""
from src.infrastructure.database.models import NetworkSegment, init_db, get_session

def configure_network_segments():
    """Configura los segmentos de red para cada router"""
    
    print("\n" + "="*70)
    print("CONFIGURACIÓN DE SEGMENTOS DE RED")
    print("="*70 + "\n")
    
    engine = init_db('sqlite:///sgubm.db')
    session = get_session(engine)
    
    # Primero, limpiar segmentos existentes si los hay
    existing = session.query(NetworkSegment).all()
    if existing:
        print(f"⚠️  Encontrados {len(existing)} segmentos existentes. Eliminando...")
        for seg in existing:
            session.delete(seg)
        session.commit()
        print("✅ Segmentos anteriores eliminados\n")
    
    # CONFIGURACIÓN DE SEGMENTOS
    # Modifica esta sección según tus redes reales
    
    segments_to_create = [
        # Router ID 1 - PRINCIPAL (12.12.12.1)
        {
            'router_id': 1,
            'name': 'Red Clientes Fibra',
            'cidr': '177.77.69.0/26'  # IPs desde 177.77.69.0 hasta 177.77.69.63
        },
        {
            'router_id': 1,
            'name': 'Red Clientes Aire',
            'cidr': '177.77.70.0/26'  # IPs desde 177.77.70.0 hasta 177.77.70.63
        },
        {
            'router_id': 1,
            'name': 'Red Clientes 71',
            'cidr': '177.77.71.0/26'  # IPs desde 177.77.71.0 hasta 177.77.71.63
        },
        {
            'router_id': 1,
            'name': 'Red Clientes 72',
            'cidr': '177.77.72.0/26'  # IPs desde 177.77.72.0 hasta 177.77.72.63
        },
        {
            'router_id': 1,
            'name': 'Red Clientes 73',
            'cidr': '177.77.73.0/26'  # IPs desde 177.77.73.0 hasta 177.77.73.63
        },
        # Nota: 12.12.12.0/24 es probablemente red de gestión, excluida intencionalmente
        
        # Router ID 2 - PUERTO VIVAS (12.12.12.53)
        # {
        #     'router_id': 2,
        #     'name': 'Red Principal',
        #     'cidr': '10.10.10.0/24'
        # },
        
        # Router ID 3 - GUIMARAL
        {
            'router_id': 3,
            'name': 'Red PPPoE',
            'cidr': '172.16.10.0/24'
        },
        {
            'router_id': 3,
            'name': 'Red Clientes SimpleQueue',
            'cidr': '192.168.17.0/24'
        },
        
        # Agrega más segmentos según necesites
    ]
    
    print("Creando segmentos de red:\n")
    
    for seg_data in segments_to_create:
        segment = NetworkSegment(
            router_id=seg_data['router_id'],
            name=seg_data['name'],
            cidr=seg_data['cidr']
        )
        session.add(segment)
        print(f"✅ Router ID {seg_data['router_id']}: {seg_data['name']} ({seg_data['cidr']})")
    
    session.commit()
    
    print(f"\n✅ {len(segments_to_create)} segmentos configurados exitosamente\n")
    
    # Verificar
    print("="*70)
    print("VERIFICACIÓN")
    print("="*70 + "\n")
    
    all_segments = session.query(NetworkSegment).all()
    by_router = {}
    for seg in all_segments:
        if seg.router_id not in by_router:
            by_router[seg.router_id] = []
        by_router[seg.router_id].append(seg)
    
    for router_id, segs in sorted(by_router.items()):
        print(f"📡 Router ID {router_id}:")
        for seg in segs:
            print(f"   - {seg.name}: {seg.cidr}")
        print()
    
    session.close()
    
    print("="*70)
    print("CONFIGURACIÓN COMPLETADA")
    print("="*70)
    print("\nAhora puedes:")
    print("1. Escanear clientes desde la UI")
    print("2. Verificar el filtrado con: python verify_filtering.py")
    print("3. Solo verás clientes con IPs en los rangos configurados")
    print()


if __name__ == "__main__":
    configure_network_segments()
