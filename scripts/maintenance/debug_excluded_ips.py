"""
Script de debugging para analizar qué clientes están siendo excluidos por el filtro
Muestra las IPs de los clientes excluidos para identificar qué segmentos faltan
"""
import requests
from collections import defaultdict
from ipaddress import ip_address, ip_network

BASE_URL = "http://localhost:5000"

def analyze_excluded_clients(router_id):
    """Analiza qué clientes están siendo excluidos y por qué"""
    
    print("\n" + "="*80)
    print("ANÁLISIS DE CLIENTES EXCLUIDOS POR EL FILTRO")
    print("="*80 + "\n")
    
    # Obtener datos del router directamente (sin filtro de segmentos)
    from src.infrastructure.database.models import NetworkSegment, init_db, get_session
    from src.infrastructure.mikrotik.adapter import MikroTikAdapter
    from src.infrastructure.database.db_manager import get_db
    
    db = get_db()
    router_repo = db.get_router_repository()
    router = router_repo.get_by_id(router_id)
    
    if not router:
        print(f"❌ Router {router_id} no encontrado")
        return
    
    print(f"📡 Router: {router.alias} ({router.host_address})\n")
    
    # Obtener segmentos configurados
    engine = init_db('sqlite:///sgubm.db')
    session = get_session(engine)
    segments = session.query(NetworkSegment).filter(NetworkSegment.router_id == router_id).all()
    
    print(f"Segmentos configurados ({len(segments)}):")
    for seg in segments:
        print(f"  ✅ {seg.cidr} - {seg.name}")
    print()
    
    allowed_networks = [ip_network(s.cidr, strict=False) for s in segments]
    
    def is_ip_allowed(ip_str):
        if not ip_str or ip_str == '0.0.0.0':
            return True  # IPs dinámicas
        clean_ip = ip_str.split('/')[0]
        try:
            addr = ip_address(clean_ip)
            return any(addr in net for net in allowed_networks)
        except:
            return False
    
    # Conectar al router y obtener ALL Simple Queues
    adapter = MikroTikAdapter()
    
    try:
        connected = adapter.connect(
            host=router.host_address,
            username=router.api_username,
            password=router.api_password,
            port=router.api_port,
            timeout=10
        )
        
        if not connected:
            print("❌ No se pudo conectar al router")
            return
        
        print("Obteniendo Simple Queues del router...\n")
        all_queues = adapter.get_all_simple_queues()
        
        print(f"Total Simple Queues encontradas: {len(all_queues)}\n")
        
        # Separar en incluidas y excluidas
        included = []
        excluded = []
        
        for queue in all_queues:
            ip = queue.get('ip_address', '')
            if is_ip_allowed(ip):
                included.append(queue)
            else:
                excluded.append(queue)
        
        print(f"✅ INCLUIDAS (pasan el filtro): {len(included)}")
        print(f"❌ EXCLUIDAS (filtradas): {len(excluded)}\n")
        
        if excluded:
            print("="*80)
            print("CLIENTES EXCLUIDOS - Análisis de IPs")
            print("="*80 + "\n")
            
            # Agrupar por rango de red
            ip_groups = defaultdict(list)
            
            for queue in excluded:
                ip = queue.get('ip_address', '')
                if not ip or ip == '0.0.0.0':
                    continue
                
                clean_ip = ip.split('/')[0]
                # Obtener los primeros 3 octetos (red /24)
                parts = clean_ip.split('.')
                if len(parts) == 4:
                    network_prefix = f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
                    ip_groups[network_prefix].append({
                        'name': queue.get('name'),
                        'ip': clean_ip,
                        'speed': queue.get('max_limit', '')
                    })
            
            # Mostrar resumen por red
            print("Clientes excluidos agrupados por red:\n")
            
            sorted_networks = sorted(ip_groups.items(), key=lambda x: len(x[1]), reverse=True)
            
            for network, clients in sorted_networks:
                print(f"📍 Red {network}: {len(clients)} clientes")
                # Mostrar primeros 5 como ejemplo
                for client in clients[:5]:
                    print(f"   - {client['name']}: {client['ip']} ({client['speed']})")
                if len(clients) > 5:
                    print(f"   ... y {len(clients) - 5} más")
                print()
            
            # Sugerencias de segmentos a agregar
            print("="*80)
            print("💡 SUGERENCIAS DE SEGMENTOS A AGREGAR")
            print("="*80 + "\n")
            
            print("Para incluir todos estos clientes, agrega estos segmentos en configure_segments.py:\n")
            
            for network, clients in sorted_networks:
                print(f"    {{'router_id': {router_id}, 'name': 'Red Clientes {network.split('.')[2]}', 'cidr': '{network}'}},")
            
            print()
        
        adapter.disconnect()
        session.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Analizar router ID 1
    analyze_excluded_clients(1)
