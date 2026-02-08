"""
Script para verificar el filtrado correcto de segmentos de red
Comprueba que el endpoint filtre solo por segmentos del router específico
"""
import requests
import json
from src.infrastructure.database.models import NetworkSegment, init_db, get_session

BASE_URL = "http://localhost:5000"

def check_segments_configuration():
    """Verifica qué segmentos hay configurados en la BD"""
    print("\n" + "="*70)
    print("CONFIGURACIÓN DE SEGMENTOS DE RED EN LA BASE DE DATOS")
    print("="*70 + "\n")
    
    engine = init_db('sqlite:///sgubm.db')
    session = get_session(engine)
    
    segments = session.query(NetworkSegment).all()
    
    if not segments:
        print("⚠️  NO HAY SEGMENTOS DE RED CONFIGURADOS")
        print("\nSin segmentos configurados, el sistema mostrará TODOS los clientes.")
        print("Para configurar segmentos, ejecuta:")
        print("\n  python configure_segments.py")
        return False
    
    # Agrupar por router
    by_router = {}
    for seg in segments:
        if seg.router_id not in by_router:
            by_router[seg.router_id] = []
        by_router[seg.router_id].append(seg)
    
    print(f"Total de segmentos configurados: {len(segments)}\n")
    
    for router_id, segs in by_router.items():
        print(f"📡 Router ID {router_id}:")
        for seg in segs:
            print(f"   - {seg.name}: {seg.cidr}")
        print()
    
    session.close()
    return True


def test_discovery_filtering(router_id):
    """Prueba el endpoint de discovery con filtrado"""
    print("\n" + "="*70)
    print(f"PROBANDO DESCUBRIMIENTO DE CLIENTES - ROUTER ID {router_id}")
    print("="*70 + "\n")
    
    url = f"{BASE_URL}/api/clients/preview-import/{router_id}"
    
    try:
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            print("✅ DESCUBRIMIENTO EXITOSO\n")
            print(f"Router: {data.get('router_alias', 'N/A')}")
            print(f"Total clientes encontrados: {data.get('total_found', 0)}")
            print(f"Filtro de segmentos activo: {'Sí' if data.get('segments_filter_active') else 'No'}")
            
            if data.get('clients'):
                print(f"\nPrimeros 5 clientes filtrados:")
                for i, client in enumerate(data['clients'][:5], 1):
                    print(f"  {i}. {client['username']} - {client['ip_address']} ({client['type']})")
                
                # Verificar que las IPs estén en los segmentos correctos
                print("\n" + "="*70)
                print("VERIFICACIÓN DE FILTRADO")
                print("="*70 + "\n")
                
                # Obtener segmentos de este router
                engine = init_db('sqlite:///sgubm.db')
                session = get_session(engine)
                segments = session.query(NetworkSegment).filter(NetworkSegment.router_id == router_id).all()
                
                if segments:
                    print(f"Segmentos configurados para este router:")
                    for seg in segments:
                        print(f"  - {seg.cidr}")
                    
                    # Verificar algunas IPs
                    from ipaddress import ip_address, ip_network
                    allowed_networks = [ip_network(s.cidr, strict=False) for s in segments]
                    
                    print(f"\nVerificando IPs de los primeros 10 clientes:")
                    for client in data['clients'][:10]:
                        ip = client['ip_address']
                        if ip and ip != 'Dinámica':
                            clean_ip = ip.split('/')[0]
                            try:
                                addr = ip_address(clean_ip)
                                is_in_segment = any(addr in net for net in allowed_networks)
                                status = "✅" if is_in_segment else "❌"
                                print(f"  {status} {client['username']}: {clean_ip}")
                            except:
                                print(f"  ⚠️  {client['username']}: {clean_ip} (IP inválida)")
                else:
                    print("⚠️  No hay segmentos configurados para este router")
                    print("   Todos los clientes encontrados se mostrarán sin filtrar")
                
                session.close()
            else:
                print("\n⚠️  No se encontraron clientes (puede ser que todos fueron filtrados)")
            
            return True
        else:
            print(f"❌ ERROR {response.status_code}")
            print(f"Respuesta: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ ERROR: No se pudo conectar al servidor")
        print("   Asegúrate de que el servidor esté corriendo: python run.py")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


if __name__ == "__main__":
    print("\n" + "="*70)
    print("VERIFICACIÓN DEL SISTEMA DE FILTRADO POR SEGMENTOS DE RED")
    print("="*70)
    
    # Paso 1: Verificar configuración
    has_segments = check_segments_configuration()
    
    # Paso 2: Obtener routers
    try:
        response = requests.get(f"{BASE_URL}/api/routers", timeout=10)
        if response.status_code == 200:
            routers = response.json()
            if routers:
                print("\n" + "="*70)
                print("ROUTERS DISPONIBLES")
                print("="*70 + "\n")
                for r in routers[:3]:  # Primeros 3
                    print(f"  - ID {r['id']}: {r['alias']} ({r['host_address']})")
                
                # Probar con el primer router
                test_router_id = routers[0]['id']
                test_discovery_filtering(test_router_id)
            else:
                print("\n❌ No hay routers configurados")
        else:
            print(f"\n❌ Error obteniendo routers: {response.status_code}")
    except:
        print("\n❌ Error conectando al servidor")
    
    print("\n" + "="*70)
    print("FIN DE LA VERIFICACIÓN")
    print("="*70 + "\n")
