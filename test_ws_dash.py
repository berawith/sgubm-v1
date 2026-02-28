import os
import sys
import logging
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask
from src.infrastructure.database.db_manager import DatabaseManager, get_db, set_app
import socketio
import requests

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///c:/SGUBM-V1/data/sgubm.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db_manager = get_db()
set_app(app)

from src.infrastructure.database.models import Client, Router

logging.basicConfig(level=logging.INFO)

def run_test():
    with app.app_context():
        router = db_manager.session.query(Router).first()
        if not router:
            print("No router found")
            return

        clients = db_manager.session.query(Client).filter(Client.is_online == True).limit(5).all()
        client_ids = [c.id for c in clients]
        
        print(f"Targeting router {router.id} with clients: {client_ids}")

        sio = socketio.Client()
        
        @sio.event
        def connect():
            print("Connected to SGUBM Socket.IO Server")
            sio.emit('join_router', {'router_id': router.id})
            sio.emit('subscribe_clients', {'router_id': router.id, 'client_ids': client_ids})
            
            # Start emitting fake traffic
            import threading
            def bg_emit():
                for i in range(10):
                    time.sleep(2)
                    fake_data = {}
                    for cid in client_ids:
                        multiplier = i + 1
                        fake_data[cid] = {
                            'id': cid,
                            'status': 'online',
                            'download': 2000000 * multiplier,  # 2 Mbps
                            'upload': 1000000 * multiplier,    # 1 Mbps
                            'method': 'arp'
                        }
                    print(f"Pushing fake traffic event... Iter {i}")
                    # In real life, the server emits to room 'router_{router.id}'
                    # Because we are a client, we cannot emit directly to others via namespace unless we hit an endpoint.
                    try:
                        resp = requests.post("http://localhost:5000/api/dash/test_ws", json={
                            'router_id': router.id, 
                            'data': fake_data
                        })
                    except:
                        pass
                print("Done emitting.")
                sio.disconnect()
            
            b_thread = threading.Thread(target=bg_emit)
            b_thread.start()

        @sio.event
        def connect_error(err):
            print("Connection failed", err)

        @sio.event
        def disconnect():
            print("Disconnected")
            
        @sio.event
        def client_traffic(data):
            print("Received client_traffic relay:", list(data.keys()))

        try:
            sio.connect('http://localhost:5000')
            sio.wait()
        except Exception as e:
            print("Server not running or socket error:", e)

if __name__ == '__main__':
    run_test()
