import sys
import os
import logging
from run import create_app
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.mikrotik.adapter import MikroTikAdapter

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('RouterDetail')

def main():
    target_ip = "12.12.12.1"
    
    app = create_app()
    with app.app_context():
        db = get_db()
        router_repo = db.get_router_repository()
        all_routers = router_repo.get_all()
        
        target_router = None
        for r in all_routers:
            if r.host_address == target_ip:
                target_router = r
                break
        
        if not target_router:
            print(f"❌ Error: No se encontró ningún router con IP {target_ip} en la base de datos.")
            print("Routers disponibles:")
            for r in all_routers:
                print(f" - {r.alias}: {r.host_address}")
            return

        print(f"✅ Router encontrado: {target_router.alias} ({target_router.host_address})")
        
        # 1. Clientes en Base de Datos
        client_repo = db.get_client_repository()
        db_clients = client_repo.get_by_router(target_router.id)
        total_db = len(db_clients)
        print(f"\n📊 Estadísticas de Base de Datos:")
        print(f"   • Total Clientes Registrados: {total_db}")
        
        # 2. Análisis en Tiempo Real (MikroTik)
        print(f"\n🔌 Conectando al router para análisis en vivo...")
        adapter = MikroTikAdapter()
        if adapter.connect(target_router.host_address, target_router.api_username, target_router.api_password, target_router.api_port):
            
            # A. Obtener IPs Activas (Online)
            # - Active PPP
            active_ppp = adapter.get_ppp_active_ips()
            # - Bound DHCP Leases
            dhcp_leases = adapter.get_dhcp_leases() 
            bound_ips = {l['address'] for l in dhcp_leases if l.get('address')}
            # - Valid ARP Entries (Para clientes con IP estática manual)
            arp_table = adapter.get_arp_table()
            arp_ips = {entry.get('address') for entry in arp_table if entry.get('address')}
            
            # Conjunto total de IPs Online (desde el punto de vista del router)
            # Online = PPP OR DHCP Bound OR ARP Valid
            router_online_ips = active_ppp.union(bound_ips).union(arp_ips)
            
            # B. Cruzar con Clientes DB
            count_online = 0
            count_offline = 0
            offline_list = []
            
            for client in db_clients:
                # Normalizar IP (quitar espacios, cidr)
                cip = client.ip_address.split('/')[0].strip() if client.ip_address else None
                
                if cip and cip in router_online_ips:
                    count_online += 1
                else:
                    count_offline += 1
                    offline_list.append(client)

            # C. Obtener Waiting/Failed (usando helper methods nuevos)
            waiting_leases = adapter.get_waiting_leases()
            failed_arp = adapter.get_failed_arp_ips()
            
            # --- ANÁLISIS DETALLADO DE WAITING/FAILED ---
            # Separar "Waiting" en: Registrados (Clientes Offline) vs Desconocidos (Intrusos)
            
            waiting_registered = []
            waiting_unknown = []
            
            failed_registered = []
            failed_unknown = []
            
            # Mapa de IPs registradas para búsqueda rápida
            registered_ips_map = {c.ip_address.split('/')[0].strip(): c for c in db_clients if c.ip_address}
            
            # Clasificar Waiting
            for lease in waiting_leases:
                ip = lease.get('address')
                if ip in registered_ips_map:
                    client = registered_ips_map[ip]
                    waiting_registered.append(f"{ip} ({client.username})")
                else:
                    waiting_unknown.append(ip)
            
            # Clasificar Failed ARP
            for ip in failed_arp:
                if ip in registered_ips_map:
                    client = registered_ips_map[ip]
                    failed_registered.append(f"{ip} ({client.username})")
                else:
                    failed_unknown.append(ip)

            print(f"\n🕵️ ANÁLISIS DE WAITING & FAILED:")
            print(f"   • Total Waiting en Router: {len(waiting_leases)}")
            print(f"     ✅ Registrados (Clientes Offline): {len(waiting_registered)}")
            print(f"     ❓ Desconocidos (Intrusos/Otros): {len(waiting_unknown)}")
            
            print(f"   • Total Failed ARP en Router: {len(failed_arp)}")
            print(f"     ✅ Registrados (Clientes Offline): {len(failed_registered)}")
            print(f"     ❓ Desconocidos (Intrusos/Otros): {len(failed_unknown)}")

            if waiting_registered:
                print("\n   ⚠️ Clientes Registrados en WAITING (Intentando conectar):")
                for item in waiting_registered[:10]: # Mostrar primeros 10
                    print(f"      - {item}")
                if len(waiting_registered) > 10: print(f"      ... y {len(waiting_registered)-10} más.")

            # D. Recalcular Offline Total REAL
            # Offline Real = (Registrados en Waiting) + (Registrados en Failed) + (Registrados sin rastro)
            # Ya tenemos count_offline calculado arriba (que es Total Registrados - Online Registrados)
            # Vamos a desglosar ese count_offline correctamente.
            
            registrados_sin_rastro = count_offline - len(waiting_registered) - len(failed_registered)
            # Ajuste por si las listas se solapan (raro pero posible) o si count_offline difiere ligeramente por el ARP check
            # Mejor confiamos en la clasificación directa:
            
            print(f"\n📉 RESUMEN FINAL DE TUS CLIENTES ({total_db} Total):")
            print(f"   🟢 ONLINE: {count_online}")
            print(f"   🔴 OFFLINE: {count_offline}")
            print(f"      ↳ Waiting (Intentando): {len(waiting_registered)}")
            print(f"      ↳ Failed (Error ARP):  {len(failed_registered)}")
            print(f"      ↳ Apagados (Sin rastro): {max(0, registrados_sin_rastro)}")

            
            # Info extra del router
            print(f"\n🤖 Info Router Global:")
            print(f"   • Total Active PPP Sessions: {len(active_ppp)}")
            print(f"   • Total DHCP Bound: {len(bound_ips)}")
            print(f"   • Total DHCP Waiting: {len(waiting_leases)}")
            
            adapter.disconnect()
        else:
            print("\n❌ No se pudo conectar al router para análisis en vivo.")

if __name__ == "__main__":
    main()
