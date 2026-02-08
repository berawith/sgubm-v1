
import os
import sys
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Añadir el path del proyecto para importar modelos
sys.path.append(os.getcwd())

try:
    from src.infrastructure.database.models import Client, Router
    from src.infrastructure.mikrotik.adapter import MikroTikAdapter
except ImportError:
    print("Error: No se pudieron importar los módulos.")
    sys.exit(1)

def scan_network_and_update_ips():
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    print("="*100)
    print(f"{'ESCANEANDO RED MIKROTIK PARA ACTUALIZAR IPS':^100}")
    print("="*100)

    # 1. Obtener todos los routers online
    routers = session.query(Router).filter(Router.status == 'online').all()
    if not routers:
        print("❌ No hay routers en línea para escanear.")
        session.close()
        return

    total_updated = 0

    for router in routers:
        print(f"\n📡 Conectando a Router: {router.alias} ({router.host_address})...")
        adapter = MikroTikAdapter()
        
        if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
            try:
                # Obtener sesiones activas (PPPoE o ARP/DHCP)
                # Primero intentamos sesiones PPPoE activas
                active_sessions = adapter.get_active_pppoe_sessions()
                
                # También obtener ARP table para clientes que no son PPPoE
                arp_table = adapter.get_arp_table()
                
                # Mapear IP por nombre (para PPPoE)
                ip_by_username = {name: data['ip'] for name, data in active_sessions.items()}
                
                # Mapear IP por MAC (para DHCP/Queues)
                ip_by_mac = {entry.get('mac-address'): entry.get('address') for entry in arp_table if entry.get('mac-address')}
                
                # Obtener clientes de este router
                clients = session.query(Client).filter(Client.router_id == router.id).all()
                
                print(f"   Analizando {len(clients)} clientes...")
                
                router_updates = 0
                for client in clients:
                    new_ip = None
                    
                    # Prioridad 1: PPPoE Active Session
                    if client.username and client.username in ip_by_username:
                        new_ip = ip_by_username[client.username]
                    
                    # Prioridad 2: ARP Match por MAC
                    if not new_ip and client.mac_address and client.mac_address in ip_by_mac:
                        new_ip = ip_by_mac[client.mac_address]
                    
                    # Si encontramos una IP y es diferente a la actual (o la actual era NULL)
                    if new_ip and new_ip != client.ip_address:
                        old_ip = client.ip_address or "VACÍO"
                        client.ip_address = new_ip
                        router_updates += 1
                        total_updated += 1
                        print(f"   ✅ [UPDATE] {client.legal_name[:25]:<25} | {old_ip} -> {new_ip}")
                
                if router_updates == 0:
                    print("   ℹ️ No se detectaron cambios de IP en este router.")
                else:
                    print(f"   ✨ Total actualizados en {router.alias}: {router_updates}")
                
            except Exception as e:
                print(f"   ❌ Error escaneando {router.alias}: {e}")
            finally:
                adapter.disconnect()
        else:
            print(f"   ❌ No se pudo conectar al router {router.alias}.")

    # 3. Guardar cambios en la base de datos
    try:
        session.commit()
        print("\n" + "="*100)
        print(f"FIN DEL ESCANEO: Se actualizaron {total_updated} direcciones IP en total.")
        print("="*100)
    except Exception as e:
        session.rollback()
        print(f"❌ Error al guardar datos: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    scan_network_and_update_ips()
