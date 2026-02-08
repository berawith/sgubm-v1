"""
Interfaces (Contracts) del Sistema
Todas las interfaces que definen contratos entre módulos
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import datetime


# ============================================================================
# NETWORK SERVICE INTERFACE
# ============================================================================
class INetworkService(ABC):
    """
    Contrato para servicios de red (MikroTik, Cisco, Ubiquiti, etc.)
    Cualquier implementación debe cumplir este contrato
    """
    
    @abstractmethod
    def connect(self, host: str, username: str, password: str, port: int = 8728) -> bool:
        """Establece conexión con el dispositivo de red"""
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Cierra la conexión"""
        pass
    
    @abstractmethod
    def create_client_service(self, client_data: Dict[str, Any]) -> Dict[str, Any]:
        """Crea un servicio para un cliente (PPPoE, Queue, etc.)"""
        pass
    
    @abstractmethod
    def update_client_service(self, client_id: str, updates: Dict[str, Any]) -> bool:
        """Actualiza configuración de servicio"""
        pass
    
    @abstractmethod
    def suspend_client_service(self, client_id: str) -> bool:
        """Suspende servicio (mora, mantenimiento)"""
        pass
    
    @abstractmethod
    def restore_client_service(self, client_id: str) -> bool:
        """Restaura servicio suspendido"""
        pass
    
    @abstractmethod
    def delete_client_service(self, client_id: str) -> bool:
        """Elimina servicio del router"""
        pass
    
    @abstractmethod
    def get_client_stats(self, client_id: str) -> Dict[str, Any]:
        """Obtiene estadísticas de tráfico del cliente"""
        pass
    
    @abstractmethod
    def discover_configuration(self) -> Dict[str, Any]:
        """Analiza y retorna la configuración actual del router"""
        pass


# ============================================================================
# DATABASE REPOSITORY INTERFACE
# ============================================================================
class IRepository(ABC):
    """
    Contrato genérico para repositorios de datos
    """
    
    @abstractmethod
    def create(self, entity: Any) -> Any:
        """Crea una nueva entidad"""
        pass
    
    @abstractmethod
    def get_by_id(self, entity_id: str) -> Optional[Any]:
        """Obtiene entidad por ID"""
        pass
    
    @abstractmethod
    def get_all(self, filters: Optional[Dict] = None) -> List[Any]:
        """Obtiene todas las entidades con filtros opcionales"""
        pass
    
    @abstractmethod
    def update(self, entity_id: str, updates: Dict[str, Any]) -> bool:
        """Actualiza una entidad"""
        pass
    
    @abstractmethod
    def delete(self, entity_id: str) -> bool:
        """Elimina una entidad"""
        pass


# ============================================================================
# BILLING SERVICE INTERFACE
# ============================================================================
class IBillingService(ABC):
    """
    Contrato para servicios de facturación
    """
    
    @abstractmethod
    def generate_invoice(self, client_id: str, period: str) -> Dict[str, Any]:
        """Genera factura para un cliente en un periodo"""
        pass
    
    @abstractmethod
    def register_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Registra un pago"""
        pass
    
    @abstractmethod
    def check_overdue_clients(self, zone_id: Optional[str] = None) -> List[Dict]:
        """Verifica clientes morosos"""
        pass
    
    @abstractmethod
    def calculate_total(self, items: List[Dict], taxes: List[Dict]) -> float:
        """Calcula total de factura"""
        pass


# ============================================================================
# AUTHENTICATION SERVICE INTERFACE
# ============================================================================
class IAuthService(ABC):
    """
    Contrato para autenticación y autorización
    """
    
    @abstractmethod
    def authenticate(self, username: str, password: str) -> Optional[Dict]:
        """Autentica usuario"""
        pass
    
    @abstractmethod
    def authorize(self, user_id: str, resource: str, action: str) -> bool:
        """Verifica permisos"""
        pass
    
    @abstractmethod
    def create_token(self, user_data: Dict) -> str:
        """Genera token de sesión"""
        pass
    
    @abstractmethod
    def validate_token(self, token: str) -> Optional[Dict]:
        """Valida token"""
        pass


# ============================================================================
# EVENT BUS INTERFACE
# ============================================================================
class IEventBus(ABC):
    """
    Contrato para sistema de eventos (pub/sub)
    Permite comunicación desacoplada entre módulos
    """
    
    @abstractmethod
    def subscribe(self, event_name: str, handler: callable) -> None:
        """Suscribe un manejador a un evento"""
        pass
    
    @abstractmethod
    def unsubscribe(self, event_name: str, handler: callable) -> None:
        """Desuscribe un manejador"""
        pass
    
    @abstractmethod
    def publish(self, event_name: str, data: Dict[str, Any]) -> None:
        """Publica un evento"""
        pass


# ============================================================================
# NOTIFICATION SERVICE INTERFACE
# ============================================================================
class INotificationService(ABC):
    """
    Contrato para servicios de notificación
    """
    
    @abstractmethod
    def send_email(self, to: str, subject: str, body: str) -> bool:
        """Envía email"""
        pass
    
    @abstractmethod
    def send_sms(self, phone: str, message: str) -> bool:
        """Envía SMS"""
        pass
    
    @abstractmethod
    def send_whatsapp(self, phone: str, message: str) -> bool:
        """Envía mensaje por WhatsApp"""
        pass


# ============================================================================
# REPORT GENERATOR INTERFACE
# ============================================================================
class IReportGenerator(ABC):
    """
    Contrato para generadores de reportes
    """
    
    @abstractmethod
    def generate(self, report_type: str, params: Dict[str, Any]) -> bytes:
        """Genera reporte en formato binario"""
        pass
    
    @abstractmethod
    def get_available_formats(self) -> List[str]:
        """Retorna formatos soportados (PDF, Excel, etc.)"""
        pass


# ============================================================================
# CACHE SERVICE INTERFACE
# ============================================================================
class ICacheService(ABC):
    """
    Contrato para servicios de caché
    """
    
    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Obtiene valor del caché"""
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Almacena valor en caché"""
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """Elimina valor del caché"""
        pass
    
    @abstractmethod
    def clear(self) -> bool:
        """Limpia todo el caché"""
        pass
