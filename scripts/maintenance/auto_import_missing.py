
import requests
import json
import time

def auto_import_routers(router_ids):
    base_url = "http://127.0.0.1:5000/api/routers"
    
    for rid in router_ids:
        print(f"\n🔍 Procesando Router ID: {rid}")
        
        # 1. Discover
        try:
            disc_resp = requests.get(f"{base_url}/{rid}/discover-clients")
            if disc_resp.status_code != 200:
                print(f"❌ Error en discovery para {rid}: {disc_resp.text}")
                continue
                
            data = disc_resp.json()
            sq = data.get('simple_queues', [])
            ppp = data.get('pppoe_secrets', [])
            
            print(f"   ✅ Candidatos encontrados: {len(sq)} Simple Queues, {len(ppp)} PPPoE Secrets")
            
            if not sq and not ppp:
                print("   ⚠️ No hay candidatos nuevos para importar.")
                continue
                
            # 2. Import
            import_payload = {
                'simple_queues': sq,
                'pppoe_secrets': ppp,
                'strategy': 'skip' # No queremos sobreescribir los ya configurados manualmente si los hay
            }
            
            imp_resp = requests.post(f"{base_url}/{rid}/import-clients", json=import_payload)
            if imp_resp.status_code == 200:
                result = imp_resp.json()
                print(f"   ✨ Importación Exitosa: {result.get('imported')} nuevos, {result.get('skipped')} omitidos, {result.get('errors')} errores")
            else:
                print(f"   ❌ Error en importación para {rid}: {imp_resp.text}")
                
        except Exception as e:
            print(f"   ❌ Error de conexión: {e}")

if __name__ == "__main__":
    # Router 4: LOS BANCOS
    # Router 6: GUAYANITO
    # Router 5: MI JARDIN (para buscar faltantes)
    auto_import_routers([4, 6, 5])
