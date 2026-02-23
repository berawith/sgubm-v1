"""
MikroTik Service Adapter
Implementación concreta de INetworkService para routers MikroTik
Este módulo es completamente intercambiable - se puede crear CiscoAdapter, UbiquitiAdapter, etc.
"""
from typing import Dict, Any, Optional, List, Set
import logging
from routeros_api import RouterOsApiPool
from routeros_api.exceptions import RouterOsApiConnectionError, RouterOsApiCommunicationError

from src.core.interfaces.contracts import INetworkService
from src.core.domain.entities import ManagementMethod

logger = logging.getLogger(__name__)


class MikroTikAdapter(INetworkService):
    """
    Adaptador para comunicación con routers MikroTik
    Implementa la interfaz INetworkService
    """
    
    def __init__(self):
        self._connection_pool: Optional[RouterOsApiPool] = None
        self._api_connection = None
        self._host: str = ""
        self._is_connected: bool = False
    
    def connect(self, host: str, username: str, password: str, port: int = 8728, timeout: int = 10) -> bool:
        """
        Establece conexión con el router MikroTik
        """
        import socket
        
        try:
            self._host = host
            
            # 1. Pre-Chequeo de conexión con Socket Crudo (Evita colgarse si está offline)
            # Esto reemplaza el uso peligroso de socket.setdefaulttimeout() que afecta hilos globales
            try:
                # Intenta abrir un socket TCP simple. Si falla por timeout, el router está offline.
                s = socket.create_connection((host, port), timeout=timeout)
                s.close()
            except (socket.timeout, ConnectionRefusedError, OSError) as e:
                logger.warning(f"Router {host}:{port} unreachable (Pre-check): {e}")
                self._is_connected = False
                return False

            # 2. Iniciar sesión API con RouterOsApiPool (Modo Bloqueante Seguro)
            # Al confirmar conectividad arriba, podemos dejar que la librería use blocking sockets
            # para operaciones largas (como Sync) sin riesgo de corrupción WinError 10038
            self._connection_pool = RouterOsApiPool(
                host=host,
                username=username,
                password=password,
                port=port,
                plaintext_login=True
            )
            self._api_connection = self._connection_pool.get_api()
            self._is_connected = True
            logger.info(f"Connected to MikroTik router at {host}:{port}")
            return True
        
        except Exception as e:
            logger.error(f"Error connecting to {host}: {str(e)}")
            self._is_connected = False
            return False
    
    def disconnect(self) -> None:
        """Cierra la conexión"""
        if self._connection_pool:
            try:
                self._connection_pool.disconnect()
                self._is_connected = False
                logger.info(f"Disconnected from {self._host}")
            except Exception as e:
                logger.error(f"Error disconnecting: {str(e)}")
    
    def discover_configuration(self) -> Dict[str, Any]:
        """
        Analiza el router y detecta su configuración
        Retorna métodos de gestión, segmentos de red, planes, etc.
        """
        if not self._is_connected:
            raise ConnectionError("Not connected to router")
        
        configuration = {
            "methods": [],
            "network_segments": [],
            "detected_plans": [],
            "interfaces": [],
            "system_info": {}
        }
        
        try:
            # Detectar System Info
            resource = self._api_connection.get_resource('/system/resource')
            system_info_list = resource.get()
            
            if system_info_list:
                sys_data = system_info_list[0]
                
                # Calcular uso de memoria
                total_mem = int(sys_data.get("total-memory", 0))
                free_mem = int(sys_data.get("free-memory", 0))
                mem_usage = 0
                if total_mem > 0:
                    mem_usage = int(((total_mem - free_mem) / total_mem) * 100)
                
                configuration["system_info"] = {
                    "platform": sys_data.get("platform", ""),
                    "board_name": sys_data.get("board-name", ""),
                    "version": sys_data.get("version", ""),
                    "uptime": sys_data.get("uptime", ""),
                    "cpu_load": sys_data.get("cpu-load", "0"),
                    "memory_usage": mem_usage
                }
            else:
                configuration["system_info"] = {"uptime": "N/A", "cpu_load": 0, "memory_usage": 0}
            
            # Detectar PPPoE
            pppoe_config = self._detect_pppoe()
            if pppoe_config["enabled"]:
                configuration["methods"].append(ManagementMethod.PPPOE.value)
                configuration["detected_plans"].extend(pppoe_config["profiles"])
                configuration["network_segments"].extend(pppoe_config["pools"])
            
            # Detectar Hotspot
            hotspot_config = self._detect_hotspot()
            if hotspot_config["enabled"]:
                configuration["methods"].append(ManagementMethod.HOTSPOT.value)
                configuration["detected_plans"].extend(hotspot_config["profiles"])
            
            # Detectar Simple Queues
            queues_config = self._detect_simple_queues()
            if queues_config["enabled"]:
                configuration["methods"].append(ManagementMethod.SIMPLE_QUEUE.value)
                configuration["detected_plans"].extend(queues_config["queue_types"])
            
            # Detectar PCQ
            pcq_config = self._detect_pcq()
            if pcq_config["enabled"]:
                configuration["methods"].append(ManagementMethod.PCQ.value)
            
            # Detectar interfaces de red
            interfaces = self._api_connection.get_resource('/interface')
            for iface in interfaces.get():
                configuration["interfaces"].append({
                    "name": iface.get("name", ""),
                    "type": iface.get("type", ""),
                    "running": iface.get("running", False)
                })
            
            # --- CONTEO DE CLIENTES ACTIVOS REALES ---
            active_clients_count = 0
            try:
                # Contar PPPoE Activos
                ppp_active = self._api_connection.get_resource('/ppp/active')
                ppp_list = ppp_active.get()
                active_clients_count += len(ppp_list) if ppp_list else 0
                
                # Contar Hotspot Activos
                hotspot_active = self._api_connection.get_resource('/ip/hotspot/active')
                hs_list = hotspot_active.get()
                active_clients_count += len(hs_list) if hs_list else 0
                
                # Contar Simple Queues Activas (clientes con IP)
                try:
                    queues = self._api_connection.get_resource('/queue/simple').get()
                    arp_table = self._api_connection.get_resource('/ip/arp').get()
                    arp_ips = {arp.get('address') for arp in arp_table if arp.get('address')}
                    
                    # Contar queues activas: no disabled, con IP, y la IP está en ARP
                    for q in queues:
                        if q.get('disabled') == 'true':
                            continue
                        if q.get('dynamic') == 'true':  # Excluir colas dinámicas de PPPoE
                            continue
                        
                        target = q.get('target', '')
                        ip = target.split('/')[0] if target else ''
                        
                        # Si la IP está en ARP, el cliente está realmente conectado
                        if ip and ip in arp_ips:
                            active_clients_count += 1
                            
                except Exception as e:
                    logger.debug(f"Error counting Simple Queues: {e}")
                
                # Guardamos este dato en system_info para que el controlador lo use
                configuration["system_info"]["active_connections"] = active_clients_count
                logger.info(f"Active connections detected: {active_clients_count}")
                
            except Exception as e:
                logger.warning(f"Error counting active clients: {e}")
                configuration["system_info"]["active_connections"] = 0
            # ----------------------------------------
            
            logger.info(f"Configuration discovered: {len(configuration['methods'])} methods detected")
            return configuration
            
        except Exception as e:
            logger.error(f"Error discovering configuration: {str(e)}")
            raise
    
    def _detect_pppoe(self) -> Dict[str, Any]:
        """Detecta configuración de PPPoE"""
        try:
            profiles = self._api_connection.get_resource('/ppp/profile')
            secrets = self._api_connection.get_resource('/ppp/secret')
            pools = self._api_connection.get_resource('/ip/pool')
            
            profile_list = profiles.get()
            secret_list = secrets.get()
            pool_list = pools.get()
            
            detected_profiles = []
            detected_pools = []
            
            for profile in profile_list:
                detected_profiles.append({
                    "name": profile.get("name", ""),
                    "local_address": profile.get("local-address", ""),
                    "remote_address": profile.get("remote-address", ""),
                    "rate_limit": profile.get("rate-limit", "")
                })
            
            for pool in pool_list:
                detected_pools.append({
                    "name": pool.get("name", ""),
                    "ranges": pool.get("ranges", "")
                })
            
            return {
                "enabled": len(secret_list) > 0,
                "profiles": detected_profiles,
                "pools": detected_pools,
                "client_count": len(secret_list)
            }
            
        except Exception as e:
            logger.error(f"Error detecting PPPoE: {str(e)}")
            return {"enabled": False, "profiles": [], "pools": []}

    def create_ppp_profile(self, name: str, rate_limit: str, local_address: str = None, remote_address: str = None) -> bool:
        """Crea o actualiza un perfil PPPoE"""
        if not self._is_connected: return False

        try:
            profiles = self._api_connection.get_resource('/ppp/profile')
            existing = profiles.get(name=name)
            
            params = {
                "name": name,
                "rate-limit": rate_limit,
                "only-one": "default", 
                "use-mpls": "default",
                "use-compression": "default",
                "use-encryption": "default"
            }
            if local_address: params["local-address"] = local_address
            if remote_address: params["remote-address"] = remote_address
            
            if existing:
                # Update existing (safe override)
                profiles.set(id=existing[0]['id'], **params)
                logger.info(f"PPPoE Profile '{name}' updated with limit {rate_limit}")
            else:
                # Create new
                profiles.add(**params)
                logger.info(f"PPPoE Profile '{name}' created with limit {rate_limit}")
                
            return True
        except Exception as e:
            logger.error(f"Error managing PPPoE Profile '{name}': {e}")
            return False

    
    def _detect_hotspot(self) -> Dict[str, Any]:
        """Detecta configuración de Hotspot"""
        try:
            servers = self._api_connection.get_resource('/ip/hotspot')
            users = self._api_connection.get_resource('/ip/hotspot/user')
            profiles = self._api_connection.get_resource('/ip/hotspot/user/profile')
            
            server_list = servers.get()
            user_list = users.get()
            profile_list = profiles.get()
            
            detected_profiles = []
            for profile in profile_list:
                detected_profiles.append({
                    "name": profile.get("name", ""),
                    "rate_limit": profile.get("rate-limit", "")
                })
            
            return {
                "enabled": len(server_list) > 0,
                "profiles": detected_profiles,
                "client_count": len(user_list)
            }
            
        except Exception as e:
            logger.error(f"Error detecting Hotspot: {str(e)}")
            return {"enabled": False, "profiles": []}
    
    def _detect_simple_queues(self) -> Dict[str, Any]:
        """Detecta configuración de Simple Queues"""
        try:
            queues = self._api_connection.get_resource('/queue/simple')
            queue_list = queues.get()
            
            queue_types = {}
            for queue in queue_list:
                max_limit = queue.get("max-limit", "")
                if max_limit not in queue_types:
                    queue_types[max_limit] = {
                        "max_limit": max_limit,
                        "count": 0
                    }
                queue_types[max_limit]["count"] += 1
            
            return {
                "enabled": len(queue_list) > 0,
                "queue_types": list(queue_types.values()),
                "total_queues": len(queue_list)
            }
            
        except Exception as e:
            logger.error(f"Error detecting Simple Queues: {str(e)}")
            return {"enabled": False, "queue_types": []}
    
    def _detect_pcq(self) -> Dict[str, Any]:
        """Detecta configuración de PCQ"""
        try:
            queue_types = self._api_connection.get_resource('/queue/type')
            type_list = queue_types.get()
            
            pcq_types = [qt for qt in type_list if qt.get("kind", "") == "pcq"]
            
            return {
                "enabled": len(pcq_types) > 0,
                "pcq_count": len(pcq_types)
            }
            
        except Exception as e:
            logger.error(f"Error detecting PCQ: {str(e)}")
            return {"enabled": False}
    
    def create_client_service(self, client_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Crea servicio para un cliente según el método especificado
        """
        method = client_data.get("management_method")
        
        if method == ManagementMethod.PPPOE.value:
            return self._create_pppoe_client(client_data)
        elif method == ManagementMethod.HOTSPOT.value:
            return self._create_hotspot_client(client_data)
        elif method == ManagementMethod.SIMPLE_QUEUE.value:
            return self._create_queue_client(client_data)
        else:
            raise ValueError(f"Unsupported management method: {method}")
    
    def _create_pppoe_client(self, client_data: Dict[str, Any]) -> Dict[str, Any]:
        """Crea cliente PPPoE"""
        try:
            secrets = self._api_connection.get_resource('/ppp/secret')
            
            secret_params = {
                "name": client_data["username"],
                "password": client_data["password"],
                "service": "pppoe",
                "profile": client_data.get("profile", "default"),
                "comment": "" # Clean Winbox: No comments
            }
            
            if "local_address" in client_data:
                secret_params["local-address"] = client_data["local_address"]
            if "remote_address" in client_data:
                secret_params["remote-address"] = client_data["remote_address"]
            
            result = secrets.add(**secret_params)
            logger.info(f"PPPoE client created: {client_data['username']}")
            
            return {
                "success": True,
                "mikrotik_id": result.get("ret", ""),
                "method": "pppoe",
                "details": secret_params
            }
            
        except Exception as e:
            logger.error(f"Error creating PPPoE client: {str(e)}")
            raise
    
    def _create_hotspot_client(self, client_data: Dict[str, Any]) -> Dict[str, Any]:
        """Crea cliente Hotspot"""
        try:
            users = self._api_connection.get_resource('/ip/hotspot/user')
            
            user_params = {
                "name": client_data["username"],
                "password": client_data["password"],
                "profile": client_data.get("profile", "default"),
                "comment": "" # Clean Winbox: No comments
            }
            
            result = users.add(**user_params)
            logger.info(f"Hotspot client created: {client_data['username']}")
            
            return {
                "success": True,
                "mikrotik_id": result.get("ret", ""),
                "method": "hotspot",
                "details": user_params
            }
            
        except Exception as e:
            logger.error(f"Error creating Hotspot client: {str(e)}")
            raise
    
    def _create_queue_client(self, client_data: Dict[str, Any]) -> Dict[str, Any]:
        """Crea Simple Queue para cliente"""
        # Reutilizamos la lógica pública
        name = client_data.get("legal_name") or client_data.get("queue_name") or client_data["username"]
        target = client_data["target_address"]
        max_limit = client_data["max_limit"]
        
        # Extra params for full client creation
        burst_limit = client_data.get("burst_limit")
        burst_threshold = client_data.get("burst_threshold")
        burst_time = client_data.get("burst_time")
        
        success = self.create_simple_queue(name, target, max_limit, burst_limit, burst_threshold, burst_time)
        
        return {
            "success": success,
            "mikrotik_id": "", # No capturamos el ID en la versión pública simple
            "method": "simple_queue",
            "details": {"name": name, "target": target}
        }

    def create_simple_queue(self, name: str, target: str, max_limit: str, 
                          burst_limit: str = None, burst_threshold: str = None, burst_time: str = None) -> bool:
        """
        Crea una Simple Queue de forma directa.
        Útil para 'Fix Queue' o gestiones manuales.
        """
        try:
            queues = self._api_connection.get_resource('/queue/simple')
            
            queue_params = {
                "name": name,
                "target": target,
                "max-limit": max_limit,
                "comment": "" # Clean Winbox
            }
            
            if burst_limit:
                queue_params["burst-limit"] = burst_limit
                queue_params["burst-threshold"] = burst_threshold or ""
                queue_params["burst-time"] = burst_time or "8s/8s"
            
            # Verificar si existe para actualizar o crear
            existing = queues.get(name=name)
            if existing:
                queues.set(id=existing[0]['id'], **queue_params)
                logger.info(f"Simple Queue updated: {name}")
            else:
                queues.add(**queue_params)
                logger.info(f"Simple Queue created: {name}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error creating Simple Queue '{name}': {str(e)}")
            return False
    
    def ensure_cutoff_firewall_rules(self) -> bool:
        """
        Configura las reglas de firewall necesarias para manejar la lista IPS_BLOQUEADAS.
        Asegura que las reglas estén al INICIO del Filter para que sean efectivas.
        """
        if not self._is_connected:
            return False
            
        try:
            logger.info(f"MikroTik [{self._host}]: Verificando reglas de firewall para cortes...")
            filter_rules = self._api_connection.get_resource('/ip/firewall/filter')
            all_filters = filter_rules.get()
            
            # Definiciones de nuestras reglas
            rules_to_ensure = [
                {
                    'chain': 'forward',
                    'src-address-list': 'IPS_BLOQUEADAS',
                    'action': 'drop',
                    'comment': 'Bloquear servicio/internet a IPS_BLOQUEADAS'
                },
                {
                    'chain': 'input',
                    'src-address-list': 'IPS_BLOQUEADAS',
                    'action': 'drop',
                    'comment': 'Bloquear acceso al router a IPS_BLOQUEADAS'
                }
            ]
            
            for rule_def in rules_to_ensure:
                # 1. Buscar si ya existe la regla
                existing_rule = None
                for r in all_filters:
                    # Buscamos por comentario o por combinación técnica
                    # routeros-api devuelve las llaves tal cual las entrega MikroTik (con guiones)
                    comment = r.get('comment', '')
                    chain = r.get('chain', '')
                    src_list = r.get('src-address-list', '') or r.get('src_address_list', '')
                    action = r.get('action', '')

                    if comment == rule_def['comment']:
                        existing_rule = r
                        break
                    
                    if (chain == rule_def['chain'] and 
                        src_list == rule_def['src-address-list'] and 
                        action == rule_def['action']):
                        existing_rule = r
                        break
                
                if not existing_rule:
                    logger.info(f"MikroTik [{self._host}]: Creando regla faltante: {rule_def['comment']}")
                    # Crear la regla al inicio
                    add_params = {
                        'chain': rule_def['chain'],
                        'src-address-list': rule_def['src-address-list'],
                        'action': rule_def['action'],
                        'comment': rule_def['comment']
                    }
                    
                    # Solo usamos place-before si hay reglas existentes
                    if all_filters:
                        add_params['place-before'] = '0'
                        
                    filter_rules.add(**add_params)
                else:
                    #logger.debug(f"MikroTik [{self._host}]: Regla ya existe: {rule_def['comment']}")
                    pass

            return True
        except Exception as e:
            logger.error(f"Error configuring firewall rules in MikroTik [{self._host}]: {e}")
            return False

    def update_client_service(self, current_username: str, client_data: Dict[str, Any], old_ip: str = None) -> bool:
        """
        Actualiza la configuración del servicio del cliente en el MikroTik.
        Sincroniza el nombre en el campo 'Name' y maneja cambios de IP.
        """
        if not self._is_connected:
            return False
            
        success = True
        new_username = client_data.get('username')
        legal_name = client_data.get('legal_name')
        new_ip = client_data.get('ip_address')
        service_type = client_data.get('service_type', 'pppoe')
        
        # Helper para obtener ID de forma robusta
        def get_id(item):
            return item.get('id') or item.get('.id')

        # 1. ACTUALIZAR EN SIMPLE QUEUES
        try:
            queues = self._api_connection.get_resource('/queue/simple')
            q_target = None
            
            # Intentar buscar por nombre actual
            q_list = queues.get(name=current_username)
            if q_list:
                q_target = q_list[0]
            elif old_ip or new_ip:
                # FALLBACK: Buscar por IP Vieja o Nueva
                all_queues = queues.get()
                search_ips = [ip.split('/')[0] for ip in [old_ip, new_ip] if ip]
                for q in all_queues:
                    q_ip = q.get('target', '').split('/')[0]
                    if q_ip in search_ips:
                        q_target = q
                        break
            
            if q_target:
                target_id = get_id(q_target)
                if target_id:
                    update_params = {}
                    
                    if service_type == 'simple_queue' and legal_name:
                        update_params['name'] = legal_name
                    elif new_username:
                        update_params['name'] = new_username
                    
                    if new_ip and new_ip != '0.0.0.0' and new_ip != 'Dinámica':
                        # MikroTik requiere máscara (/32 usualmente)
                        update_params['target'] = f"{new_ip}/32" if '/' not in new_ip else new_ip
                    
                    update_params['comment'] = "" # Limpiar comentarios
                    
                    if update_params:
                        queues.set(id=target_id, **update_params)
                        logger.info(f"MikroTik: Simple Queue actualizada para {current_username} -> {new_ip}")
        except Exception as e:
            logger.error(f"Error updating Simple Queue in MikroTik: {e}")
            success = False

        # 2. ACTUALIZAR EN PPPOE SECRETS
        if service_type == 'pppoe':
            try:
                secrets = self._api_connection.get_resource('/ppp/secret')
                s_target = None
                
                s_list = secrets.get(name=current_username)
                if s_list:
                    s_target = s_list[0]
                elif old_ip or new_ip:
                    all_secrets = secrets.get()
                    search_ips = [old_ip, new_ip]
                    for s in all_secrets:
                        if s.get('remote-address') in search_ips:
                            s_target = s
                            break
                
                if s_target:
                    target_id = get_id(s_target)
                    if target_id:
                        update_params = {'comment': ""}
                        if new_username: update_params['name'] = new_username
                        if new_ip and new_ip != '0.0.0.0' and new_ip != 'Dinámica':
                            update_params['remote-address'] = new_ip
                        
                        if update_params:
                            secrets.set(id=target_id, **update_params)
                            logger.info(f"MikroTik: PPPoE Secret actualizada (ID: {target_id})")
            except Exception as e:
                logger.error(f"Error updating PPPoE Secret in MikroTik: {e}")
                success = False

        # 3. ACTUALIZAR DHCP LEASES
        if new_ip or old_ip or client_data.get('mac_address'):
            try:
                leases = self._api_connection.get_resource('/ip/dhcp-server/lease')
                search_ips = [ip for ip in [old_ip, new_ip] if ip]
                all_l = leases.get()
                l_targets = [l for l in all_l if l.get('address') in search_ips]
                
                for lease in l_targets:
                    tid = get_id(lease)
                    if tid:
                        upd = {'comment': ""}
                        if new_ip: upd['address'] = new_ip
                        if client_data.get('mac_address'): upd['mac-address'] = client_data.get('mac_address')
                        leases.set(id=tid, **upd)
                logger.info(f"MikroTik: DHCP Leases actualizados")
            except Exception as e:
                logger.error(f"Error updating DHCP Lease: {e}")

        # 4. ACTUALIZAR ADDRESS LISTS (Cortes/Suspensión)
        if old_ip and new_ip and old_ip != new_ip:
            try:
                addr_lists = self._api_connection.get_resource('/ip/firewall/address-list')
                clean_old = old_ip.split('/')[0]
                clean_new = new_ip.split('/')[0]
                
                # Buscar todas las entradas con la IP vieja
                old_entries = addr_lists.get(address=clean_old)
                for entry in old_entries:
                    tid = get_id(entry)
                    if tid:
                        # Mover a la nueva IP conservando la lista y el comentario (legal_name)
                        list_name = entry.get('list')
                        addr_lists.set(id=tid, address=clean_new)
                        logger.info(f"MikroTik: Movido de {clean_old} a {clean_new} en Address List '{list_name}'")
            except Exception as e:
                logger.error(f"Error updating Address Lists: {e}")

        return success
    
    def suspend_client_service(self, client_data: Dict[str, Any]) -> bool:
        """
        Suspende el servicio del cliente.
        Deshabilita el Secret/Queue, lo agrega a la Address List de BLOQUEADOS y patea la sesión si es PPPoE.
        """
        if not self._is_connected:
            return False
            
        username = client_data.get('username')
        ip_address = client_data.get('ip_address')
        legal_name = client_data.get('legal_name', username)
        service_type = client_data.get('service_type', 'pppoe')
        
        # Helper para obtener ID de forma robusta
        def get_id(item):
            return item.get('id') or item.get('.id')

        try:
            logger.info(f"🚫 Suspendiendo servicio MikroTik para {username} (IP original: {ip_address}, Tipo: {service_type})")
            
            # 0. Asegurar que las reglas de firewall existan
            self.ensure_cutoff_firewall_rules()

            # 1. Obtener IP real si es dinámica o PPPoE para asegurar el bloqueo en Firewall
            # Esto es CRÍTICO para que el corte sea efectivo
            real_ip = ip_address
            active_sessions = {}
            if service_type == 'pppoe' or not ip_address or ip_address == 'Dinámica' or ip_address == '0.0.0.0':
                active_sessions = self.get_active_pppoe_sessions()
                if username in active_sessions:
                    real_ip = active_sessions[username].get('ip')
                    if real_ip:
                         logger.info(f"📍 Detectada IP real activa para {username}: {real_ip}")

            # 2. Deshabilitar Secret/Queue
            if service_type == 'pppoe':
                resource = self._api_connection.get_resource('/ppp/secret')
            else:
                resource = self._api_connection.get_resource('/queue/simple')
                
            item = resource.get(name=username)
            if item:
                # Verificar si es dinámico (MikroTik no permite deshabilitar colas dinámicas directamente)
                is_dynamic = item[0].get('dynamic') == 'true'
                if is_dynamic:
                    logger.warning(f"La cola {service_type} '{username}' es DINÁMICA. No se puede deshabilitar físicamente, se omitirá este paso.")
                else:
                    target_id = get_id(item[0])
                    if target_id:
                        resource.set(id=target_id, disabled='yes', comment="")
                        logger.debug(f"Deshabilitado {service_type} para {username}")
            else:
                logger.warning(f"No se encontró {service_type} '{username}' para deshabilitar.")
            
            # 3. Agregar a Address List para redirección (Corte)
            target_ip_to_block = real_ip or ip_address
            if target_ip_to_block and target_ip_to_block not in ['Dinámica', '0.0.0.0']:
                clean_target_ip = target_ip_to_block.split('/')[0]
                addr_lists = self._api_connection.get_resource('/ip/firewall/address-list')
                
                # Verificar si YA EXISTE
                try:
                    target_entries = addr_lists.get(list='IPS_BLOQUEADAS', address=clean_target_ip)
                    if not target_entries:
                        addr_lists.add(list='IPS_BLOQUEADAS', address=clean_target_ip, comment=legal_name)
                        logger.info(f"MikroTik: IP {clean_target_ip} agregada a lista IPS_BLOQUEADAS")
                except Exception as e_list:
                    logger.error(f"Error al manipular Address List en suspensión: {e_list}")
            
            # 4. FORZAR DESCONEXIÓN (KICK) si es PPPoE
            # Esto obliga al router a cerrar la sesión y al firewall a aplicar la nueva regla IPS_BLOQUEADAS
            if service_type == 'pppoe':
                self.kick_ppp_active_session(username)
                
            return True
        except Exception as e:
            logger.error(f"Error suspendiendo cliente en MikroTik: {e}")
            return False

    def kick_ppp_active_session(self, username: str) -> bool:
        """
        Elimina la sesión activa de un usuario PPPoE para forzar reconexión o corte.
        """
        if not self._is_connected or not username:
            return False
            
        try:
            active_resource = self._api_connection.get_resource('/ppp/active')
            sessions = active_resource.get(name=username)
            
            if sessions:
                for session in sessions:
                    session_id = session.get('.id') or session.get('id')
                    if session_id:
                        active_resource.remove(id=session_id)
                        logger.info(f"⚡ PPPoE Session kicked for user: {username}")
                return True
            else:
                logger.debug(f"No active PPPoE session found for {username} to kick.")
                return False
        except Exception as e:
            logger.error(f"Error kicking PPPoE session for {username}: {e}")
            return False
    
    def restore_client_service(self, client_data: Dict[str, Any]) -> bool:
        """
        Restaura el servicio del cliente.
        Habilita el Secret/Queue y lo elimina de la Address List de SUSPENDIDOS.
        """
        if not self._is_connected:
            return False
            
        username = client_data.get('username')
        ip_address = client_data.get('ip_address')
        service_type = client_data.get('service_type', 'pppoe')
        
        # Helper para obtener ID de forma robusta
        def get_id(item):
            return item.get('id') or item.get('.id')

        try:
            logger.info(f"🔄 Restaurando servicio MikroTik para {username} (IP: {ip_address}, Tipo: {service_type})")
            
            # 1. Habilitar Secret/Queue
            if service_type == 'pppoe':
                resource = self._api_connection.get_resource('/ppp/secret')
            else:
                resource = self._api_connection.get_resource('/queue/simple')
                
            item = resource.get(name=username)
            if item:
                target_id = get_id(item[0])
                if target_id:
                    resource.set(id=target_id, disabled='no', comment="")
                    logger.debug(f"Habilitado {service_type} para {username}")
            else:
                logger.warning(f"No se encontró {service_type} '{username}' para habilitar.")
            
            # 2. Eliminar de Address List (LÓGICA ROBUSTA)
            if ip_address:
                # Normalizar IP buscando solo la base (sin máscara)
                clean_target_ip = ip_address.split('/')[0]
                
                addr_lists = self._api_connection.get_resource('/ip/firewall/address-list')
                # Obtenemos toda la lista de suscritos (suele ser pequeña comparado con total de reglas)
                # o al menos filtramos por nombre de lista para ser eficientes.
                try:
                    target_entries = addr_lists.get(list='IPS_BLOQUEADAS', address=clean_target_ip)
                    found = False
                    for entry in target_entries:
                        eid = get_id(entry)
                        if eid:
                            addr_lists.remove(id=eid)
                            logger.info(f"MikroTik: IP {clean_target_ip} ELIMINADA de IPS_BLOQUEADAS")
                            found = True
                    
                    if not found:
                        logger.debug(f"IP {clean_target_ip} no estaba en la lista IPS_BLOQUEADAS.")
                        
                except Exception as e_list:
                    logger.error(f"Error al manipular Address List en restauración: {e_list}")
                
            return True
        except Exception as e:
            logger.error(f"Error crítico restaurando cliente en MikroTik: {e}")
            return False
    
    def remove_client_service(self, client_data: Dict[str, Any]) -> bool:
        """
        Elimina por completo el servicio del cliente en el MikroTik.
        Elimina Secret PPPoE, Simple Queue, DHCP Lease y Address Lists.
        """
        if not self._is_connected:
            return False
            
        username = client_data.get('username')
        ip_address = client_data.get('ip_address')
        mac_address = client_data.get('mac_address')
        legal_name = client_data.get('legal_name')
        success = True

        # Helper para obtener ID de forma robusta
        def get_id(item):
            return item.get('.id') or item.get('id')

        # 1. Eliminar de PPP Secrets
        if username:
            try:
                secrets = self._api_connection.get_resource('/ppp/secret')
                s_list = secrets.get(name=username)
                if s_list:
                    for s in s_list:
                        sid = get_id(s)
                        if sid:
                            secrets.remove(id=sid)
                            logger.info(f"MikroTik: PPPoE Secret '{username}' eliminado")
            except Exception as e:
                logger.error(f"Error removiendo PPPoE Secret: {e}")
                success = False

        # 2. Eliminar de Simple Queues
        try:
            queues = self._api_connection.get_resource('/queue/simple')
            q_list = []
            
            # Buscar por nombre técnico (username)
            if username:
                q_list = queues.get(name=username)
            
            # Fallback 1: buscar por nombre legal
            if not q_list and legal_name:
                q_list = queues.get(name=legal_name)
            
            # Fallback 2: buscar por IP/Target
            if not q_list and ip_address:
                clean_ip = ip_address.split('/')[0]
                all_q = queues.get()
                q_list = [q for q in all_q if clean_ip in q.get('target', '')]
            
            if q_list:
                for q in q_list:
                    qid = get_id(q)
                    if qid:
                        queues.remove(id=qid)
                        logger.info(f"MikroTik: Simple Queue eliminada")
        except Exception as e:
            logger.error(f"Error removiendo Simple Queue: {e}")
            success = False

        # 3. Eliminar de DHCP Leases
        if ip_address or mac_address:
            try:
                leases = self._api_connection.get_resource('/ip/dhcp-server/lease')
                l_list = []
                if ip_address:
                    clean_ip = ip_address.split('/')[0]
                    # Búsqueda manual robusta en leases
                    all_leases = leases.get()
                    l_list = [l for l in all_leases if l.get('address', '').split('/')[0] == clean_ip]
                
                # Si no encontramos por IP, intentamos por MAC
                if not l_list and mac_address:
                    if not 'all_leases' in locals(): all_leases = leases.get()
                    l_list = [l for l in all_leases if l.get('mac-address', '').lower() == mac_address.lower()]
                
                if l_list:
                    for l in l_list:
                        lid = get_id(l)
                        if lid:
                            leases.remove(id=lid)
                            logger.info(f"MikroTik: DHCP Lease eliminado")
            except Exception as e:
                logger.error(f"Error removiendo DHCP Lease: {e}")

        # 4. Eliminar de TODAS las Address Lists donde aparezca la IP (ROBUSTO)
        if ip_address:
            try:
                clean_ip = ip_address.split('/')[0]
                addr_lists = self._api_connection.get_resource('/ip/firewall/address-list')
                all_entries = addr_lists.get()
                for entry in all_entries:
                    if entry.get('address', '').split('/')[0] == clean_ip:
                        eid = get_id(entry)
                        if eid:
                            list_name = entry.get('list', 'desconocida')
                            addr_lists.remove(id=eid)
                            logger.info(f"MikroTik: IP {clean_ip} removida de Address List '{list_name}'")
            except Exception as e:
                logger.error(f"Error removiendo de Address Lists: {e}")

        return success

    def remove_ppp_secret(self, username: str) -> bool:
        """Elimina un Secret PPPoE por nombre"""
        if not self._is_connected or not username: return False
        try:
            secrets = self._api_connection.get_resource('/ppp/secret')
            item = secrets.get(name=username)
            if item:
                secrets.remove(id=item[0].get('.id') or item[0].get('id'))
                return True
            return False
        except: return False

    def remove_simple_queue(self, name_or_ip: str) -> bool:
        """Elimina una Simple Queue por nombre o IP"""
        if not self._is_connected or not name_or_ip: return False
        try:
            queues = self._api_connection.get_resource('/queue/simple')
            item = queues.get(name=name_or_ip)
            if not item and '.' in name_or_ip: # Probable IP
                 clean_ip = name_or_ip.split('/')[0]
                 all_q = queues.get()
                 item = [q for q in all_q if clean_ip in q.get('target', '').split('/')[0]]
            
            if item:
                queues.remove(id=item[0].get('.id') or item[0].get('id'))
                return True
            return False
        except: return False

    def delete_client_service(self, client_id: str) -> bool:
        """Elimina servicio (Legacy alias)"""
        # En una implementación real, buscaríamos el cliente por ID primero
        # pero para el adapter delegamos a remove_client_service con data completa
        return False
    
    def get_client_stats(self, client_id: str) -> Dict[str, Any]:
        """Obtiene estadísticas"""
        return {}

    def get_active_pppoe_sessions(self) -> Dict[str, Dict[str, str]]:
        """
        Obtiene lista de sesiones PPPoE activas para saber quién está Online
        Retorna: { "username": { "uptime": "1d 05:00:00", "ip": "1.2.3.4", "id": "*12" } }
        """
        if not self._is_connected:
            return {}
            
        try:
            active_resource = self._api_connection.get_resource('/ppp/active')
            active_list = active_resource.get()
            
            sessions = {}
            for session in active_list:
                name = session.get('name')
                if name:
                    sessions[name] = {
                        'uptime': session.get('uptime', ''),
                        'ip': session.get('address', ''),
                        'caller_id': session.get('caller-id', ''),
                        'id': session.get('.id')
                    }
            return sessions
            
        except Exception as e:
            logger.error(f"Error getting active sessions: {e}")
            return {}

    def get_bulk_traffic(self, targets: List[str], all_ifaces: List[Dict] = None, all_queues: List[Dict] = None) -> Dict[str, Dict[str, int]]:
        """
        Obtiene tráfico en tiempo real procesando en ráfagas (chunks).
        Capta tanto Interfaces (PPPoE/Ethernet) usando monitor-traffic,
        como Simple Queues usando el atributo 'rate' que es lo más eficiente.
        Permite pasar datos pre-obtenidos para evitar llamadas redundantes a la API.
        """
        if not self._is_connected or not targets:
            return {}
            
        try:
            valid_requested = [t for t in targets if t]
            if not valid_requested: return {}
            
            results = {}
            
            # 1. IDENTIFICAR QUÉ ES INTERFAZ Y QUÉ ES COLA
            # Usar datos proporcionados o pedirlos si no existen
            if all_ifaces is None:
                resource_iface = self._api_connection.get_resource('/interface')
                all_ifaces = resource_iface.get()
            
            if all_queues is None:
                resource_queue = self._api_connection.get_resource('/queue/simple')
                all_queues = resource_queue.get()
            
            # Tablas de búsqueda (lower_case -> exact_name)
            iface_map = {i.get('name').lower(): i.get('name') for i in all_ifaces if i.get('name')}
            queue_map = {q.get('name').lower(): q for q in all_queues if q.get('name')}
            
            interfaces_to_monitor = []
            queue_stats_found = {}

            for target in valid_requested:
                target_l = target.lower()
                # Patrones de búsqueda comunes para MikroTik
                patterns = [target_l, f"<{target_l}>", f"pppoe-{target_l}", f"<pppoe-{target_l}>"]
                
                # A. Priorizar Interface (PPPoE activo suele tener interface dinámica)
                found_iface = next((p for p in patterns if p in iface_map), None)
                if found_iface:
                    real_iface_name = iface_map[found_iface]
                    interfaces_to_monitor.append((real_iface_name, target))
                
                # B. Buscar en Simple Queues (Fallback o para clientes estáticos)
                found_queue_key = next((p for p in patterns if p in queue_map), None)
                if found_queue_key:
                    q_data = queue_map[found_queue_key]
                    rate_str = q_data.get('rate', '0/0')
                    try:
                        u, d = rate_str.split('/')
                        queue_stats_found[target] = {
                            'upload': int(u),
                            'download': int(d)
                        }
                    except:
                        pass

            # 2. PROCESAR INTERFACES CON MONITOR-TRAFFIC (Para datos de ráfaga precisos)
            if interfaces_to_monitor:
                chunk_size = 40 # Límite razonable para la API
                iface_real_names = [pair[0] for pair in interfaces_to_monitor]
                name_to_target_map = {pair[0]: pair[1] for pair in interfaces_to_monitor}
                
                resource_iface = self._api_connection.get_resource('/interface')
                for i in range(0, len(iface_real_names), chunk_size):
                    chunk = iface_real_names[i:i + chunk_size]
                    try:
                        response = resource_iface.call('monitor-traffic', {
                            'interface': ",".join(chunk),
                            'once': 'true'
                        })
                        
                        for item in response:
                            name = item.get('name')
                            target = name_to_target_map.get(name)
                            if target:
                                rx = int(item.get('rx-bits-per-second', 0))
                                tx = int(item.get('tx-bits-per-second', 0))
                                results[target] = {
                                    'upload': rx,
                                    'download': tx
                                }
                    except Exception as e:
                        logger.warning(f"Error monitoring traffic chunk: {e}")

            # 3. MERGE CON DATOS DE QUEUES
            # Si una interfaz no reportó tráfico (o no existe), usar el dato de la cola
            for target, stats in queue_stats_found.items():
                if target not in results or (results[target]['upload'] == 0 and results[target]['download'] == 0):
                    results[target] = stats
            
            return results
            
        except Exception as e:
            logger.error(f"Error in get_bulk_traffic: {e}")
            return {}

    def get_bulk_interface_stats(self, usernames: List[str]) -> Dict[str, Dict[str, int]]:
        """
        Obtiene contadores acumulados de bytes (tx-byte, rx-byte) desde Simple Queues.
        Necesario para calcular consumo diario/mensual en los reportes.
        Retorna: { username: { tx_bytes: int, rx_bytes: int } }
        """
        if not self._is_connected or not usernames:
            return {}
        
        try:
            queue_resource = self._api_connection.get_resource('/queue/simple')
            all_queues = queue_resource.get()
            
            # Crear mapa de queues por nombre (case-insensitive)
            queue_map = {}
            for q in all_queues:
                name = q.get('name', '').lower()
                queue_map[name] = q
            
            results = {}
            for user in usernames:
                if not user:
                    continue
                user_l = user.lower()
                
                # Buscar la queue que corresponde a este usuario
                q = queue_map.get(user_l)
                if not q:
                    # Intentar con patrones alternativos
                    for pattern in [f"<{user_l}>", f"pppoe-{user_l}", f"<pppoe-{user_l}>"]:
                        q = queue_map.get(pattern)
                        if q:
                            break
                
                if q:
                    # Parsear bytes del campo 'bytes' que viene como "upload/download"
                    bytes_str = q.get('bytes', '0/0')
                    try:
                        parts = bytes_str.split('/')
                        tx_bytes = int(parts[0]) if len(parts) > 0 else 0
                        rx_bytes = int(parts[1]) if len(parts) > 1 else 0
                        
                        results[user] = {
                            'tx_bytes': tx_bytes,
                            'rx_bytes': rx_bytes
                        }
                    except (ValueError, IndexError):
                        results[user] = {'tx_bytes': 0, 'rx_bytes': 0}
                else:
                    results[user] = {'tx_bytes': 0, 'rx_bytes': 0}
            
            return results
            
        except Exception as e:
            logger.error(f"Error getting bulk interface stats: {e}")
            return {}

    def ping_bulk(self, targets: List[str], count: int = 3) -> Dict[str, Dict[str, any]]:
        """
        Ejecuta pings desde el router MikroTik via la API /tool/ping.
        Mide latencia, packet loss y jitter para cada IP objetivo.
        Retorna: { ip: { latency: float, loss: float, jitter: float, status: str } }
        """
        if not self._is_connected or not targets:
            return {}
        
        results = {}
        
        for target_ip in targets:
            if not target_ip:
                continue
            try:
                ping_resource = self._api_connection.get_resource('/tool')
                response = ping_resource.call('ping', {
                    'address': target_ip,
                    'count': str(count),
                    'interval': '200ms'
                })
                
                latencies = []
                sent = 0
                received = 0
                
                for item in response:
                    sent_val = item.get('sent')
                    received_val = item.get('received')
                    time_val = item.get('time')
                    
                    if sent_val is not None:
                        sent = int(sent_val)
                    if received_val is not None:
                        received = int(received_val)
                    
                    if time_val is not None:
                        try:
                            # MikroTik devuelve tiempo como "12ms" o "1234us"
                            time_str = str(time_val).replace('ms', '').replace('us', '')
                            lat_ms = float(time_str)
                            if 'us' in str(time_val):
                                lat_ms /= 1000.0
                            latencies.append(lat_ms)
                        except (ValueError, TypeError):
                            pass
                
                if latencies:
                    avg_latency = sum(latencies) / len(latencies)
                    # Calcular Jitter como desviación estándar
                    if len(latencies) > 1:
                        mean = avg_latency
                        variance = sum((x - mean) ** 2 for x in latencies) / len(latencies)
                        jitter = variance ** 0.5
                    else:
                        jitter = 0.0
                    
                    loss_pct = ((sent - received) / sent * 100) if sent > 0 else 100.0
                    
                    results[target_ip] = {
                        'latency': round(avg_latency, 1),
                        'loss': round(loss_pct, 1),
                        'jitter': round(jitter, 1),
                        'status': 'online' if loss_pct < 100 else 'offline'
                    }
                else:
                    results[target_ip] = {
                        'latency': -1,
                        'loss': 100.0,
                        'jitter': 0.0,
                        'status': 'timeout'
                    }
                    
            except Exception as e:
                logger.debug(f"Ping failed for {target_ip}: {e}")
                results[target_ip] = {
                    'latency': -1,
                    'loss': 100.0,
                    'jitter': 0.0,
                    'status': 'error'
                }
        
        return results

    def get_all_last_seen(self) -> Dict[str, str]:
        """
        Obtiene la información de 'Last Seen' para todos los clientes (DHCP y PPPoE).
        Retorna un diccionario: { 'username_or_ip': 'timestamp_iso_or_duration_string' }
        """
        if not self._is_connected:
            return {}
        
        results = {}
        try:
            # 1. DHCP Leases (Para clientes IP/Queue)
            leases = self._api_connection.get_resource('/ip/dhcp-server/lease').get()
            for l in leases:
                last_seen_duration = l.get('last-seen')
                if not last_seen_duration: continue
                
                # Intentar por IP
                ip = l.get('address')
                if ip:
                    results[ip] = last_seen_duration
                
                # Intentar por MAC
                mac = l.get('mac-address')
                if mac:
                    results[mac] = last_seen_duration
                    
                # Intentar por Hostname o Comment
                host = l.get('host-name')
                comment = l.get('comment')
                if host: results[host] = last_seen_duration
                if comment: results[comment] = last_seen_duration
            
            # 2. PPPoE Secrets (Para clientes PPPoE)
            secrets = self._api_connection.get_resource('/ppp/secret').get()
            for s in secrets:
                name = s.get('name')
                last_logout = s.get('last-logged-out')
                if name and last_logout and last_logout != 'never':
                    results[name] = str(last_logout)

        except Exception as e:
            logger.error(f"Error fetching last seen info: {e}")
        
        return results

    def get_bulk_interface_stats(self, interfaces: List[str]) -> Dict[str, Dict[str, int]]:
        """
        Obtiene bytes totales (rx/tx) para múltiples interfaces.
        Utilizado para reportes de consumo histórico.
        """
        if not self._is_connected or not interfaces:
            return {}
            
        try:
            valid_requested = [i for i in interfaces if i]
            if not valid_requested: return {}
            
            # 1. Obtener todas las interfaces para mapeo
            resource = self._api_connection.get_resource('/interface')
            all_ifaces = resource.get()
            
            # Indexar por nombre para búsqueda rápida O(N)
            iface_map = {i.get('name'): i for i in all_ifaces if i.get('name')}
            
            results = {}
            for user in valid_requested:
                # Buscar posible nombre de interfaz (Patrones PPPoE)
                possible_names = [user, f"<{user}>", f"<pppoe-{user}>", f"pppoe-{user}"]
                
                target_iface = None
                for name in possible_names:
                    if name in iface_map:
                        target_iface = iface_map[name]
                        break
                
                if target_iface:
                    results[user] = {
                        'rx_bytes': int(target_iface.get('rx-byte', 0)),
                        'tx_bytes': int(target_iface.get('tx-byte', 0))
                    }
            
            return results
            
        except Exception as e:
            logger.error(f"Error getting bulk interface stats: {e}")
            return {}

    def ping_bulk(self, ips: List[str], count: int = 2) -> Dict[str, Dict[str, Any]]:
        """
        Realiza PING a múltiples IPs secuencialmente (o en batch si fuera posible, 
        pero MikroTik API es secuencial para comandos síncronos).
        Retorna {ip: {'latency': ms, 'loss': %}}
        """
        if not self._is_connected or not ips:
            return {}
            
        results = {}
        # Limitamos a un lote razonable para un hilo de monitoreo (aprox 500)
        target_ips = ips[:500] 
        
        try:
            # Usamos un truco: flood ping rápido si es posible, o count bajo
            import re
            ip_pattern = re.compile(r'^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$')

            for ip in target_ips:
                try:
                    # Validar que sea una IP para evitar errores con nombres como "Dinámica"
                    if not ip_pattern.match(str(ip)):
                        # logger.debug(f"Skipping ping for non-IP address: {ip}")
                        results[ip] = {'latency': 0, 'loss': 100, 'status': 'offline'}
                        continue

                    # Ping rápido con timeout corto
                    ping_res = self._api_connection.get_resource('/').call('ping', {
                        'address': ip,
                        'count': str(count),
                        'interval': '0.2' # Rápido
                    })
                    
                    # Analizar resultados
                    sent = len(ping_res)
                    received_packets = [p for p in ping_res if 'time' in p]
                    received = len(received_packets)
                    
                    latencies = []
                    if received > 0:
                        for p in received_packets:
                            t_str = str(p['time'])
                            try:
                                clean_val_str = "".join(c for c in t_str if c.isdigit() or c == '.')
                                if not clean_val_str: continue
                                t_val = float(clean_val_str)
                                
                                if 'ms' in t_str: pass
                                elif 'us' in t_str: t_val = t_val / 1000.0
                                elif 's' in t_str and 'ms' not in t_str: t_val = t_val * 1000.0
                                
                                latencies.append(t_val)
                            except: continue

                        avg_rtt = sum(latencies) / len(latencies) if latencies else 0
                        min_rtt = min(latencies) if latencies else 0
                        max_rtt = max(latencies) if latencies else 0
                        
                        # Jitter calculation (Average Deviation)
                        jitter = 0
                        if len(latencies) > 1:
                            jitter = sum(abs(x - avg_rtt) for x in latencies) / len(latencies)

                        results[ip] = {
                            'latency': round(avg_rtt, 1),
                            'min_latency': round(min_rtt, 1),
                            'max_latency': round(max_rtt, 1),
                            'jitter': round(jitter, 1),
                            'loss': round(((sent - received) / sent) * 100, 1),
                            'status': 'online'
                        }
                    else:
                        results[ip] = {'latency': 0, 'loss': 100, 'status': 'offline', 'jitter': 0}
                except Exception as e:
                    logger.warning(f"Error pinging {ip}: {e}")
                    results[ip] = {'latency': 0, 'loss': 100, 'status': 'error'}
            
            return results

        except Exception as e:
            logger.error(f"Error bulk ping: {e}")
            return {}

    def reboot_system(self) -> bool:
        """Reinicia el router"""
        if not self._is_connected:
            return False
        try:
            self._api_connection.get_resource('/system/reboot').call('reboot')
            return True
        except Exception as e:
            # Es normal que falle porque se pierde la conexión
            logger.info(f"Reboot command sent (connection drop expected): {e}")
            return True

    def get_interfaces(self) -> List[Dict[str, Any]]:
        """Obtiene lista de interfaces"""
        if not self._is_connected:
            return []
        try:
            interfaces = self._api_connection.get_resource('/interface')
            result = []
            for iface in interfaces.get():
                result.append({
                    "name": iface.get("name", ""),
                    "type": iface.get("type", ""),
                    "running": iface.get("running", "false") == "true",
                    "disabled": iface.get("disabled", "false") == "true"
                })
            return result
        except Exception as e:
            logger.error(f"Error getting interfaces: {e}")
            return []

    def get_interface_traffic(self, interface_name: str) -> Dict[str, int]:
        """Obtiene tráfico de una interfaz en tiempo real"""
        if not self._is_connected:
            return {'rx': 0, 'tx': 0}
            
        try:
            resource = self._api_connection.get_resource('/interface')
            response = resource.call('monitor-traffic', {
                'interface': interface_name,
                'once': 'true'
            })
            
            if response:
                item = response[0]
                return {
                    'rx': int(item.get('rx-bits-per-second', 0)),
                    'tx': int(item.get('tx-bits-per-second', 0))
                }
            return {'rx': 0, 'tx': 0}
        except Exception as e:
            logger.error(f"Error getting interface traffic for {interface_name}: {e}")
            return {'rx': 0, 'tx': 0}

    def get_batch_interface_traffic(self, interfaces: List[str]) -> Dict[str, Dict[str, int]]:
        """
        Obtiene tráfico para múltiples interfaces en una sola consulta.
        Mucho más eficiente que llamar get_interface_traffic en bucle.
        """
        if not self._is_connected or not interfaces:
            return {}
            
        try:
            # Join interfaces with comma
            iface_str = ",".join(interfaces)
            
            resource = self._api_connection.get_resource('/interface')
            response = resource.call('monitor-traffic', {
                'interface': iface_str,
                'once': 'true'
            })
            
            results = {}
            for item in response:
                name = item.get('name')
                if name:
                    results[name] = {
                        'rx': int(item.get('rx-bits-per-second', 0)),
                        'tx': int(item.get('tx-bits-per-second', 0))
                    }
            return results
        except Exception as e:
            logger.error(f"Error getting batch traffic: {e}")
            return {}
    def get_dhcp_leases(self) -> List[Dict[str, str]]:
        """
        Obtiene todos los leases de DHCP que están activos (bound)
        """
        if not self._is_connected:
            return []
        try:
            resource = self._api_connection.get_resource('/ip/dhcp-server/lease')
            # Filtrar directamente en el router
            return resource.get(status='bound', disabled='false')
        except Exception as e:
            logger.error(f"Error getting DHCP leases: {e}")
            return []

    def get_dhcp_stats(self) -> Dict[str, int]:
        """
        Obtiene conteo rápido de estados DHCP haciendo consultas filtradas
        para evitar errores de parsing en datasets grandes/corruptos.
        """
        if not self._is_connected: return {'bound': 0, 'waiting': 0}
        try:
           # Estrategia segura: Consultas filtradas
           # 1. Contar BOUND
           bound_list = self._api_connection.get_resource('/ip/dhcp-server/lease').get(status='bound')
           bound = len(bound_list)
           
           # 2. Contar WAITING
           waiting_list = self._api_connection.get_resource('/ip/dhcp-server/lease').get(status='waiting')
           waiting = len(waiting_list)
           
           logger.debug(f"DHCP Stats Secure: Bound={bound}, Waiting={waiting}")
           return {'bound': bound, 'waiting': waiting, 'total': bound + waiting}
        except Exception as e:
            logger.error(f"Error getting DHCP stats: {e}")
            return {'bound': 0, 'waiting': 0}

    def get_arp_table(self) -> List[Dict[str, str]]:
        """
        Obtiene la tabla ARP filtrando entradas inválidas
        """
        if not self._is_connected:
            return []
        try:
            resource = self._api_connection.get_resource('/ip/arp')
            # Filtrar directamente en el router para evitar 'Malformed attribute' en entradas corruptas
            # y reducir tráfico
            return resource.get(invalid='false', disabled='false')
        except Exception as e:
            logger.error(f"Error getting ARP table: {e}")
            # Intento de recuperación sin filtros si falla
            try:
                return resource.get()
            except:
                return []

    # =========================================================================
    # CLIENT IMPORT METHODS
    # =========================================================================
    
    def get_all_simple_queues(self) -> List[Dict[str, Any]]:
        """
        Obtiene todas las Simple Queues configuradas en el router
        Retorna lista con información completa de cada queue
        """
        if not self._is_connected:
            return []
        
        try:
            queues_resource = self._api_connection.get_resource('/queue/simple')
            queues_list = queues_resource.get()
            
            result = []
            for queue in queues_list:
                # Parsear max-limit para obtener download/upload
                max_limit = queue.get('max-limit', '')
                download, upload = self._parse_speed_limit(max_limit)
                
                # Extraer IP del target
                target = queue.get('target', '')
                ip_address = target.split('/')[0] if target else ''
                
                result.append({
                    'mikrotik_id': queue.get('.id', ''),
                    'name': queue.get('name', ''),
                    'target': target,
                    'ip_address': ip_address,
                    'max_limit': max_limit,
                    'download_speed': download,
                    'upload_speed': upload,
                    'disabled': queue.get('disabled', 'false') == 'true',
                    'comment': queue.get('comment', ''),
                    'burst_limit': queue.get('burst-limit', ''),
                    'burst_threshold': queue.get('burst-threshold', ''),
                    'burst_time': queue.get('burst-time', ''),
                    'priority': queue.get('priority', ''),
                })
            
            logger.info(f"Retrieved {len(result)} Simple Queues from router")
            return result
            
        except Exception as e:
            logger.error(f"Error getting Simple Queues: {e}")
            return []
    
    def get_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Obtiene logs recientes del router"""
        if not self._is_connected:
            return []
        try:
            log_resource = self._api_connection.get_resource('/log')
            logs = log_resource.get()
            # Retornar los últimos 'limit' registros
            return logs[-limit:] if logs else []
        except Exception as e:
            logger.error(f"Error getting logs: {e}")
            return []

    def get_all_pppoe_secrets(self) -> List[Dict[str, Any]]:
        """
        Obtiene todos los PPPoE Secrets configurados en el router
        Retorna lista con información completa de cada secret
        """
        if not self._is_connected:
            return []
        
        try:
            secrets_resource = self._api_connection.get_resource('/ppp/secret')
            secrets_list = secrets_resource.get()
            
            result = []
            for secret in secrets_list:
                # Parsear rate-limit para obtener download/upload
                rate_limit = secret.get('rate-limit', '')
                download, upload = self._parse_speed_limit(rate_limit)
                
                result.append({
                    'mikrotik_id': secret.get('.id', ''),
                    'name': secret.get('name', ''),
                    'password': secret.get('password', ''),
                    'service': secret.get('service', 'pppoe'),
                    'profile': secret.get('profile', ''),
                    'local_address': secret.get('local-address', ''),
                    'remote_address': secret.get('remote-address', ''),
                    'rate_limit': rate_limit,
                    'download_speed': download,
                    'upload_speed': upload,
                    'disabled': secret.get('disabled', 'false') == 'true',
                    'comment': secret.get('comment', ''),
                })
            
            logger.info(f"Retrieved {len(result)} PPPoE Secrets from router")
            return result
            
        except Exception as e:
            logger.error(f"Error getting PPPoE Secrets: {e}")
            return []

    def get_ppp_profiles(self) -> List[Dict[str, Any]]:
        """Obtiene todos los perfiles PPP"""
        if not self._is_connected: return []
        try:
            resource = self._api_connection.get_resource('/ppp/profile')
            return resource.get()
        except Exception as e:
            logger.error(f"Error getting PPP profiles: {e}")
            return []

    def get_ip_pools(self) -> List[Dict[str, Any]]:
        """Obtiene todas las IP Pools"""
        if not self._is_connected: return []
        try:
            resource = self._api_connection.get_resource('/ip/pool')
            return resource.get()
        except Exception as e:
            logger.error(f"Error getting IP pools: {e}")
            return []
    
    def _parse_speed_limit(self, limit_str: str) -> tuple:
        """
        Parsea string de límite de velocidad en formato MikroTik
        Ejemplos: "50M/10M", "100M/50M", "512k/256k"
        Retorna: (download, upload) como strings
        """
        if not limit_str:
            return ('', '')
        
        try:
            parts = limit_str.split('/')
            if len(parts) == 2:
                return (parts[0].strip(), parts[1].strip())
            elif len(parts) == 1:
                # Si solo hay un valor, usarlo para ambos
                return (parts[0].strip(), parts[0].strip())
        except Exception:
            pass
        
        return ('', '')
    
    # =========================================================================
    # HELPER METHODS FOR POPULATION SCRIPT
    # =========================================================================
    
    def get_system_info(self) -> Dict[str, Any]:
        """
        Obtiene información del sistema del router
        Retorna CPU, RAM, uptime, versión, etc.
        """
        if not self._is_connected:
            return {}
        
        try:
            resource = self._api_connection.get_resource('/system/resource')
            system_info_list = resource.get()
            
            if not system_info_list:
                return {}
            
            sys_data = system_info_list[0]
            
            # Calcular uso de memoria
            total_mem = int(sys_data.get("total-memory", 0))
            free_mem = int(sys_data.get("free-memory", 0))
            mem_usage = 0
            if total_mem > 0:
                mem_usage = int(((total_mem - free_mem) / total_mem) * 100)
            
            return {
                "platform": sys_data.get("platform", ""),
                "board_name": sys_data.get("board-name", ""),
                "version": sys_data.get("version", ""),
                "uptime": sys_data.get("uptime", ""),
                "cpu_load": sys_data.get("cpu-load", "0"),
                "memory_usage": mem_usage
            }
            
        except Exception as e:
            logger.error(f"Error getting system info: {e}")
            return {}
    
    def detect_management_methods(self) -> List[str]:
        """
        Detecta qué métodos de gestión están configurados en el router
        Retorna lista de métodos: ['pppoe', 'hotspot', 'simple_queue', 'pcq']
        """
        if not self._is_connected:
            return []
        
        methods = []
        
        try:
            # Detectar PPPoE
            secrets = self._api_connection.get_resource('/ppp/secret')
            if len(secrets.get()) > 0:
                methods.append('pppoe')
        except Exception:
            pass
        
        try:
            # Detectar Hotspot
            hotspot = self._api_connection.get_resource('/ip/hotspot')
            if len(hotspot.get()) > 0:
                methods.append('hotspot')
        except Exception:
            pass
        
        try:
            # Detectar Simple Queues
            queues = self._api_connection.get_resource('/queue/simple')
            if len(queues.get()) > 0:
                methods.append('simple_queue')
        except Exception:
            pass
        
        try:
            # Detectar PCQ
            queue_types = self._api_connection.get_resource('/queue/type')
            type_list = queue_types.get()
            pcq_types = [qt for qt in type_list if qt.get("kind", "") == "pcq"]
            if len(pcq_types) > 0:
                methods.append('pcq')
        except Exception:
            pass
        
        return methods
    
    def get_pppoe_secrets(self) -> List[Dict[str, Any]]:
        """
        Alias para get_all_pppoe_secrets para compatibilidad
        """
        return self.get_all_pppoe_secrets()
    
    def get_simple_queues(self) -> List[Dict[str, Any]]:
        """
        Alias para get_all_simple_queues para compatibilidad
        """
        return self.get_all_simple_queues()

    # =========================================================================
    # ADVANCED DIAGNOSTICS METHODS (Network Auditor)
    # =========================================================================

    def get_ppp_active_ips(self) -> Set[str]:
        """Obtiene un Set de todas las IPs activas en interfaces PPP (PPPoE, L2TP, PPTP)"""
        active_ips = set()
        if not self._is_connected: return active_ips
        
        try:
            # Consultar active PPP connections
            # Podemos pedir active services
            ppp_active = self._api_connection.get_resource('/ppp/active')
            
            # Obtener todo y filtrar en memoria para asegurar cobertura
            # (Aunque podríamos filtrar por service, es más rápido una llamada única si no son miles)
            all_active = ppp_active.get()
            
            for conn in all_active:
                ip = conn.get('address')
                if ip:
                    active_ips.add(ip)
            
            return active_ips
        except Exception as e:
            logger.error(f"Error getting active PPP IPs: {e}")
            return active_ips

    def get_waiting_leases(self) -> List[Dict[str, str]]:
        """Obtiene lista detallada de leases en estado 'waiting'"""
        if not self._is_connected: return []
        try:
            return self._api_connection.get_resource('/ip/dhcp-server/lease').get(status='waiting')
        except Exception as e:
            logger.error(f"Error getting waiting leases: {e}")
            return []

    def get_failed_arp_ips(self) -> Set[str]:
        """Obtiene Set de IPs con estado ARP 'failed'"""
        failed_ips = set()
        if not self._is_connected: return failed_ips
        try:
            # Buscar explícitamente status failed
            arps = self._api_connection.get_resource('/ip/arp').get(status='failed')
            for entry in arps:
                ip = entry.get('address')
                if ip:
                    failed_ips.add(ip)
            return failed_ips
        except Exception as e:
            logger.error(f"Error getting failed ARP IPs: {e}")
            return failed_ips

    def remove_dhcp_lease(self, lease_id: str) -> bool:
        """Elimina un lease DHCP por ID"""
        if not self._is_connected: return False
        try:
            self._api_connection.get_resource('/ip/dhcp-server/lease').remove(id=lease_id)
            return True
        except Exception as e:
            logger.error(f"Error removing lease {lease_id}: {e}")
            return False


    def get_client_identity(self, ip: str = None, mac: str = None, username: str = None) -> Dict[str, Any]:
        """
        Busca la identidad completa de un cliente (IP, MAC, Username) en el MikroTik.
        Cruza datos de DHCP Leases, Arp Table y PPP Active.
        """
        if not self._is_connected:
            return {}

        result = {
            'ip': ip,
            'mac': mac,
            'username': username,
            'found': False,
            'source': None
        }

        # 1. Buscar en DHCP Leases
        try:
            leases = self._api_connection.get_resource('/ip/dhcp-server/lease')
            l_found = None
            if ip:
                l_found = leases.get(address=ip)
            elif mac:
                # Filtrado manual si la MAC no es parámetro indexado (depende del MikroTik)
                all_l = leases.get()
                l_found = [l for l in all_l if l.get('mac-address', '').lower() == mac.lower()]
            
            if l_found:
                data = l_found[0]
                result['ip'] = data.get('address')
                result['mac'] = data.get('mac-address')
                result['found'] = True
                result['source'] = 'dhcp-lease'
                return result
        except Exception as e:
            logger.debug(f"Identity search in DHCP failed: {e}")

        # 2. Buscar en ARP Table
        try:
            arp = self._api_connection.get_resource('/ip/arp')
            a_found = None
            if ip:
                a_found = arp.get(address=ip)
            elif mac:
                all_a = arp.get()
                a_found = [a for a in all_a if a.get('mac-address', '').lower() == mac.lower()]
            
            if a_found:
                data = a_found[0]
                result['ip'] = data.get('address')
                result['mac'] = data.get('mac-address')
                result['found'] = True
                result['source'] = 'arp'
                return result
        except Exception as e:
            logger.debug(f"Identity search in ARP failed: {e}")

        # 3. Buscar en PPP Active
        try:
            ppp = self._api_connection.get_resource('/ppp/active')
            p_found = None
            if username:
                p_found = ppp.get(name=username)
            elif ip:
                p_found = ppp.get(address=ip)
            
            if p_found:
                data = p_found[0]
                result['ip'] = data.get('address')
                result['username'] = data.get('name')
                result['found'] = True
                result['source'] = 'ppp-active'
                # Nota: PPP Active usualmente no muestra MAC a menos que sea a través de caller-id
                if 'caller-id' in data and ':' in data['caller-id']:
                    result['mac'] = data['caller-id']
                return result
        except Exception as e:
            logger.debug(f"Identity search in PPP failed: {e}")

        return result
