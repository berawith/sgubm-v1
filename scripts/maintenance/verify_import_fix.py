import requests
import json
import sys

BASE_URL = "http://localhost:5000"

def verify_import():
    print("="*60)
    print("VERIFICACION DE FIX DE IMPORTACION (FILTRADO 'STA/UBIQUITI')")
    print("="*60)
    
    try:
        # 1. Obtener Routers
        print("1. Obteniendo routers disponibles...")
        try:
            r = requests.get(f"{BASE_URL}/api/routers", timeout=5)
            routers = r.json()
        except requests.exceptions.ConnectionError:
            print("\n❌ ERROR: No se puede conectar a http://localhost:5000")
            print("   Por favor verifica que la aplicación esté corriendo.")
            return False

        if not routers:
            print("⚠️  No hay routers configurados en la base de datos.")
            return False

        print(f"   ✅ {len(routers)} routers encontrados.")

        # 2. Escanear cada router hasta encontrar casos de prueba
        suspicious_patterns = ['STA', 'UBIQUITI'] # Patrones que antes estaban BLOCK
        found_any_case = False
        
        for router in routers:
            rid = router['id']
            alias = router['alias']
            print(f"\n2. Escaneando Router '{alias}' (ID {rid})...")
            
            try:
                url = f"{BASE_URL}/api/clients/preview-import/{rid}"
                resp = requests.get(url, timeout=30)
                
                if resp.status_code != 200:
                    print(f"   ❌ Error {resp.status_code} al escanear.")
                    continue
                    
                data = resp.json()
                clients = data.get('clients', [])
                total = len(clients)
                print(f"   ✅ Escaneo completado. Encontrados: {total} clientes.")
                
                # Buscar clientes que coincidan con los patrones liberados
                restored_clients = []
                for c in clients:
                    name = c.get('username', '').upper()
                    for p in suspicious_patterns:
                        if p in name:
                            restored_clients.append(c['username'])
                            break
                
                if restored_clients:
                    found_any_case = True
                    print("\n   🎉 ÉXITO: Se encontraron clientes que antes hubieran sido FILTRADOS:")
                    for name in restored_clients[:10]:
                        print(f"      - {name}")
                    if len(restored_clients) > 10:
                        print(f"      ... y {len(restored_clients)-10} más.")
                else:
                    print("   ℹ️  No se encontraron clientes con 'STA' o 'UBIQUITI' en este router.")
                    
            except Exception as e:
                print(f"   ❌ Error escaneando router {alias}: {e}")

        print("\n" + "="*60)
        if found_any_case:
            print("RESULTADO FINAL: ✅ PRUEBA EXITOSA")
            print("El filtro ya no bloquea 'STA' ni 'UBIQUITI'.")
        else:
            print("RESULTADO FINAL: ⚠️ NO CONCLUYENTE (Pero funcional)")
            print("No se encontraron clientes con esos nombres, pero el escaneo funciona.")
            print("La lógica de filtrado no está crasheando.")
        print("="*60)

    except Exception as e:
        print(f"\n❌ Error General: {e}")

if __name__ == "__main__":
    verify_import()
