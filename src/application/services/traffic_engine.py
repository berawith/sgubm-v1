"""
Traffic Surgical Engine v2.0
Módulo especializado en la extracción y procesamiento de datos de MikroTik.
Este motor está diseñado para ser invocado por el MonitoringManager y no depende de WebSockets.
"""
import logging
from typing import List, Dict, Set, Optional
from cachetools import TTLCache

logger = logging.getLogger(__name__)

class TrafficSurgicalEngine:
    def __init__(self):
        # Caché de metadatos con Time-To-Live (10 minutos) para evitar consultas constantes a DB
        self.metadata_cache = TTLCache(maxsize=2000, ttl=600)
        
    def get_snapshot(self, adapter, client_ids: List[int], db_session_factory, 
                     raw_ifaces: List[Dict] = None, raw_queues: List[Dict] = None) -> Dict[str, Dict]:
        """
        Punto de entrada principal: Obtiene el estado y tráfico de una lista de clientes.
        """
        if not getattr(adapter, '_is_connected', False):
            return {}
            
        try:
            # 1. Asegurar Metadata (Sincronización con DB local)
            self._ensure_metadata(client_ids, db_session_factory)
            
            # 2. Obtener Datos Base del Router (Surgical)
            # Fetch interfaces and queues in one go if not provided
            if raw_ifaces is None:
                raw_ifaces = self._fetch_interfaces(adapter)
            if raw_queues is None:
                raw_queues = self._fetch_queues(adapter)
            
            # 3. Obtener Estado de Conexión (PPPoE, ARP, DHCP)
            active_pppoe = self._fetch_pppoe(adapter)
            active_arp = self._fetch_arp(adapter)
            active_dhcp = self._fetch_dhcp(adapter)
            
            # 4. Procesar y Mapear
            # Convertir raw data en mapas de búsqueda rápida
            queue_map = self._build_queue_map(raw_queues)
            iface_map = self._build_iface_map(raw_ifaces)
            
            results = {}
            for cid in client_ids:
                meta = self.metadata_cache.get(cid)
                if not meta: continue
                
                results[cid] = self._resolve_client_data(
                    meta, 
                    active_pppoe, active_arp, active_dhcp,
                    queue_map, iface_map
                )
                
            return results
        except Exception as e:
            logger.error(f"Error crítico en TrafficSurgicalEngine.get_snapshot para {len(client_ids)} clientes: {e}")
            # NO retornar {} silenciosamente, dejar que el error suba o marcarlo como fallido
            raise e

    def _ensure_metadata(self, client_ids: List[int], db_session_factory):
        missing_ids = [cid for cid in client_ids if cid not in self.metadata_cache]
        if missing_ids:
            session = db_session_factory()
            try:
                from src.infrastructure.database.models import Client
                clients = session.query(Client).filter(Client.id.in_(missing_ids)).all()
                for c in clients:
                    self.metadata_cache[c.id] = {
                        'id': c.id,
                        'user': c.username,
                        'name': c.legal_name,
                        'ip': c.ip_address,
                        'q_name': c.mikrotik_queue_name,
                        'iface_name': c.mikrotik_interface_name,
                        'status_db': c.status
                    }
            finally:
                session.close()

    def _fetch_interfaces(self, adapter) -> List[Dict]:
        try:
            return adapter._get_resource('/interface').call('print', {".proplist": "name,disabled,last-link-up-time"})
        except Exception as e:
            logger.warning(f"Surgical fetch_interfaces failed: {e}")
            raise e

    def _fetch_queues(self, adapter) -> List[Dict]:
        try:
            return adapter._get_resource('/queue/simple').call('print', {".proplist": "name,target,rate,max-limit,disabled"})
        except Exception as e:
            logger.warning(f"Surgical fetch_queues failed: {e}")
            raise e

    def _fetch_pppoe(self, adapter) -> Set[str]:
        try:
            sessions = adapter.get_active_pppoe_sessions()
            return {s.lower() for s in sessions.keys()}
        except Exception as e:
            logger.warning(f"Surgical fetch_pppoe failed: {e}")
            raise e

    def _fetch_arp(self, adapter) -> Set[str]:
        try:
            arp = adapter.get_arp_table()
            return {a.get('address') for a in arp if a.get('address') and a.get('status', '').lower() not in ['failed', 'incomplete']}
        except Exception as e:
            logger.warning(f"Surgical fetch_arp failed: {e}")
            raise e

    def _fetch_dhcp(self, adapter) -> Set[str]:
        try:
            leases = adapter.get_dhcp_leases()
            return {l.get('address') for l in leases if l.get('address') and l.get('status') == 'bound'}
        except Exception as e:
            logger.warning(f"Surgical fetch_dhcp failed: {e}")
            raise e

    def _build_queue_map(self, raw_queues: List[Dict]) -> Dict[str, Dict]:
        q_map = {}
        for q in raw_queues:
            name = q.get('name', '').lower()
            if not name: continue
            
            rate = q.get('rate', '0/0')
            try:
                u, d = rate.split('/')
                up, dw = int(u), int(d)
            except:
                up, dw = 0, 0
                
            target = q.get('target', '')
            ip = target.split('/')[0] if '/' in target else target
            
            q_map[name] = {
                'up': up, 'dw': dw, 'ip': ip, 'dis': q.get('disabled') == 'true'
            }
        return q_map

    def _build_iface_map(self, raw_ifaces: List[Dict]) -> Dict[str, Dict]:
        # Para status de interfaces físicas/dinámicas
        return {i.get('name').lower(): i for i in raw_ifaces if i.get('name')}

    def _resolve_client_data(self, meta, pppoe, arp, dhcp, q_map, iface_map) -> Dict:
        """Determina status y tráfico de un cliente individual"""
        cid = meta['id']
        username = (meta['user'] or '').lower()
        ip = meta['ip']
        q_name = (meta['q_name'] or '').lower()
        
        # 1. DETERMINAR STATUS ONLINE
        is_online = False
        method = "none"
        
        if username and username in pppoe:
            is_online = True
            method = "pppoe"
        elif ip and ip in arp:
            is_online = True
            method = "arp"
        elif ip and ip in dhcp:
            is_online = True
            method = "dhcp"
            
        # 2. CAPTURAR TRÁFICO
        # Priorizar por nombre de cola (más exacto) -> IP en colas -> Interfaz
        up, dw = 0, 0
        
        # A. Por nombre de cola
        target_q = (
            q_map.get(q_name) or 
            q_map.get(username) or 
            q_map.get(f"<pppoe-{username}>") or
            (q_map.get(meta['name'].lower()) if meta['name'] else None)
        )
        
        if target_q:
            up, dw = target_q['up'], target_q['dw']
        elif ip:
            # B. Buscar en mapa de colas por IP (fallback si el nombre cambió)
            for name, qinfo in q_map.items():
                if qinfo['ip'] == ip:
                    up, dw = qinfo['up'], qinfo['dw']
                    break
        
        return {
            'id': cid,
            'status': 'online' if is_online else 'offline',
            'upload': up,
            'download': dw,
            'method': method
        }
