
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

def find_grabiela_physically():
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    routers = session.query(Router).filter(Router.status == 'online').all()
    print("Buscando a Grabiela físicamente en los routers...")

    for r in routers:
        print(f"Buscando en {r.alias}...")
        adapter = MikroTikAdapter()
        if adapter.connect(r.host_address, r.api_username, r.api_password, r.api_port):
            try:
                secrets = adapter._api_connection.get_resource('/ppp/secret').get()
                for s in secrets:
                    if 'grabiela' in s.get('name', '').lower() or 'grabiela' in s.get('comment', '').lower():
                        print(f"✅ ¡ENCONTRADA en {r.alias} ppp secret!")
                        print(f"   Name: {s.get('name')} | IP: {s.get('remote-address')} | Comment: {s.get('comment')}")
                
                queues = adapter._api_connection.get_resource('/queue/simple').get()
                for q in queues:
                    if 'grabiela' in q.get('name', '').lower() or 'grabiela' in q.get('comment', '').lower():
                        print(f"✅ ¡ENCONTRADA en {r.alias} simple queue!")
                        print(f"   Name: {q.get('name')} | IP: {q.get('target')} | Comment: {q.get('comment')}")
            finally:
                adapter.disconnect()
    session.close()

if __name__ == "__main__":
    find_grabiela_physically()
