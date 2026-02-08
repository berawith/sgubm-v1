from src.application.services.monitoring_manager import MonitoringManager
import time

monitor = MonitoringManager.get_instance()
print(f"Active Threads: {len(monitor.router_threads)}")
for rid, thread in monitor.router_threads.items():
    print(f"Router {rid}: Alive={thread.is_alive()}")

print(f"Monitored Clients: {monitor.monitored_clients}")
print(f"Sessions: {monitor.router_sessions.keys()}")
