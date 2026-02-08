
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.getcwd())
try:
    from src.infrastructure.database.models import Router
    from src.infrastructure.mikrotik.adapter import MikroTikAdapter
except ImportError:
    sys.exit(1)

def find_ip_physically(target_ip):
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    routers = session.query(Router).filter(Router.status == 'online').all()
    print(f"Buscando la IP {target_ip} físicamente en los routers...")

    for r in routers:
        print(f"Buscando en {r.alias}...")
        adapter = MikroTikAdapter()
        if adapter.connect(r.host_address, r.api_username, r.api_password, r.api_port):
            try:
                secrets = adapter._api_connection.get_resource('/ppp/secret').get()
                for s in secrets:
                    if s.get('remote-address') == target_ip:
                        print(f"✅ ¡ENCONTRADA en {r.alias} ppp secret!")
                        print(f"   Name: {s.get('name')} | IP: {s.get('remote-address')} | Comment: {s.get('comment')}")
                
                queues = adapter._api_connection.get_resource('/queue/simple').get()
                for q in queues:
                    if target_ip in q.get('target', ''):
                        print(f"✅ ¡ENCONTRADA en {r.alias} simple queue!")
                        print(f"   Name: {q.get('name')} | IP: {q.get('target')} | Comment: {q.get('comment')}")
            finally:
                adapter.disconnect()
    session.close()

if __name__ == "__main__":
    find_ip_physically('177.77.70.23')
