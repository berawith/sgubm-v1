import os
import sys
import logging
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask
from src.infrastructure.database.db_manager import DatabaseManager, get_db, set_app

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///c:/SGUBM-V1/data/sgubm.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db_manager = get_db()
set_app(app)

from src.infrastructure.database.models import Client, Router
from src.application.services.monitoring_manager import MonitoringManager
from src.infrastructure.mikrotik.adapter import MikroTikAdapter

logging.basicConfig(level=logging.DEBUG)

def run_test():
    with app.app_context():
        router = db_manager.session.query(Router).first()
        if not router:
            print("No router found")
            return

        clients = db_manager.session.query(Client).filter(Client.router_id == router.id).all()
        client_ids = [c.id for c in clients]
        mgr = MonitoringManager()

        adapter = MikroTikAdapter()
        connected = adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port, timeout=5)
        
        if not connected:
            print("Failed to connect")
            return

        print("\n--- Running exact background Full Sync Code ---")
        try:
            # 1. Interfaces (Para status y monitor-traffic)
            all_ifaces = adapter._get_resource('/interface').call('print', {'.proplist': 'name,rx-byte,tx-byte,disabled,last-link-up-time'})
            # 2. Queues (Para tráfico fallback y limites)
            all_queues = adapter._get_resource('/queue/simple').call('print', {'.proplist': 'name,target,rate,max-limit,burst-limit,disabled'})
            
            # Background full snapshot simulation
            full_snapshot = mgr.traffic_engine.get_snapshot(
                adapter, 
                client_ids, 
                db_manager.session_factory,
                raw_ifaces=all_ifaces,
                raw_queues=all_queues
            )
            
            print('Testing online/offline snapshot values:')
            for cid in [49, 51, 52]:
                print(f'Client {cid}: {full_snapshot.get(cid, {}).get("status")}')
            
            offline_meta = adapter.get_all_last_seen()
            mgr.update_clients_online_status(router.id, full_snapshot, offline_metadata=offline_meta)
            
            db_manager.session.commit()
            for cid in [49, 51, 52]:
                c = db_manager.session.query(Client).get(cid)
                print(f'DB After Background Sync - ID {c.id}: {c.is_online}')
                
        except Exception as e:
            print("Error:", e)
        finally:
            adapter.disconnect()

if __name__ == '__main__':
    run_test()
