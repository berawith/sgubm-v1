"""
Monitoring Manager
Gestiona hilos de monitoreo en tiempo real por cada router
"""
import threading
import time
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import asyncio
from typing import Dict, List, Any, Optional, Set
# from flask_socketio import SocketIO -> Eliminado
# from src.infrastructure.database.db_manager import get_db, get_app -> Ver abajo
from src.application.services.traffic_engine import TrafficSurgicalEngine
from src.application.services.monitoring_utils import MikroTikTimeParser
from src.application.services.status_resolver import StatusResolver
from src.infrastructure.mikrotik.adapter import MikroTikAdapter

logger = logging.getLogger(__name__)

class MonitoringManager:
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.router_threads: Dict[int, threading.Thread] = {}
        self.stop_events: Dict[int, threading.Event] = {}
        self.router_sessions: Dict[int, MikroTikAdapter] = {}
        self.router_locks: Dict[int, threading.Lock] = {} # Locks per router
        self.monitored_interfaces: Dict[int, set] = {} # {router_id: {iface_names}}
        self.dashboard_interfaces: Dict[int, set] = {} # {router_id: {iface_names}}
        self.monitored_clients: Dict[int, set] = {}    # {router_id: {client_ids}}
        self.traffic_engine = TrafficSurgicalEngine() # MOTOR QUIRÚRGICO AISLADO
        self.last_db_sync: Dict[int, float] = {} # {router_id: last_sync_timestamp}
        self.last_name_sync: Dict[int, float] = {} # {router_id: last_sync_timestamp}
        self.client_metadata_cache = {}
        self.last_emitted_data: Dict[int, Dict] = {} # {router_id: {client_id: last_data}}
        self.global_traffic = {'tx': 0, 'rx': 0}
        self.socketio: Optional[Any] = None
        self._active_syncs: Set[int] = set() # {router_id} para evitar hilos de sync duplicados
        self._sync_lock = threading.Lock()
        self.loop = None

    @classmethod
    def get_instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = MonitoringManager()
            return cls._instance

    def init_socketio(self, sio):
        self.sio = sio
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = asyncio.get_event_loop()
        logger.info(f"MonitoringManager: AsyncServer injected and loop captured: {self.loop}")

    def _safe_emit(self, event, data, room=None):
        """Emite eventos de forma segura desde hilos de fondo al loop asíncrono"""
        if not hasattr(self, 'sio') or not self.sio:
            return
            
        try:
            if room:
                asyncio.run_coroutine_threadsafe(self.sio.emit(event, data, room=room), self.loop)
            else:
                asyncio.run_coroutine_threadsafe(self.sio.emit(event, data), self.loop)
        except Exception as e:
            logger.error(f"Error in _safe_emit ({event}): {e}")

    def start_router_monitoring(self, router_id: int):
        """Starts a dedicated thread for monitoring a specific router"""
        if router_id in self.router_threads and self.router_threads[router_id].is_alive():
            return

        stop_event = threading.Event()
        self.stop_events[router_id] = stop_event
        
        thread = threading.Thread(
            target=self._monitor_loop,
            args=(router_id, stop_event),
            daemon=True
        )
        self.router_threads[router_id] = thread
        if router_id not in self.router_locks:
            self.router_locks[router_id] = threading.Lock()
            
        thread.start()
        logger.info(f"Started monitoring thread for router {router_id}")

    def stop_router_monitoring(self, router_id: int):
        """Stops the monitoring thread for a specific router"""
        if router_id in self.stop_events:
            self.stop_events[router_id].set()
            del self.stop_events[router_id]
        if router_id in self.router_threads:
            del self.router_threads[router_id]
        if router_id in self.router_sessions:
            del self.router_sessions[router_id]

    def get_active_session(self, router_id: int) -> Optional[MikroTikAdapter]:
        """Returns an active MikroTikAdapter session if available and connected"""
        adapter = self.router_sessions.get(router_id)
        if adapter and adapter._is_connected:
            return adapter
        return None

    def start_dashboard_monitoring(self):
        """Ensures all routers with dashboard interfaces are being monitored"""
        from src.infrastructure.database.models import Router
        import json
        
        db = get_db()
        session = db.session
        routers = session.query(Router).all()
        
        for router in routers:
            # Requisito proactivo: Si está online debe monitorearse
            # aunque no tenga interfaces de dashboard configuradas aún.
            if router.status == 'online' or router.monitored_interfaces:
                try:
                    if router.monitored_interfaces:
                        prefs = json.loads(router.monitored_interfaces)
                        dashboard_ifaces = [name for name, p in prefs.items() if p.get('dashboard', False)]
                        if dashboard_ifaces:
                            self.dashboard_interfaces[router.id] = dashboard_ifaces
                            for iface in dashboard_ifaces:
                                self.add_monitored_interface(router.id, iface)
                    
                    self.start_router_monitoring(router.id)
                except Exception as e:
                    logger.error(f"Error starting proactive monitoring for router {router.id}: {e}")

    def _monitor_loop(self, router_id: int, stop_event: threading.Event):
        """Main loop for monitoring a router"""
        from src.infrastructure.database.models import Router
        from src.infrastructure.database.db_manager import get_db
        
        db = get_db()
        adapter = None
        
        try:
            # 1. Get router details from DB
            session = db.session
            router = session.query(Router).get(router_id)
            if not router:
                logger.error(f"Router {router_id} not found in database")
                return

            # 2. Establish persistent connection
            adapter = MikroTikAdapter()
            
            # Reintentar conexión inicial si falla (Resiliencia ante routers offline)
            while not stop_event.is_set():
                connected = adapter.connect(
                    host=router.host_address,
                    username=router.api_username,
                    password=router.api_password,
                    port=router.api_port,
                    timeout=5
                )
                
                if connected:
                    break
                
                # Reportar estado offline pero seguir intentando
                logger.warning(f"Router {router_id} ({router.alias}) offline. Reintentando en 30s...")
                self._safe_emit('router_status', {
                    'router_id': router_id,
                    'status': 'offline',
                    'error': 'No se pudo establecer conexión inicial'
                }, room=f"router_{router_id}")
                
                # Esperar 30 segundos antes de reintentar (permitiendo interrupción)
                if stop_event.wait(30):
                    return

            self.router_sessions[router_id] = adapter
            
            # 3. Fast monitoring loop
            last_metrics_check = 0
            while not stop_event.is_set():
                now = time.time()
                
                try:
                    # Sync Service, Interfaces, Queues, Traffic, etc.
                    if adapter._is_connected:
                        try:
                            # Sincronizar operaciones pendientes cada 15 segundos
                            if now - getattr(self, f'last_pending_sync_{router_id}', 0) > 15.0:
                                setattr(self, f'last_pending_sync_{router_id}', now)
                                
                                def run_sync():
                                    with self._sync_lock:
                                        if router_id in self._active_syncs:
                                            return
                                        self._active_syncs.add(router_id)

                                    try:
                                        from src.infrastructure.database.db_manager import get_db
                                        db_local = get_db()
                                        from src.application.services.sync_service import SyncService
                                        sync_service = SyncService(db_local)
                                        router_info = router.to_dict()
                                        result = sync_service.sync_router_operations(router_id, router_info)
                                        
                                        if result['completed'] > 0:
                                            logger.info(f"🔄 Sincronizadas {result['completed']} operaciones para router {router_id}")
                                            self._safe_emit('sync_completed', {
                                                'router_id': router_id,
                                                'router_name': router.alias,
                                                'completed': result['completed'],
                                                'timestamp': datetime.now().isoformat()
                                            })
                                    finally:
                                        with self._sync_lock:
                                            if router_id in self._active_syncs:
                                                self._active_syncs.remove(router_id)

                                threading.Thread(target=run_sync, daemon=True).start()
                        except Exception as e:
                            logger.error(f"Error iniciando Sync Service: {e}")

                    # Pre-fetch surgical data
                    try:
                        all_ifaces = adapter._get_resource('/interface').call('print', {".proplist": "name,rx-byte,tx-byte,disabled,last-link-up-time"})
                        all_queues = adapter._get_resource('/queue/simple').call('print', {".proplist": "name,target,rate,max-limit,burst-limit,disabled"})
                    except Exception as mt_err:
                        logger.warning(f"Error surgical pre-fetch: {mt_err}")
                        all_ifaces, all_queues = [], []

                    # Traffic Interfaces (Graphed in Modal)
                    current_interfaces = list(self.monitored_interfaces.get(router_id, []))
                    if current_interfaces:
                        traffic_data = {}
                        for iface_name in current_interfaces:
                            # 1. Intentar obtener de colas (por si es un alias o cliente)
                            temp_q = adapter.get_bulk_traffic([iface_name], all_queues=all_queues)
                            if temp_q and iface_name in temp_q and (temp_q[iface_name]['tx'] > 0 or temp_q[iface_name]['rx'] > 0):
                                traffic_data[iface_name] = temp_q[iface_name]
                            else:
                                # 2. Intentar obtener directamente de la interfaz (monitor-traffic)
                                traffic_data[iface_name] = adapter.get_interface_traffic(iface_name)
                        
                        if traffic_data:
                            self._safe_emit('interface_traffic', {
                                'router_id': router_id,
                                'traffic': traffic_data,
                                'timestamp': now
                            }, room=f"router_{router_id}")

                    # Background DB Sync (60s)
                    if now - self.last_db_sync.get(router_id, 0) > 60:
                        self.last_db_sync[router_id] = now
                        try:
                            from src.infrastructure.database.models import Client
                            session_sync = get_db().session_factory()
                            try:
                                all_active = session_sync.query(Client.id).filter(Client.router_id == router_id, Client.status == 'active').all()
                                all_ids = [c.id for c in all_active]
                            finally:
                                session_sync.close()
                            
                            if all_ids:
                                full_snapshot = self.traffic_engine.get_snapshot(adapter, all_ids, get_db().session_factory, raw_ifaces=all_ifaces, raw_queues=all_queues)
                                offline_meta = adapter.get_all_last_seen()
                                self.update_clients_online_status(router_id, full_snapshot, offline_metadata=offline_meta)
                        except Exception as sync_e:
                            logger.error(f"Error in background sync: {sync_e}")

                    # Client Monitoring
                    router_monitored_clients = list(self.monitored_clients.get(router_id, []))
                    if router_monitored_clients:
                        if now - self.last_name_sync.get(router_id, 0) > 300:
                            self.last_name_sync[router_id] = now
                            self._sync_technical_names(router_id, adapter)

                        client_traffic = self.traffic_engine.get_snapshot(adapter, router_monitored_clients, get_db().session_factory, raw_ifaces=all_ifaces, raw_queues=all_queues)
                        if client_traffic:
                            self.update_clients_online_status(router_id, client_traffic)
                            
                            router_last = self.last_emitted_data.get(router_id, {})
                            delta_data = {}
                            for cid, cdata in client_traffic.items():
                                last_cdata = router_last.get(cid)
                                if not last_cdata or cdata['status'] != last_cdata['status'] or \
                                   abs(cdata['upload'] - last_cdata['upload']) > 50000 or \
                                   abs(cdata['download'] - last_cdata['download']) > 50000:
                                    delta_data[cid] = cdata
                            
                            if delta_data:
                                router_last.update(delta_data)
                                self.last_emitted_data[router_id] = router_last
                                self._safe_emit('client_traffic', delta_data, room=f"router_{router_id}")

                    # Dashboard Interfaces
                    dashboard_ifaces = self.dashboard_interfaces.get(router_id, [])
                    if dashboard_ifaces:
                        total_tx, total_rx = 0, 0
                        for iface in dashboard_ifaces:
                            res = adapter.get_interface_traffic(iface)
                            total_tx += res.get('tx', 0)
                            total_rx += res.get('rx', 0)
                        self._safe_emit('dashboard_traffic_update', {'router_id': router_id, 'tx': total_tx, 'rx': total_rx, 'timestamp': now})

                    # Router Metrics (5s)
                    if now - last_metrics_check >= 5.0:
                        last_metrics_check = now
                        system_info = adapter.get_system_info()
                        self._safe_emit('router_metrics', {'router_id': router_id, 'cpu': system_info.get('cpu_load', '0'), 'memory': system_info.get('memory_usage', 0), 'uptime': system_info.get('uptime', ''), 'timestamp': now}, room=f"router_{router_id}")

                except Exception as loop_e:
                    logger.error(f"Error in fast loop for router {router_id}: {loop_e}")
                    if not adapter._is_connected:
                        break # Force re-connect

                time.sleep(1.5)

        except Exception as e:
            logger.critical(f"Critical error in monitor thread for router {router_id}: {e}")
        finally:
            if adapter: adapter.disconnect()
            if router_id in self.router_sessions: del self.router_sessions[router_id]
            logger.info(f"Monitor thread for router {router_id} finished")

    def add_monitored_interface(self, router_id: int, interface_name: str):
        if router_id not in self.monitored_interfaces:
            self.monitored_interfaces[router_id] = set()
        self.monitored_interfaces[router_id].add(interface_name)

    def remove_monitored_interface(self, router_id: int, interface_name: str):
        if router_id in self.monitored_interfaces:
            if interface_name in self.monitored_interfaces[router_id]:
                self.monitored_interfaces[router_id].remove(interface_name)

    def add_monitored_clients(self, router_id: Optional[Any], client_ids: List[Any]):
        """Agrega clientes al monitoreo, infiriendo el router si no se proporciona"""
        # 1. Agrupar clientes por su router_id real (desde DB)
        from src.infrastructure.database.models import Client
        db = get_db()
        session = db.session
        
        try:
            # Convertir IDs a lista limpia
            clean_client_ids = []
            for cid in client_ids:
                try: clean_client_ids.append(int(cid))
                except: continue
                
            if not clean_client_ids: return

            # Cargar metadata y router_id de los clientes
            clients_in_db = session.query(Client).filter(Client.id.in_(clean_client_ids)).all()
            
            for client in clients_in_db:
                # Usar el router_id del cliente, o el proporcionado como fallback
                rid = client.router_id or router_id
                if rid:
                    rid_int = int(rid)
                    if rid_int not in self.monitored_clients:
                        self.monitored_clients[rid_int] = set()
                    self.monitored_clients[rid_int].add(client.id)
                    
                    # Asegurar que el hilo de este router esté corriendo
                    self.start_router_monitoring(rid_int)
                    
            logger.info(f"Added {len(clients_in_db)} clients to monitoring across routers")
            
        except Exception as e:
            logger.error(f"Error adding monitored clients: {e}")
        finally:
            session.close()
            db.remove_session()

    def remove_monitored_clients(self, client_ids: List[int]):
        for router_id in self.monitored_clients:
            for c_id in client_ids:
                if c_id in self.monitored_clients[router_id]:
                    self.monitored_clients[router_id].remove(c_id)

    def get_router_clients_traffic(self, router_id: int, client_ids: List[int], adapter, all_ifaces: List[Dict] = None, all_queues: List[Dict] = None):
        """
        Legacy wrapper. Ahora usa el motor modular TrafficSurgicalEngine.
        """
        return self.traffic_engine.get_snapshot(adapter, client_ids, get_db().session_factory)


    def update_clients_online_status(self, router_id: int, traffic_results: Dict[str, Any], offline_metadata: Dict[str, str] = None):
        """Actualiza el estado is_online y last_seen en la BD basado en el monitoreo"""
        try:
            from src.infrastructure.database.models import Client
            
            try:
                db = get_db()
                session = db.session
                clients_db = session.query(Client).filter(Client.router_id == router_id).all()
                client_map = {c.id: c for c in clients_db}
            except Exception as e:
                logger.error(f"Error accessing DB in update_clients_online_status: {e}")
                return

            # --- LÓGICA ANTI-FLICKER (CONTROL DE CORDURA) ---
            # Si el snapshot indica un bajón masivo e inusual (ej: >50% de los clientes pasan a offline de golpe)
            # y el adaptador dice estar conectado, sospechamos de una lectura parcial de MikroTik.
            total_in_snapshot = len(traffic_results)
            if total_in_snapshot > 10: # Solo para lotes significativos
                online_in_snapshot = sum(1 for info in traffic_results.values() if info.get('status') == 'online')
                online_ratio = online_in_snapshot / total_in_snapshot
                
                # Si menos del 10% aparecen online de repente, es sospechoso (especialmente en routers grandes)
                if online_ratio < 0.10:
                    logger.warning(f"⚠️ Anti-Flicker: Snapshot para router {router_id} reporta solo {online_in_snapshot}/{total_in_snapshot} online. Posible lectura parcial. Abortando actualización masiva de DB para prevenir falsos negativos.")
                    return
            # -----------------------------------------------

            client_updates = []

            for client_id_str, info in traffic_results.items():
                # Fix: Handle both int and str keys (TrafficSurgicalEngine returns int)
                if isinstance(client_id_str, str) and not client_id_str.isdigit(): continue
                
                cid = int(client_id_str)
                if cid not in client_map: continue
                
                client = client_map[cid]
                is_online = StatusResolver.resolve_online_status(info)
                
                update_data = {
                    'id': cid,
                    'is_online': is_online
                }

                if is_online:
                     # Si está online, last_seen es AHORA
                     update_data['last_seen'] = datetime.now()
                     if cid in self.client_metadata_cache:
                         self.client_metadata_cache[cid]['last_seen_cache'] = update_data['last_seen'].isoformat()
                else:
                    # Si está offline, intentamos usar metadata de Mikrotik
                    if offline_metadata:
                        last_seen_dt = StatusResolver.resolve_last_seen(client, offline_metadata)
                        if last_seen_dt:
                            update_data['last_seen'] = last_seen_dt
                            if cid in self.client_metadata_cache:
                                self.client_metadata_cache[cid]['last_seen_cache'] = last_seen_dt.isoformat()

                client_updates.append(update_data)
            
            if not client_updates: return

            for u in client_updates:
                data = {'is_online': u['is_online']}
                if 'last_seen' in u:
                    data['last_seen'] = u['last_seen']
                
                session.query(Client).filter(Client.id == u['id']).update(data, synchronize_session=False)

            session.commit()
            
            if offline_metadata:
                logger.info(f"✅ DB Sync Router {router_id}: Actualizado con metadatos del MikroTik.")
        except Exception as e:
            logger.error(f"Error syncing client status to DB: {e}")
            try: get_db().session.rollback()
            except: pass
        finally:
            get_db().remove_session()

    def _sync_technical_names(self, router_id: int, adapter: MikroTikAdapter):
        """
        Sincroniza los nombres técnicos de MikroTik (Queues e Interfaces) 
        con los clientes en la base de datos para optimizar el monitoreo.
        Punto 5 del Plan de Optimización.
        """
        logger.info(f"⚙️ Iniciando sincronización de nombres técnicos para router {router_id}...")
        try:
            from src.infrastructure.database.db_manager import get_db
            db_manager = get_db()
            db = db_manager.session
            from src.infrastructure.database.models import Client
            clients = db.query(Client).filter(Client.router_id == router_id).all()
            
            updates = 0
            for client in clients:
                user_l = client.username.lower()
                legal_norm = normalize_name(client.legal_name)
                c_ip = client.ip_address.strip() if client.ip_address else None
                    
                # A. Resolver Interfaz
                iface_patterns = [user_l, f"<{user_l}>", f"pppoe-{user_l}", f"<pppoe-{user_l}>"]
                resolved_iface = next((iface_map[p] for p in iface_patterns if p in iface_map), None)
                
                # B. Resolver Cola
                queue_patterns = [user_l, f"<{user_l}>", legal_norm, f"<{legal_norm}>", user_l.replace('-', '_')]
                resolved_queue = next((queue_by_name[p] for p in queue_patterns if p in queue_by_name), None)
                if not resolved_queue and c_ip in queue_by_ip:
                    resolved_queue = queue_by_ip[c_ip]
                
                # Guardar si cambió
                if client.mikrotik_queue_name != resolved_queue or client.mikrotik_interface_name != resolved_iface:
                    client.mikrotik_queue_name = resolved_queue
                    client.mikrotik_interface_name = resolved_iface
                    updates += 1
                
                if updates > 0:
                    db.commit()
                    logger.info(f"✅ Sincronizados {updates} nombres técnicos en DB para router {router_id}")

        except Exception as e:
            logger.error(f"Error en sync_technical_names: {e}")
