
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.getcwd())
try:
    from src.infrastructure.database.models import Client, Payment, Invoice, Router
    from src.infrastructure.mikrotik.adapter import MikroTikAdapter
except ImportError:
    sys.exit(1)

def fix_all_entities():
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    print("--- INICIANDO CORRECCIÓN FINAL DE IDENTIDADES ---")

    # 1. Recuperar/Crear a Leocadia Mora
    leocadia = session.query(Client).filter(Client.legal_name.ilike('%Leocadia Mora%')).first()
    if not leocadia:
        leocadia = Client(
            legal_name='Leocadia Mora',
            subscriber_code='CLT-0499', # Código que tenía originalmente según auditoría
            ip_address='77.16.10.239',
            router_id=4, # LOS BANCOS
            status='active',
            username='LeocadiaMora',
            monthly_fee=90000.0,
            account_balance=0.0
        )
        session.add(leocadia)
        session.flush()
        print(f"✅ Leocadia Mora recreada (ID: {leocadia.id}) en Router LOS BANCOS.")
    else:
        leocadia.ip_address = '77.16.10.239'
        leocadia.router_id = 4
        print(f"✅ Leocadia Mora actualizada (ID: {leocadia.id}) en Router LOS BANCOS.")

    # 2. Corregir a Juan Pablo Barrios
    jp = session.query(Client).filter(Client.legal_name.ilike('%Juan Pablo Barrios%')).first()
    if jp:
        jp.ip_address = '177.77.70.9'
        jp.router_id = 1 # PRINCIPAL
        print(f"✅ Juan Pablo Barrios corregido (Router: PRINCIPAL, IP: 177.77.70.9)")

    # 3. Corregir a Grabiela Alvarado
    grabiela = session.query(Client).filter(Client.legal_name.ilike('%Grabiela Alvarado%')).first()
    if grabiela:
        grabiela.ip_address = '177.77.70.23'
        grabiela.router_id = 1 # PRINCIPAL
        print(f"✅ Grabiela Alvarado corregida (Router: PRINCIPAL, IP: 177.77.70.23)")

    # 4. Reasignar Pagos
    # El pago ID 188 es el que pertenecía originalmente a Leocadia (IP 77.16.10.239)
    p188 = session.query(Payment).get(188)
    if p188:
        p188.client_id = leocadia.id
        print(f"✅ Pago ID 188 devuelto a Leocadia Mora.")

    session.commit()

    # 5. Sincronización Física (MikroTik)
    # A. Leocadia en LOS BANCOS
    router_lb = session.query(Router).get(4)
    if router_lb and router_lb.status == 'online':
        print(f"Sincronizando Leocadia en LOS BANCOS...")
        adapter = MikroTikAdapter()
        if adapter.connect(router_lb.host_address, router_lb.api_username, router_lb.api_password, router_lb.api_port):
            try:
                # Cambiar nombre del secret que tenga la IP de Leocadia
                secrets = adapter._api_connection.get_resource('/ppp/secret')
                items = secrets.get(remote_address='77.16.10.239')
                if items:
                    secrets.set(id=items[0].get('.id') or items[0].get('id'), name='Leocadia Mora', comment='Sincronizado SGUBM')
                    print(f"   ✅ Secreto actualizado a 'Leocadia Mora' en LOS BANCOS.")
                adapter.restore_client_service(leocadia.to_dict())
            except Exception as e:
                print(f"   ❌ Error en LOS BANCOS: {e}")
            finally:
                adapter.disconnect()

    # B. Juan Pablo en PRINCIPAL
    router_pr = session.query(Router).get(1)
    if router_pr and router_pr.status == 'online':
        print(f"Sincronizando Juan Pablo en PRINCIPAL...")
        adapter = MikroTikAdapter()
        if adapter.connect(router_pr.host_address, router_pr.api_username, router_pr.api_password, router_pr.api_port):
            try:
                adapter.restore_client_service(jp.to_dict())
                print(f"   ✅ Servicio de Juan Pablo restaurado en PRINCIPAL.")
            except Exception as e:
                print(f"   ❌ Error en PRINCIPAL: {e}")
            finally:
                adapter.disconnect()

    print("--- PROCESO COMPLETADO ---")
    session.close()

if __name__ == "__main__":
    fix_all_entities()
