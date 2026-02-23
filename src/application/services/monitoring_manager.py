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
from flask_socketio import SocketIO
from src.infrastructure.mikrotik.adapter import MikroTikAdapter
from src.infrastructure.database.db_manager import get_db

logger = logging.getLogger(__name__)

class MonitoringManager:
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.router_threads: Dict[int, threading.Thread] = {}
        self.stop_events: Dict[int, threading.Event] = {}
        self.router_sessions: Dict[int, MikroTikAdapter] = {}
        self.monitored_interfaces: Dict[int, set] = {} # {router_id: {iface_names}}
        self.dashboard_interfaces: Dict[int, set] = {} # {router_id: {iface_names}}
        self.monitored_clients: Dict[int, set] = {}    # {router_id: {client_ids}}
        self.client_metadata_cache: Dict[int, Dict] = {} # {client_id: {username, ip}}
        self.last_db_sync: Dict[int, float] = {} # {router_id: last_sync_timestamp}
        self.global_traffic = {'tx': 0, 'rx': 0}
        self.socketio: Optional[SocketIO] = None

    @classmethod
    def get_instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = MonitoringManager()
            return cls._instance

    def init_socketio(self, socketio: SocketIO):
        self.socketio = socketio
        logger.info("MonitoringManager: SocketIO injected")

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
        thread.start()
        logger.info(f"Started monitoring thread for router {router_id}")

    def stop_router_monitoring(self, router_id: int):
        """Stops the monitoring thread for a specific router"""
        if router_id in self.stop_events:
            self.stop_events[router_id].set()
            del self.stop_events[router_id]
        if router_id in self.router_threads:
            del self.router_threads[router_id]

    def start_dashboard_monitoring(self):
        """Ensures all routers with dashboard interfaces are being monitored"""
        from src.infrastructure.database.models import Router
        import json
        
        db = get_db()
        session = db.session
        routers = session.query(Router).all()
        
        for router in routers:
            if router.monitored_interfaces:
                try:
                    prefs = json.loads(router.monitored_interfaces)
                    dashboard_ifaces = [name for name, p in prefs.items() if p.get('dashboard', False)]
                    if dashboard_ifaces:
                        self.dashboard_interfaces[router.id] = dashboard_ifaces
                        for iface in dashboard_ifaces:
                            self.add_monitored_interface(router.id, iface)
                        self.start_router_monitoring(router.id)
                except Exception as e:
                    logger.error(f"Error loading dashboard interfaces for router {router.id}: {e}")

    def _monitor_loop(self, router_id: int, stop_event: threading.Event):
        """Main loop for monitoring a router"""
        from src.infrastructure.database.models import Router
        adapter = None
        db = get_db()
        
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
                if self.socketio:
                    self.socketio.emit('router_status', {
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
                    # ---------------------------------------------------------
                    # SYNC SERVICE: Procesar Operaciones Pendientes (suspend/activate)
                    # ---------------------------------------------------------
                    if adapter._is_connected:
                        try:
                            # Sincronizar operaciones pendientes cada 15 segundos (más conservador)
                            if now - getattr(self, f'last_pending_sync_{router_id}', 0) > 15.0:
                                setattr(self, f'last_pending_sync_{router_id}', now)
                                
                                # Instanciar localmente solo cuando sea necesario
                                from src.application.services.sync_service import SyncService
                                sync_service = SyncService(get_db())
                                result = sync_service.sync_router_operations(router_id, router.to_dict())
                                
                                if result['completed'] > 0:
                                    logger.info(f"🔄 Sincronizadas {result['completed']} operaciones pendientes para router {router_id}")
                                    if self.socketio:
                                        self.socketio.emit('sync_completed', {
                                            'router_id': router_id,
                                            'router_name': router.alias,
                                            'completed': result['completed'],
                                            'failed': result['failed'],
                                            'timestamp': datetime.now().isoformat()
                                        })
                                elif result['failed'] > 0:
                                    if self.socketio:
                                        self.socketio.emit('sync_failed', {
                                            'router_id': router_id,
                                            'router_name': router.alias,
                                            'failed': result['failed'],
                                            'timestamp': datetime.now().isoformat()
                                        })
                                    
                        except Exception as e:
                            logger.error(f"Error en Sync Service: {e}")
                    # ---------------------------------------------------------

                    # Traer Tráfico de Interfaces (Usando Bulk para mayor velocidad)
                    current_interfaces = list(self.monitored_interfaces.get(router_id, []))
                    traffic_data = {}
                    if current_interfaces:
                        traffic_data = adapter.get_bulk_traffic(current_interfaces)
                        
                        if traffic_data and self.socketio:
                            self.socketio.emit('interface_traffic', {
                                'router_id': router_id,
                                'traffic': traffic_data,
                                'timestamp': now
                            }, room=f"router_{router_id}")

                    # CLIENT STATUS & TRAFFIC (Cada ciclo para máxima fluidez)
                    router_monitored_clients = list(self.monitored_clients.get(router_id, []))
                    if router_monitored_clients:
                        logger.debug(f"Monitor {router_id}: Processing traffic for {len(router_monitored_clients)} clients...")
                        client_traffic = self.get_router_clients_traffic(router_id, router_monitored_clients, adapter)
                        if client_traffic and self.socketio:
                            logger.debug(f"📤 Emitting client traffic for router {router_id}: {len(client_traffic)} clients")
                            # Emitir tanto global como al cuarto del router
                            self.socketio.emit('client_traffic', client_traffic, room=f"router_{router_id}")
                            self.socketio.emit('client_traffic', client_traffic)

                    # DASHBOARD GLOBAL TRAFFIC
                    dashboard_ifaces = self.dashboard_interfaces.get(router_id, [])
                    if dashboard_ifaces:
                        total_tx = 0
                        total_rx = 0
                        for iface in dashboard_ifaces:
                            if iface in traffic_data:
                                total_tx += traffic_data[iface].get('tx', 0)
                                total_rx += traffic_data[iface].get('rx', 0)
                            else:
                                res = adapter.get_interface_traffic(iface)
                                total_tx += res.get('tx', 0)
                                total_rx += res.get('rx', 0)
                                    
                        if self.socketio:
                            self.socketio.emit('dashboard_traffic_update', {
                                'router_id': router_id,
                                'tx': total_tx,
                                'rx': total_rx,
                                'timestamp': now
                            })

                    # Check system resources (CPU/RAM) cada 2 segundos
                    if now - last_metrics_check >= 2.0:
                        last_metrics_check = now
                        system_info = adapter.get_system_info()
                        if self.socketio:
                            self.socketio.emit('router_metrics', {
                                'router_id': router_id,
                                'cpu': system_info.get('cpu_load', '0'),
                                'memory': system_info.get('memory_usage', 0),
                                'uptime': system_info.get('uptime', ''),
                                'timestamp': now
                            }, room=f"router_{router_id}")

                except Exception as e:
                    if not adapter._is_connected:
                        logger.warning(f"Conexión perdida con router {router_id} ({router.alias}). Reintentando...")
                        connected = adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port, timeout=5)
                        if not connected:
                            time.sleep(15) # Esperar más tiempo si sigue offline
                    else:
                        logger.error(f"Error en loop de monitoreo para router {router_id}: {e}")
                
                time.sleep(1.5) # Intervalo optimizado para reducir carga en MikroTik y CPU

        except Exception as e:
            logger.critical(f"Critical error in monitor thread for router {router_id}: {e}")
        finally:
            if adapter:
                adapter.disconnect()
            if router_id in self.router_sessions:
                del self.router_sessions[router_id]
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
                # Cachear metadata
                self.client_metadata_cache[client.id] = {
                    'username': client.username, 
                    'ip': client.ip_address,
                    'router_id': client.router_id
                }
                
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

    def get_router_clients_traffic(self, router_id: int, client_ids: List[int], adapter: MikroTikAdapter) -> Dict[str, Any]:
        """Versión optimizada que usa metadata cacheada"""
        results = {}
        try:
            try:
                missing_ids = [cid for cid in client_ids if cid not in self.client_metadata_cache]
                if missing_ids:
                    from src.infrastructure.database.models import Client
                    db = get_db()
                    missing_clients = db.session.query(Client).filter(Client.id.in_(missing_ids)).all()
                    for c in missing_clients:
                        self.client_metadata_cache[c.id] = {
                            'username': c.username,
                            'ip': c.ip_address,
                            'router_id': c.router_id,
                            'last_seen_cache': c.last_seen.isoformat() if c.last_seen else None
                        }
                    db.remove_session()
            except Exception as e:
                logger.error(f"Error fetching missing metadata in get_router_clients_traffic: {e}")

            # 2. Obtener sesiones PPPoE
            try:
                active_sessions = adapter.get_active_pppoe_sessions()
            except Exception as e:
                logger.error(f"Error fetching pppoe sessions: {e}")
                active_sessions = {}
                
            active_map_lower = {k.lower(): k for k in active_sessions.keys()}
            
            # 3. Obtener Tabla ARP
            try:
                arp_table = adapter.get_arp_table()
            except Exception as e:
                logger.error(f"Error fetching ARP table: {e}")
                arp_table = []
                
            valid_arp_ips = set()
            for arp in arp_table:
                # Filtrar estados que indican desconexión aunque la entrada exista
                # Status comunes: DC (dynamic complete), failed, incomplete
                status = arp.get('status', '').lower()
                if arp.get('address') and status != 'failed' and status != 'incomplete':
                    valid_arp_ips.add(arp.get('address'))
            
            # 4. Obtener DHCP Leases
            try:
                dhcp_leases = adapter.get_dhcp_leases()
            except Exception as e:
                logger.error(f"Error fetching DHCP leases: {e}")
                dhcp_leases = []
                
            bound_dhcp_ips = {lease.get('address') for lease in dhcp_leases if lease.get('address')}
            
            logger.debug(f"Monitor {router_id}: Found {len(active_sessions)} PPPoE, {len(valid_arp_ips)} Valid ARP, {len(bound_dhcp_ips)} Bound DHCP")
            
            try:
                queue_stats = adapter._api_connection.get_resource('/queue/simple').get()
            except Exception as e:
                logger.error(f"Error fetching Queue stats: {e}")
                queue_stats = []
                
            queue_map = {}
            queue_by_ip = {}
            
            for q in queue_stats:
                name = q.get('name', '').lower()
                target = q.get('target', '')
                ip = target.split('/')[0] if '/' in target else target
                rate = q.get('rate', '0/0')
                try:
                    u, d = rate.split('/')
                    up, dw = int(u), int(d)
                except:
                    up, dw = 0, 0
                
                info = {'ip': ip, 'up': up, 'dw': dw, 'dis': q.get('disabled') == 'true'}
                queue_map[name] = info
                if ip: queue_by_ip[ip] = info

            online_count = 0
            online_pppoe_names = []
            client_id_to_pppoe = {}
            for c_id in client_ids:
                meta = self.client_metadata_cache.get(c_id)
                if not meta: continue
                
                user_lower = meta['username'].lower()
                c_ip = meta['ip']
                is_online, uptime, up, dw, ip = False, None, 0, 0, c_ip
                
                # A. VERIFICACIÓN PPPoE (Prioridad 1)
                if user_lower in active_map_lower:
                    is_online = True
                    real_name = active_map_lower[user_lower]
                    sess = active_sessions[real_name]
                    uptime, ip = sess.get('uptime'), sess.get('ip') or c_ip
                    
                    # Guardar nombre real para monitoreo de tráfico preciso
                    meta['real_iface_name'] = real_name
                    
                    # Optimización: Usar stats de colas si están disponibles
                    q_candidates = [real_name, real_name.lower(), f"<pppoe-{user_lower}>", f"pppoe-{user_lower}", user_lower]
                    matched_q = None
                    for cand in q_candidates:
                        if cand in queue_map:
                            matched_q = queue_map[cand]
                            break
                    
                    if matched_q:
                        up, dw = matched_q['up'], matched_q['dw']
                    else:
                        online_pppoe_names.append(real_name)
                        client_id_to_pppoe[c_id] = real_name
                        
                # B. VERIFICACIÓN ESTÁTICA / DHCP (Prioridad 2)
                # Solo online si tiene ARP válido O DHCP Bound
                elif (c_ip and (c_ip in valid_arp_ips or c_ip in bound_dhcp_ips)):
                    # Verificamos si realmente hay actividad física
                    is_online = True
                    q = queue_map.get(user_lower) or queue_by_ip.get(c_ip)
                    if q:
                        ip, up, dw = q.get('ip') or c_ip, q.get('up', 0), q.get('dw', 0)
                
                # C. FALLBACK: Si no está en ARP/DHCP pero tiene una cola activa con tráfico REAL
                # Esto detecta clientes con IPs estáticas que no están en el cache ARP en este instante
                if not is_online:
                    # Siempre buscar por IP primero para colas estáticas
                    q = queue_by_ip.get(c_ip) or queue_map.get(user_lower)
                    if q and (q.get('up', 0) > 0 or q.get('dw', 0) > 0):
                        is_online = True
                        ip, up, dw = q.get('ip') or c_ip, q.get('up', 0), q.get('dw', 0)
                        logger.debug(f"Monitor {router_id}: Client {user_lower} detected ONLINE via Queue traffic fallback.")
                


                if is_online: 
                    online_count += 1
                    # Si está online, actualizamos el cache de last_seen a ahora
                    self.client_metadata_cache[c_id]['last_seen_cache'] = datetime.now().isoformat()
                
                # Obtener last_seen del cache (evita queries pesadas a la BD en cada ciclo)
                db_last_seen = self.client_metadata_cache[c_id].get('last_seen_cache')

                results[str(c_id)] = {
                    'status': 'online' if is_online else 'offline',
                    'uptime': uptime,
                    'ip_address': ip,
                    'upload': up,
                    'download': dw,
                    'last_seen': db_last_seen
                }

            # ----------------------------------------------------------------------
            # C. MEJORA: TRÁFICO EN TIEMPO REAL (Monitor-Traffic)
            # Reemplaza los ceros estáticos por valores reales de ráfaga
            # ----------------------------------------------------------------------
            online_ids = [cid for cid, res in results.items() if res['status'] == 'online']
            if online_ids:
                # 1. Recopilar nombres de interfaces potenciales (PPPoE & Queues)
                names_to_monitor = []
                id_to_name_map = {}
                
                for cid_str in online_ids:
                    cid = int(cid_str)
                    meta = self.client_metadata_cache.get(cid)
                    if not meta: continue
                    
                    # Si es PPPoE, usamos el nombre real de la interface dinámica
                    real_name = meta.get('real_iface_name')
                    user = meta['username']
                    
                    if real_name:
                        patterns = [real_name]
                    else:
                        # Para Simple Queues, el nombre suele ser el username o <username>
                        patterns = [user, f"<{user}>", f"pppoe-{user}", f"<pppoe-{user}>"]
                        
                    for p in patterns:
                        names_to_monitor.append(p)
                        id_to_name_map[p] = cid_str

                if names_to_monitor:
                    # Usar el adapter para monitorear tráfico real de estas "interfaces"
                    # Nota: monitor-traffic una sola vez es eficiente
                    real_traffic = adapter.get_bulk_traffic(names_to_monitor)
                    for iface_name, traffic in real_traffic.items():
                        cid_str = id_to_name_map.get(iface_name)
                        if cid_str and cid_str in results:
                            # Asegurar que traffic tenga los campos necesarios
                            up_val = traffic.get('upload', 0)
                            dw_val = traffic.get('download', 0)
                            
                            # Solo sobreescribir si el valor es mayor a cero para evitar parpadeos
                            # o si el valor previo era Cero
                            if up_val > 0 or dw_val > 0 or results[cid_str].get('upload') == 0:
                                results[cid_str]['upload'] = up_val
                                results[cid_str]['download'] = dw_val

            # Obtener estadísticas globales de DHCP para el Dashboard
            dhcp_stats = adapter.get_dhcp_stats()
            
            logger.debug(f"Monitor {router_id}: Traffic results for {len(results)} clients ({online_count} online). Router Stats: {dhcp_stats}")
            
            # Inyectar estadísticas globales en el resultado
            results['__stats__'] = {
                'router_id': router_id,
                'total_leases': dhcp_stats.get('total', 0),
                'online_leases': dhcp_stats.get('bound', 0),
                'offline_leases': dhcp_stats.get('waiting', 0)
            }
            
            # ----------------------------------------------------------------------
            # BACKGROUND SYNC: Persistir estado ONLINE en Base de Datos (Cada 10s)
            # ----------------------------------------------------------------------
            current_time = time.time()
            if current_time - self.last_db_sync.get(router_id, 0) > 10.0:
                 self.last_db_sync[router_id] = current_time
                 
                 # Fetch metadata extra (Offline Last Seen) every 60s approx
                 # We simply check if it's been a while, or use the same cycle but lighter
                 offline_metadata = {}
                 if current_time - getattr(self, f"last_offline_check_{router_id}", 0) > 60.0:
                     setattr(self, f"last_offline_check_{router_id}", current_time)
                     try:
                        logger.info(f"Monitor {router_id}: Fetching detailed Last Seen info from Mikrotik...")
                        offline_metadata = adapter.get_all_last_seen()
                     except Exception as e:
                        logger.warning(f"Failed to fetch offline metadata: {e}")

                 # Run DB sync in a separate thread to avoid blocking the monitoring loop
                 threading.Thread(
                     target=self.update_clients_online_status,
                     args=(router_id, results, offline_metadata),
                     daemon=True
                 ).start()

        except Exception as e:
            logger.error(f"Error monitoring clients on router {router_id}: {e}", exc_info=True)
            
        return results

    def _smart_parse_time(self, time_str: str) -> Optional[datetime]:
        """Intelligently parses Mikrotik time into naive UTC datetime. 
        Supports: '10m30s', '24d 06:36:28', 'oct/11/2021 14:23:45', '2023-01-01 10:00:00'
        """
        if not time_str or time_str.lower() == 'never': return None
        
        # 1. Intentar como fecha absoluta (Formato oct/11/2023...)
        dt = self._parse_ppp_time(time_str)
        if dt: return dt
        
        # 2. Intentar como duración relativa (Formato 24d 06:36:28...)
        try:
            import re
            from datetime import timedelta
            s = time_str.strip().lower()
            total_seconds = 0
            
            # W y D
            w_match = re.search(r'(\d+)\s*w', s)
            d_match = re.search(r'(\d+)\s*d', s)
            if w_match: total_seconds += int(w_match.group(1)) * 604800
            if d_match: total_seconds += int(d_match.group(1)) * 86400
            
            # Quitar parte de dias/semanas
            remaining = re.sub(r'\d+\s*[wd]', '', s).strip()
            
            if ':' in remaining:
                parts = [int(x) for x in remaining.split(':')]
                if len(parts) == 3: total_seconds += parts[0] * 3600 + parts[1] * 60 + parts[2]
                elif len(parts) == 2: total_seconds += parts[0] * 60 + parts[1]
            else:
                for unit, mult in [('h', 3600), ('m', 60), ('s', 1)]:
                    match = re.search(fr'(\d+)\s*{unit}', remaining)
                    if match: total_seconds += int(match.group(1)) * mult
            
            if total_seconds > 0:
                return datetime.now() - timedelta(seconds=total_seconds)
        except:
            pass
            
        return None

    def _parse_ppp_time(self, time_str: str) -> Optional[datetime]:
        """Parses Mikrotik absolute time string (e.g. 'sep/02/2023 14:00:00')"""
        if not time_str: return None
        try:
            # Formatos comunes: "mmm/dd/yyyy HH:MM:SS"
            # Python strptime no soporta 'sep', 'oct' locale-aware reliable defaults easily without setlocale
            # Manual map
            months = {'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6, 
                      'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12}
            
            parts = time_str.split(' ')
            if len(parts) != 2: return None
            
            date_part, time_part = parts
            date_subparts = date_part.split('/')
            
            if len(date_subparts) == 3:
                m_str, d_str, y_str = date_subparts
            elif len(date_subparts) == 2:
                m_str, d_str = date_subparts
                y_str = str(datetime.now().year)
            else:
                return None
            
            month = months.get(m_str.lower())
            if not month: return None
            
            dt_str = f"{y_str}-{month:02d}-{int(d_str):02d} {time_part}"
            return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        except:
            return None

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

            client_updates = []

            for client_id_str, info in traffic_results.items():
                if not client_id_str.isdigit(): continue
                
                cid = int(client_id_str)
                if cid not in client_map: continue
                
                client = client_map[cid]
                is_online = (info.get('status') == 'online')
                
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
                        last_seen_dt = None
                        
                        # Buscar por IP (Prioridad 1)
                        if client.ip_address and client.ip_address in offline_metadata:
                            last_seen_dt = self._smart_parse_time(offline_metadata[client.ip_address])
                        
                        # Buscar por Username (Prioridad 2)
                        if not last_seen_dt and client.username and client.username in offline_metadata:
                            last_seen_dt = self._smart_parse_time(offline_metadata[client.username])
                        
                        # Buscar por MAC (Prioridad 3)
                        if not last_seen_dt and hasattr(client, 'mac_address') and client.mac_address and client.mac_address in offline_metadata:
                            last_seen_dt = self._smart_parse_time(offline_metadata[client.mac_address])
                             
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
