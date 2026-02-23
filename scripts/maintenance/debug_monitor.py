from run import create_app
from src.application.services.monitoring_manager import MonitoringManager
import time

def debug_monitor():
    app = create_app()
    with app.app_context():
        manager = MonitoringManager.get_instance()
        print(f"--- Monitoring Manager Status ---")
        print(f"Active Threads: {len(manager.router_threads)}")
        print(f"Monitored Routers: {list(manager.router_threads.keys())}")
        print(f"Monitored Clients: {manager.monitored_clients}")
        print(f"Monitored Interfaces: {manager.monitored_interfaces}")
        print(f"SocketIO Injected: {manager.socketio is not None}")
        
        for r_id, thread in manager.router_threads.items():
            print(f"Thread for Router {r_id}: Alive={thread.is_alive()}")
            
        # Check sessions
        print(f"Active Sessions: {list(manager.router_sessions.keys())}")

if __name__ == "__main__":
    debug_monitor()
