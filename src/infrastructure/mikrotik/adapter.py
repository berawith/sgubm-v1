"""
MikroTik Service Adapter (FACADE)
Implementación optimizada de INetworkService para routers MikroTik.
Arquitectura de Capacidades Modulares para aislamiento de errores y limpieza.
"""
from typing import Dict, Any, Optional, List, Set
import logging
import re
import unicodedata
from routeros_api import RouterOsApiPool
from routeros_api.exceptions import RouterOsApiConnectionError, RouterOsApiCommunicationError

from src.core.interfaces.contracts import INetworkService
from src.core.domain.entities import ManagementMethod
from .capabilities import PPPCapability, QueueCapability, SystemCapability

logger = logging.getLogger(__name__)

def normalize_name(name: str) -> str:
    """Normaliza nombres para matching robusto en MikroTik."""
    if not name: return ""
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
    name = re.sub(r'[^a-zA-Z0-9\s\-_]', '', name).lower().strip()
    return re.sub(r'\s+', ' ', name)

class MikroTikAdapter(INetworkService):
    """
    Fachada principal para la infraestructura MikroTik.
    Orquestra capacidades especializadas y gestiona la conectividad base.
    """
    
    def __init__(self):
        self._connection_pool: Optional[RouterOsApiPool] = None
        self._api_connection = None
        self._host: str = ""
        self._is_connected: bool = False
        
        # Capacidades (Delegación)
        self.ppp: Optional[PPPCapability] = None
        self.queues: Optional[QueueCapability] = None
        self.system: Optional[SystemCapability] = None
    
    def connect(self, host: str, username: str, password: str, port: int = 8728, timeout: int = 10) -> bool:
        import socket
        try:
            self._host = host
            # Pre-check táctico
            try:
                s = socket.create_connection((host, port), timeout=timeout)
                s.close()
            except Exception as e:
                logger.warning(f"🚨 MikroTik {host} inalcanzable: {e}")
                return False

            self._connection_pool = RouterOsApiPool(
                host=host, username=username, password=password, port=port, plaintext_login=True
            )
            self._api_connection = self._connection_pool.get_api()
            self._is_connected = True
            
            # Inicializar módulos de capacidad
            self.ppp = PPPCapability(self._api_connection)
            self.queues = QueueCapability(self._api_connection)
            self.system = SystemCapability(self._api_connection)
            
            for cap in [self.ppp, self.queues, self.system]:
                cap.set_host(host)

            logger.info(f"✅ [INFRA] MikroTik Adapter conectado y capacidades desplegadas en {host}")
            return True
        except Exception as e:
            logger.error(f"Fallo crítico conectando a {host}: {e}")
            return False

    def disconnect(self) -> None:
        if self._connection_pool:
            self._connection_pool.disconnect()
            self._is_connected = False
            logger.info(f"🔌 Desconectado de {self._host}")

    def discover_configuration(self) -> Dict[str, Any]:
        """Detecta la configuración completa delegando a capacidades."""
        if not self._is_connected: return {}
        
        config = {
            "methods": [],
            "detected_plans": [],
            "network_segments": [],
            "system_info": self.system.get_resource_usage(),
            "interfaces": self.system.get_interfaces()
        }
        
        ppp_info = self.ppp.detect()
        if ppp_info["enabled"]:
            config["methods"].append(ManagementMethod.PPPOE.value)
            config["detected_plans"].extend(ppp_info["profiles"])
            config["network_segments"].extend(ppp_info["pools"])
            
        queue_info = self.queues.detect()
        if queue_info["enabled"]:
            config["methods"].append(ManagementMethod.SIMPLE_QUEUE.value)
            config["detected_plans"].extend(queue_info["queue_types"])
            
        return config

    # --- Gestión de Clientes (Ciclo de Vida) ---

    def create_client_service(self, client_data: Dict[str, Any]) -> Dict[str, Any]:
        """Crea un servicio para un cliente (PPPoE, Queue, etc.)."""
        service_type = client_data.get('service_type', 'pppoe')
        logger.info(f"🆕 [FACADE] Creando servicio {service_type} para {client_data.get('username')}")
        
        if service_type == 'pppoe':
            return self.ppp.create_client(client_data)
        else:
            success = self.queues.create_simple_queue(
                client_data['username'], client_data['ip_address'], client_data.get('rate_limit', '1M/1M')
            )
            return {"success": success, "method": service_type}

    def update_client_service(self, client_id: str, updates: Dict[str, Any]) -> bool:
        """Actualiza configuración de servicio."""
        logger.info(f"⚙️ [FACADE] Actualizando servicio id: {client_id}")
        return True # Implementar lógica de reconciliación si es necesario

    def suspend_client_service(self, client_id: str) -> bool:
        """Suspende servicio (mora, mantenimiento)."""
        logger.info(f"🚫 [FACADE] Suspendiendo servicio id: {client_id}")
        self.system.ensure_firewall_rules()
        # Aquí client_id debería ser el username para MikroTik
        self.ppp.remove_secret(client_id)
        self.queues.remove_queue(client_id)
        return True

    def restore_client_service(self, client_id: str) -> bool:
        """Restaura servicio suspendido."""
        logger.info(f"🔄 [FACADE] Restaurando servicio id: {client_id}")
        return True # En Mikrotik restore suele implicar re-crear.

    def delete_client_service(self, client_id: str) -> bool:
        """Elimina servicio del router."""
        logger.info(f"🗑️ [FACADE] Eliminando servicio id: {client_id}")
        self.ppp.remove_secret(client_id)
        self.queues.remove_queue(client_id)
        return True

    def get_client_stats(self, client_id: str) -> Dict[str, Any]:
        """Obtiene estadísticas de tráfico del cliente."""
        return {'tx': 0, 'rx': 0}

    # --- Monitoreo y Estadísticas ---

    def get_active_pppoe_sessions(self) -> Dict[str, Any]:
        return self.ppp.get_active_sessions()

    def get_bulk_traffic(self, targets: List[str], all_ifaces: List[Dict] = None, all_queues: List[Dict] = None) -> Dict[str, Any]:
        return self.queues.get_bulk_traffic(targets, all_ifaces, all_queues)

    def get_all_last_seen(self) -> Dict[str, str]:
        return self.system.get_all_last_seen()

    def get_system_info(self) -> Dict[str, Any]:
        """Obtiene información de recursos del sistema (CPU, Memeria, etc.)."""
        if not self.system: return {}
        return self.system.get_resource_usage()

    def ping_bulk(self, targets: List[str], count: int = 2) -> Dict[str, Any]:
        return self.system.ping(targets, count)

    def get_logs(self, limit: int = 50) -> List[Dict]:
        return self.system.get_logs(limit)

    def get_interfaces(self) -> List[Dict]:
        return self.system.get_interfaces()

    def get_interface_traffic(self, interface_name: str) -> Dict[str, int]:
        """Obtiene tráfico acumulativo o en tiempo real de una interfaz."""
        if not self.system: return {'tx': 0, 'rx': 0}
        return self.system.get_interface_traffic(interface_name)

    def get_arp_table(self) -> List[Dict]:
        """Proxy para compatibilidad con TrafficSurgicalEngine."""
        return self.system.get_arp_table()

    def get_dhcp_leases(self) -> List[Dict]:
        """Proxy para compatibilidad con TrafficSurgicalEngine."""
        return self.system.get_dhcp_leases()

    # --- Acceso Crudo (Para motores que requieren el recurso directo) ---
    def _get_resource(self, path: str):
        return self._api_connection.get_resource(path)
