
import os
import sys
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Configurar logging para ver solo lo importante
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Añadir el path del proyecto para importar modelos
sys.path.append(os.getcwd())

try:
    from src.infrastructure.database.models import Client, Router, Invoice
    from src.infrastructure.mikrotik.adapter import MikroTikAdapter
except ImportError:
    print("Error: No se pudieron importar los módulos. Ejecuta desde la raíz del proyecto.")
    sys.exit(1)

def audit_and_clean_cuts():
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    print("="*80)
    print("INFORME DE LIMPIEZA DE CORTES INDEBIDOS EN MIKROTIK")
    print("="*80)
    print(f"{'SERVIDOR':<15} | {'CLIENTE':<35} | {'IP':<15} | {'ESTADO BD'}")
    print("-"*80)

    # Obtener routers online
    routers = session.query(Router).filter(Router.status == 'online').all()
    
    total_cleaned = 0
    detailed_report = []

    for router in routers:
        adapter = MikroTikAdapter()
        if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
            try:
                # Obtener la lista de bloqueados actual del router
                addr_lists = adapter._api_connection.get_resource('/ip/firewall/address-list')
                # Obtenemos toda la lista para IPS_BLOQUEADAS
                try:
                    all_blocked = addr_lists.get(list='IPS_BLOQUEADAS')
                except:
                    all_blocked = []

                if not all_blocked:
                    adapter.disconnect()
                    continue

                # Para cada entrada en el router, verificar en la BD si el cliente YA PAGÓ
                for entry in all_blocked:
                    ip_full = entry.get('address', '')
                    clean_ip = ip_full.split('/')[0]
                    entry_id = entry.get('.id') or entry.get('id')
                    
                    # Buscar al cliente por esta IP en la BD
                    client = session.query(Client).filter(Client.ip_address.like(f"{clean_ip}%")).first()
                    
                    if not client:
                        # Si no hay cliente vinculado a esa IP en BD pero está bloqueado, podría ser basura o cliente eliminado
                        # Por seguridad, si no lo conocemos, no lo tocamos a menos que quieras limpiar "basura"
                        continue

                    # CRITERIO DE "YA PAGÓ": Saldo <= 0 o Status 'active'
                    # Verificamos también si tiene facturas unpaid por si acaso el balance miente
                    unpaid_count = session.query(Invoice).filter(Invoice.client_id == client.id, Invoice.status == 'unpaid').count()
                    
                    should_be_active = (client.account_balance or 0) <= 0 and unpaid_count == 0
                    
                    # También si el status manual es 'active', debe estar fuera de cortes
                    if client.status == 'active' or should_be_active:
                        # ¡ERROR! Cliente está pagado o activo pero bloqueado en MikroTik
                        print(f"{router.alias:<15} | {client.legal_name[:35]:<35} | {clean_ip:<15} | ✅ PAGADO/ACTIVO")
                        
                        # SACAR DE LA LISTA
                        if entry_id:
                            addr_lists.remove(id=entry_id)
                            
                            # También rehabilitar Secret/Queue si estaba deshabilitado
                            adapter.restore_client_service(client.to_dict())
                            
                            total_cleaned += 1
                            detailed_report.append({
                                'server': router.alias,
                                'name': client.legal_name,
                                'ip': clean_ip,
                                'status': 'Restaurado (Ya pagó)'
                            })

            except Exception as e:
                logger.error(f"Error procesando router {router.alias}: {e}")
            finally:
                adapter.disconnect()

    print("-"*80)
    if total_cleaned == 0:
        print("✅ No se encontraron clientes pagados bloqueados indebidamente.")
    else:
        print(f"✅ Se restauró el servicio a {total_cleaned} clientes que ya estaban al día.")
    print("="*80)

    session.close()

if __name__ == "__main__":
    audit_and_clean_cuts()
