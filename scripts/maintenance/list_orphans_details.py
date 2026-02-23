import os
import sys
sys.path.append(os.getcwd())
from src.infrastructure.database.models import Router, Client
from src.infrastructure.mikrotik.adapter import MikroTikAdapter
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def list_orphans():
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    routers = session.query(Router).filter(Router.status == 'online').all()
    
    for router in routers:
        print(f"\nEvaluating Router: {router.alias}")
        adapter = MikroTikAdapter()
        if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
            try:
                secrets = adapter._api_connection.get_resource('/ppp/secret').get()
                queues = adapter._api_connection.get_resource('/queue/simple').get()
                
                mt_usernames = set()
                for s in secrets:
                    name = s.get('name')
                    if name: mt_usernames.add(name)
                for q in queues:
                    name = q.get('name')
                    if name: mt_usernames.add(name)
                
                db_clients = session.query(Client).filter(Client.router_id == router.id).all()
                db_usernames = {c.username for c in db_clients if c.username}
                
                orphans = [name for name in mt_usernames if name not in db_usernames and not name.startswith('Sq-')]
                
                print(f"Total Orphans: {len(orphans)}")
                if orphans:
                    print("Sample Orphans (first 10):")
                    for name in orphans[:10]:
                        print(f" - {name}")
                
            finally:
                adapter.disconnect()
        else:
            print("Failed to connect.")

    session.close()

if __name__ == "__main__":
    list_orphans()
