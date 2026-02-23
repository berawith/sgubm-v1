from run import create_app
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client
from src.infrastructure.mikrotik.adapter import MikroTikAdapter

app = create_app()
with app.app_context():
    db = get_db()
    session = db.session
    repo = db.get_client_repository()
    
    # 1. Identificar a Isabel de Veracruz (la que tiene IP 0.0.0.0 o nombre exacto)
    isabel_veracruz = session.query(Client).filter(Client.username == 'IsabelZambrano', Client.ip_address == '0.0.0.0').first()
    
    if not isabel_veracruz:
        # Intentar buscar por nombre si el usuario no coincide exactamente
        isabel_veracruz = session.query(Client).filter(Client.legal_name == 'Isabelzambrano').first()

    if isabel_veracruz:
        print(f"✅ Encontrada Isabel de Veracruz (ID: {isabel_veracruz.id})")
        old_ip = isabel_veracruz.ip_address
        isabel_veracruz.ip_address = '10.10.80.6'
        
        # 2. Intentar obtener su MAC del router
        router = db.get_router_repository().get_by_id(isabel_veracruz.router_id)
        adapter = MikroTikAdapter()
        if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
            try:
                leases = adapter.get_dhcp_leases()
                for l in leases:
                    if l.get('address') == '10.10.80.6':
                        isabel_veracruz.mac_address = l.get('mac-address')
                        print(f"   [+] MAC sincronizada: {isabel_veracruz.mac_address}")
                        break
                
                if not isabel_veracruz.mac_address:
                    arp = adapter.get_arp_table()
                    for a in arp:
                        if a.get('address') == '10.10.80.6':
                            isabel_veracruz.mac_address = a.get('mac-address')
                            print(f"   [+] MAC encontrada en ARP: {isabel_veracruz.mac_address}")
                            break
            finally:
                adapter.disconnect()
        
        session.commit()
        print(f"🚀 Registro actualizado: {isabel_veracruz.legal_name} | IP: {old_ip} -> {isabel_veracruz.ip_address}")
    else:
        print("❌ No se encontró el registro incompleto de IsabelZambrano para actualizar.")

    # Mostrar estado final de ambas
    print("\n--- ESTADO FINAL EN BASE DE DATOS ---")
    all_isabels = session.query(Client).filter(Client.legal_name.like('%Isabel%')).all()
    for c in all_isabels:
        print(f"ID: {c.id} | Nombre: {c.legal_name} | IP: {c.ip_address} | MAC: {c.mac_address}")
