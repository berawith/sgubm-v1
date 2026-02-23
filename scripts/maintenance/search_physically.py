
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

def search_pattern_physically(pattern):
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    routers = session.query(Router).filter(Router.status == 'online').all()
    print(f"Buscando el patrón '{pattern}' físicamente en los routers...")

    for r in routers:
        print(f"Buscando en {r.alias}...")
        adapter = MikroTikAdapter()
        if adapter.connect(r.host_address, r.api_username, r.api_password, r.api_port):
            try:
                secrets = adapter._api_connection.get_resource('/ppp/secret').get()
                for s in secrets:
                    if pattern.lower() in str(s).lower():
                        print(f"✅ Encontrado en {r.alias} ppp secret: {s.get('name')} | {s.get('comment')}")
                
                queues = adapter._api_connection.get_resource('/queue/simple').get()
                for q in queues:
                    if pattern.lower() in str(q).lower():
                        print(f"✅ Encontrado en {r.alias} simple queue: {q.get('name')} | {q.get('comment')}")
            finally:
                adapter.disconnect()
    session.close()

if __name__ == "__main__":
    search_pattern_physically('524')
