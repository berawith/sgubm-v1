
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.getcwd())
try:
    from src.infrastructure.database.models import Client, Router
    from src.infrastructure.mikrotik.adapter import MikroTikAdapter
except ImportError:
    print("Error")
    sys.exit(1)

def fix_router():
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    # Juan Pablo ya tiene la IP correcta en BD
    jp = session.query(Client).filter(Client.legal_name.like('%Juan Pablo Barrios%')).first()
    router = session.query(Router).get(4)

    if jp and router:
        print(f"Sincronizando MikroTik para: {jp.legal_name}")
        adapter = MikroTikAdapter()
        if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
            try:
                # 1. Buscar el Secret que tiene el nombre "LeocadiaMora" y cambiarlo a "Juan Pablo Barrios"
                secrets = adapter._api_connection.get_resource('/ppp/secret')
                # Buscamos por IP mejor ya que el nombre es el que está mal
                all_s = secrets.get()
                for s in all_s:
                    if s.get('remote-address') == '77.16.10.239':
                        sid = s.get('.id') or s.get('id')
                        secrets.set(id=sid, name=jp.legal_name, comment="Sincronizado SGUBM")
                        print(f"✅ Nombre en MikroTik actualizado a: {jp.legal_name}")
                        break
                
                # 2. Asegurarse que esté habilitado y fuera de bloqueos
                adapter.restore_client_service(jp.to_dict())
                print("✅ Servicio Restaurado/Habilitado en MikroTik.")
            finally:
                adapter.disconnect()

    session.close()

if __name__ == "__main__":
    fix_router()
