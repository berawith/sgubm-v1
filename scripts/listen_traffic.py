
import socketio
import json
import time

sio = socketio.Client()

@sio.event
def connect():
    print("Connected to server")
    # Join router 1 (common default)
    sio.emit('join_router', {'router_id': 1})
    # Subscribe to clients found in diagnostic
    sio.emit('subscribe_clients', {'client_ids': [56, 57]})

@sio.on('client_traffic')
def on_traffic(data):
    print("Received client_traffic event:")
    print(json.dumps(data, indent=2))

@sio.on('dashboard_traffic_update')
def on_dashboard(data):
    print("Received dashboard_traffic_update event:")
    print(json.dumps(data, indent=2))

if __name__ == '__main__':
    try:
        sio.connect('http://localhost:5000') # Adjust port if needed
        print("Waiting for events...")
        time.sleep(10)
        sio.disconnect()
    except Exception as e:
        print(f"Error: {e}")
