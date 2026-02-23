"""
Test script for Client Import functionality
Tests the new /discover-clients and /import-clients endpoints
"""
import requests
import json

BASE_URL = "http://localhost:5000/api/routers"

def test_discover_clients(router_id):
    """Test the discover-clients endpoint"""
    print(f"\n{'='*60}")
    print(f"Testing DISCOVER CLIENTS for Router ID: {router_id}")
    print(f"{'='*60}\n")
    
    url = f"{BASE_URL}/{router_id}/discover-clients"
    
    try:
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ SUCCESS - Clients discovered!\n")
            print(f"Router: {data.get('router_name', 'N/A')}")
            print(f"Total Clients Found: {data.get('total_clients', 0)}")
            print(f"  - Simple Queues: {data['counts'].get('simple_queues', 0)}")
            print(f"  - PPPoE Secrets: {data['counts'].get('pppoe', 0)}")
            
            # Mostrar primeros 3 de cada tipo
            if data.get('simple_queues'):
                print(f"\nPrimeras Simple Queues:")
                for i, queue in enumerate(data['simple_queues'][:3], 1):
                    print(f"  {i}. {queue.get('name')} - {queue.get('ip_address')} ({queue.get('max_limit')})")
            
            if data.get('pppoe_secrets'):
                print(f"\nPrimeros PPPoE Secrets:")
                for i, secret in enumerate(data['pppoe_secrets'][:3], 1):
                    print(f"  {i}. {secret.get('name')} - {secret.get('remote_address')} ({secret.get('rate_limit')})")
                    
            return data
        else:
            print(f"❌ ERROR {response.status_code}")
            print(response.text)
            return None
            
    except requests.exceptions.ConnectionError:
        print("❌ ERROR: No se pudo conectar al servidor. ¿Está ejecutándose 'python run.py'?")
        return None
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return None


def test_import_clients(router_id, simple_queues=[], pppoe_secrets=[]):
    """Test the import-clients endpoint"""
    print(f"\n{'='*60}")
    print(f"Testing IMPORT CLIENTS for Router ID: {router_id}")
    print(f"{'='*60}\n")
    
    url = f"{BASE_URL}/{router_id}/import-clients"
    
    payload = {
        "simple_queues": simple_queues,
        "pppoe_secrets": pppoe_secrets,
        "duplicate_strategy": "skip",
        "code_format": "auto"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ SUCCESS - Import completed!\n")
            print(f"Imported: {data.get('imported', 0)}")
            print(f"Skipped: {data.get('skipped', 0)}")
            print(f"Errors: {data.get('errors', 0)}")
            print(f"\nMessage: {data.get('message', '')}")
            
            return data
        else:
            print(f"❌ ERROR {response.status_code}")
            print(response.text)
            return None
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return None


if __name__ == "__main__":
    print("\n" + "="*60)
    print("CLIENT IMPORT FUNCTIONALITY TEST")
    print("="*60 + "\n")
    
    # PASO 1: Obtener lista de routers
    print("Obteniendo lista de routers...")
    try:
        response = requests.get(BASE_URL, timeout=10)
        if response.status_code == 200:
            routers = response.json()
            if routers:
                print(f"✅ Encontrados {len(routers)} routers\n")
                for r in routers:
                    print(f"  - ID {r['id']}: {r['alias']} ({r['host_address']}) - Status: {r['status']}")
                
                # Usar el primer router para las pruebas
                test_router_id = routers[0]['id']
                print(f"\n➡️  Usando router ID {test_router_id} para las pruebas")
                
                # PASO 2: Descubrir clientes
                discovered_data = test_discover_clients(test_router_id)
                
                if discovered_data:
                    print(f"\n{'='*60}")
                    print("NEXT STEPS:")
                    print(f"{'='*60}\n")
                    print("Para importar clientes, puedes usar:")
                    print(f"  test_import_clients({test_router_id}, simple_queues=data['simple_queues'], pppoe_secrets=data['pppoe_secrets'])")
                    print("\nO hacer una solicitud POST manualmente a:")
                    print(f"  {BASE_URL}/{test_router_id}/import-clients")
                    
            else:
                print("❌ No se encontraron routers en la base de datos")
        else:
            print(f"❌ Error obteniendo routers: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("")
        print("❌ ERROR: No se pudo conectar al servidor Flask")
        print(f"   Asegúrate de que el servidor esté corriendo en: {BASE_URL}")
        print("   Ejecuta: python run.py")
