"""
MikroTik Service Adapter
Implementación concreta de INetworkService para routers MikroTik
Este módulo es completamente intercambiable - se puede crear CiscoAdapter, UbiquitiAdapter, etc.
"""
from typing import Dict, Any, Optional, List
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
        old_timeout = socket.getdefaulttimeout()
        
        try:
            self._host = host
            
            # Configurar timeout específico para esta conexión
            socket.setdefaulttimeout(timeout)
            
            self._connection_pool = RouterOsApiPool(
                host=host,
                username=username,
                password=password,
                port=port,
                plaintext_login=True
            )
            self._api_connection = self._connection_pool.get_api()
            self._is_connected = True
            logger.info(f"Connected to MikroTik router at {host}:{port} (Timeout: {timeout}s)")
            return True
        
        except Exception as e:
            logger.error(f"Error connecting to {host}: {str(e)}")
            self._is_connected = False
            return False
            
        finally:
            # RESTAURAR TIMEOUT ORIGINAL IMPORTANTE
            socket.setdefaulttimeout(old_timeout)
    
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
                "comment": client_data.get("comment", "")
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
                "comment": client_data.get("comment", "")
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
        try:
            queues = self._api_connection.get_resource('/queue/simple')
            
            queue_params = {
                "name": client_data["queue_name"],
                "target": client_data["target_address"],
                "max-limit": client_data["max_limit"],
                "comment": client_data.get("comment", "")
            }
            
            if "burst_limit" in client_data:
                queue_params["burst-limit"] = client_data["burst_limit"]
                queue_params["burst-threshold"] = client_data.get("burst_threshold", "")
                queue_params["burst-time"] = client_data.get("burst_time", "8s/8s")
            
            result = queues.add(**queue_params)
            logger.info(f"Simple Queue created: {client_data['queue_name']}")
            
            return {
                "success": True,
                "mikrotik_id": result.get("ret", ""),
                "method": "simple_queue",
                "details": queue_params
            }
            
        except Exception as e:
            logger.error(f"Error creating Simple Queue: {str(e)}")
            raise
    
    def ensure_cutoff_firewall_rules(self) -> bool:
        """
        Configura las reglas de firewall necesarias para manejar la lista CORTADOS-SGUB.
        1. Permite DNS (UDP 53)
        2. Bloquea el resto del tráfico (Drop)
        """
        if not self._is_connected:
            return False
            
        try:
            # 1. REGLAS DE FILTRO (IP -> Firewall -> Filter)
            filter_rules = self._api_connection.get_resource('/ip/firewall/filter')
            
            # --- Regla A: Permitir DNS (indispensable para que el cliente no piense que el router murió) ---
            dns_rule = filter_rules.get(comment='SGUB-ALLOW-DNS', src_address_list='CORTADOS-SGUB')
            if not dns_rule:
                filter_rules.add(
                    chain='forward',
                    src_address_list='CORTADOS-SGUB',
                    protocol='udp',
                    dst_port='53',
                    action='accept',
                    comment='SGUB-ALLOW-DNS'
                )
                logger.info("MikroTik: Regla DNS para cortados agregada")

            # --- Regla B: Bloqueo Total (excepto lo anterior) ---
            drop_rule = filter_rules.get(comment='SGUB-DROP-CORTADOS', src_address_list='CORTADOS-SGUB')
            if not drop_rule:
                filter_rules.add(
                    chain='forward',
                    src_address_list='CORTADOS-SGUB',
                    action='drop',
                    comment='SGUB-DROP-CORTADOS'
                )
                logger.info("MikroTik: Regla Drop para cortados agregada")

            # 2. REGLAS DE NAT (Opcional: Redirección a portal de aviso)
            # Nota: Esto requiere que el ISP tenga un servidor web de avisos cargado.
            # Por ahora solo implementamos el bloqueo robusto.

            return True
        except Exception as e:
            logger.error(f"Error configuring firewall rules in MikroTik: {e}")
            return False

    def update_client_service(self, current_username: str, client_data: Dict[str, Any]) -> bool:
        """
        Actualiza la configuración del servicio del cliente en el MikroTik.
        Sincroniza el nombre en Simple Queues, DHCP Leases y Address Lists.
        """
        if not self._is_connected:
            return False
            
        success = True
        new_username = client_data.get('username')
        legal_name = client_data.get('legal_name')
        ip_address = client_data.get('ip_address')
        service_type = client_data.get('service_type', 'pppoe')
        
        # 1. ACTUALIZAR EN SIMPLE QUEUES (Si existe)
        try:
            queues = self._api_connection.get_resource('/queue/simple')
            # Buscar por nombre actual
            q_list = queues.get(name=current_username)
            if q_list:
                update_params = {}
                if new_username:
                    update_params['name'] = new_username
                if legal_name:
                    update_params['comment'] = legal_name
                
                if update_params:
                    queues.set(id=q_list[0]['.id'], **update_params)
                    logger.info(f"MikroTik: Simple Queue '{current_username}' actualizada a '{new_username or current_username}'")
        except Exception as e:
            logger.error(f"Error updating Simple Queue in MikroTik: {e}")
            success = False

        # 2. ACTUALIZAR EN PPPOE SECRETS (Si es PPPoE)
        if service_type == 'pppoe':
            try:
                secrets = self._api_connection.get_resource('/ppp/secret')
                s_list = secrets.get(name=current_username)
                if s_list:
                    update_params = {}
                    if new_username:
                        update_params['name'] = new_username
                    if legal_name:
                        update_params['comment'] = legal_name
                    
                    if update_params:
                        secrets.set(id=s_list[0]['.id'], **update_params)
                        logger.info(f"MikroTik: PPPoE Secret '{current_username}' actualizada")
            except Exception as e:
                logger.error(f"Error updating PPPoE Secret in MikroTik: {e}")
                success = False

        # 3. ACTUALIZAR COMENTARIOS EN DHCP LEASES
        if ip_address:
            try:
                leases = self._api_connection.get_resource('/ip/dhcp-server/lease')
                l_list = leases.get(address=ip_address)
                if l_list and legal_name:
                    for lease in l_list:
                        leases.set(id=lease['.id'], comment=legal_name)
                    logger.info(f"MikroTik: DHCP Lease para IP {ip_address} actualizado con comentario '{legal_name}'")
            except Exception as e:
                logger.error(f"Error updating DHCP Lease comment in MikroTik: {e}")

        # 4. ACTUALIZAR COMENTARIOS EN ADDRESS LISTS
        if ip_address:
            try:
                addr_lists = self._api_connection.get_resource('/ip/firewall/address-list')
                # Buscamos todas las entradas con esta IP para actualizar el comentario
                a_list = addr_lists.get(address=ip_address)
                if a_list and legal_name:
                    for entry in a_list:
                        addr_lists.set(id=entry['.id'], comment=legal_name)
                    logger.info(f"MikroTik: Address List entries para IP {ip_address} actualizados con comentario '{legal_name}'")
            except Exception as e:
                logger.error(f"Error updating Address List comment in MikroTik: {e}")

        return success
    
    def suspend_client_service(self, client_data: Dict[str, Any]) -> bool:
        """
        Suspende el servicio del cliente.
        Deshabilita el Secret/Queue y lo agrega a la Address List de SUSPENDIDOS.
        """
        if not self._is_connected:
            return False
            
        username = client_data.get('username')
        ip_address = client_data.get('ip_address')
        legal_name = client_data.get('legal_name', username)
        service_type = client_data.get('service_type', 'pppoe')
        
        try:
            # 1. Deshabilitar Secret/Queue
            if service_type == 'pppoe':
                resource = self._api_connection.get_resource('/ppp/secret')
            else:
                resource = self._api_connection.get_resource('/queue/simple')
                
            item = resource.get(name=username)
            if item:
                resource.set(id=item[0]['.id'], disabled='yes')
            
            # 2. Agregar a Address List para redirección (Corte)
            if ip_address:
                addr_lists = self._api_connection.get_resource('/ip/firewall/address-list')
                # Verificar si ya está en la lista para no duplicar
                existing = addr_lists.get(list='CORTADOS-SGUB', address=ip_address)
                if not existing:
                    addr_lists.add(list='CORTADOS-SGUB', address=ip_address, comment=legal_name)
                    logger.info(f"MikroTik: IP {ip_address} agregada a lista CORTADOS-SGUB")
                
            return True
        except Exception as e:
            logger.error(f"Error suspending client in MikroTik: {e}")
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
        
        try:
            # 1. Habilitar Secret/Queue
            if service_type == 'pppoe':
                resource = self._api_connection.get_resource('/ppp/secret')
            else:
                resource = self._api_connection.get_resource('/queue/simple')
                
            item = resource.get(name=username)
            if item:
                resource.set(id=item[0]['.id'], disabled='no')
            
            # 2. Eliminar de Address List
            if ip_address:
                addr_lists = self._api_connection.get_resource('/ip/firewall/address-list')
                existing = addr_lists.get(list='CORTADOS-SGUB', address=ip_address)
                if existing:
                    for entry in existing:
                        addr_lists.remove(id=entry['.id'])
                    logger.info(f"MikroTik: IP {ip_address} eliminada de lista CORTADOS-SGUB")
                
            return True
        except Exception as e:
            logger.error(f"Error restoring client in MikroTik: {e}")
            return False
    
    def delete_client_service(self, client_id: str) -> bool:
        """Elimina servicio"""
        # Implementación para eliminar
        pass
    
    def get_client_stats(self, client_id: str) -> Dict[str, Any]:
        """Obtiene estadísticas"""
        # Implementación para obtener tráfico de un solo cliente
        pass

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

    def get_bulk_traffic(self, interfaces: List[str]) -> Dict[str, Dict[str, str]]:
        """
        Obtiene tráfico en tiempo real validando primero qué interfaces existen realmente.
        Evita que el comando falle si una interfaz (candidato) no existe.
        """
        if not self._is_connected or not interfaces:
            return {}
            
        try:
            valid_requested = [i for i in interfaces if i]
            if not valid_requested: return {}
            
            # 1. Obtener lista REAL de interfaces del router para validar existencia
            # Esto es ligero si solo pedimos nombres
            try:
                all_interfaces_res = self._api_connection.get_resource('/interface')
                # Solo traemos nombres para ser rápidos (routeros_api no soporta 'attributes', usamos .get() simple)
                all_ifaces_list = all_interfaces_res.get()
                existing_names = {i.get('name') for i in all_ifaces_list if i.get('name')}
            except Exception as e:
                logger.error(f"Error listing interfaces for validation: {e}")
                return {}

            # 2. Construir lista de interfaces a consultar que SÍ existen
            final_interfaces_query = []
            mapping = {} # Mapa interfaz_real -> usuario_db

            for user in valid_requested:
                # Candidatos posibles
                c1 = user
                c2 = f"<pppoe-{user}>"
                
                matched = False
                
                # Verificamos cuál existe
                if c2 in existing_names:
                    final_interfaces_query.append(c2)
                    mapping[c2] = user
                    matched = True
                elif c1 in existing_names:
                    final_interfaces_query.append(c1)
                    mapping[c1] = user
                    matched = True
                
                # Si no existe ninguna, no la pedimos (evita romper el comando)

            if not final_interfaces_query:
                return {}

            iface_str = ",".join(final_interfaces_query)
            
            # 3. Ejecutar monitor-traffic SOLO con interfaces válidas
            resource = self._api_connection.get_resource('/interface')
            try:
                response = resource.call('monitor-traffic', {
                    'interface': iface_str,
                    'once': 'true'
                })
            except Exception as e:
                logger.warning(f"Monitor traffic command failed despite validation: {e}")
                return {}
            
            results = {}
            for item in response:
                name = item.get('name')
                if name in mapping:
                    original_user = mapping[name]
                    
                    tx = int(item.get('tx-bits-per-second', 0))
                    rx = int(item.get('rx-bits-per-second', 0))
                    
                    results[original_user] = {
                        'upload': rx,
                        'download': tx
                    }
            
            return results
            
        except Exception as e:
            logger.error(f"Error bulk traffic logic: {e}")
            return {}

    def get_dhcp_leases(self) -> List[Dict[str, str]]:
        """
        Obtiene todos los leases de DHCP
        """
        if not self._is_connected:
            return []
        try:
            resource = self._api_connection.get_resource('/ip/dhcp-server/lease')
            return resource.get()
        except Exception as e:
            logger.error(f"Error getting DHCP leases: {e}")
            return []

    def get_arp_table(self) -> List[Dict[str, str]]:
        """
        Obtiene la tabla ARP
        """
        if not self._is_connected:
            return []
        try:
            resource = self._api_connection.get_resource('/ip/arp')
            return resource.get()
        except Exception as e:
            logger.error(f"Error getting ARP table: {e}")
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

