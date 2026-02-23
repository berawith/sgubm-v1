"""
Event Bus - Sistema de Eventos Desacoplado
Permite comunicación entre módulos sin dependencias directas

Ejemplo de uso:
    # Módulo A publica un evento
    event_bus.publish("client.suspended", {"client_id": "123", "reason": "overdue"})
    
    # Módulo B se suscribe al evento (sin conocer a A)
    event_bus.subscribe("client.suspended", handle_suspension)
"""
from typing import Dict, List, Callable, Any
from datetime import datetime
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class Event:
    """Evento del sistema"""
    name: str
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source_module: str = "unknown"


class EventBus:
    """
    Implementación del patrón Pub/Sub para comunicación entre módulos
    """
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._event_history: List[Event] = []
        self._max_history = 1000  # Límite de eventos en historial
    
    def subscribe(self, event_name: str, handler: Callable) -> None:
        """
        Suscribe un manejador a un evento
        
        Args:
            event_name: Nombre del evento (ej: "client.created")
            handler: Función que manejará el evento
        """
        if event_name not in self._subscribers:
            self._subscribers[event_name] = []
        
        if handler not in self._subscribers[event_name]:
            self._subscribers[event_name].append(handler)
            logger.info(f"Handler subscribed to event: {event_name}")
    
    def unsubscribe(self, event_name: str, handler: Callable) -> None:
        """Desuscribe un manejador"""
        if event_name in self._subscribers:
            if handler in self._subscribers[event_name]:
                self._subscribers[event_name].remove(handler)
                logger.info(f"Handler unsubscribed from event: {event_name}")
    
    def publish(self, event_name: str, data: Dict[str, Any], source: str = "unknown") -> None:
        """
        Publica un evento
        
        Args:
            event_name: Nombre del evento
            data: Datos del evento
            source: Módulo que origina el evento
        """
        event = Event(name=event_name, data=data, source_module=source)
        
        # Guardar en historial
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)
        
        # Notificar a suscriptores
        if event_name in self._subscribers:
            for handler in self._subscribers[event_name]:
                try:
                    handler(event.data)
                    logger.debug(f"Event {event_name} handled successfully")
                except Exception as e:
                    logger.error(f"Error handling event {event_name}: {str(e)}")
    
    def get_history(self, event_name: Optional[str] = None, limit: int = 100) -> List[Event]:
        """Obtiene historial de eventos"""
        if event_name:
            return [e for e in self._event_history if e.name == event_name][-limit:]
        return self._event_history[-limit:]
    
    def clear_history(self) -> None:
        """Limpia el historial de eventos"""
        self._event_history.clear()


# ============================================================================
# EVENTOS ESTÁNDAR DEL SISTEMA
# ============================================================================
class SystemEvents:
    """Constantes de eventos del sistema"""
    
    # Eventos de Cliente
    CLIENT_CREATED = "client.created"
    CLIENT_UPDATED = "client.updated"
    CLIENT_DELETED = "client.deleted"
    CLIENT_SUSPENDED = "client.suspended"
    CLIENT_RESTORED = "client.restored"
    
    # Eventos de Suscripción
    SUBSCRIPTION_CREATED = "subscription.created"
    SUBSCRIPTION_ACTIVATED = "subscription.activated"
    SUBSCRIPTION_SUSPENDED = "subscription.suspended"
    SUBSCRIPTION_CANCELLED = "subscription.cancelled"
    
    # Eventos de Facturación
    INVOICE_GENERATED = "invoice.generated"
    PAYMENT_RECEIVED = "payment.received"
    PAYMENT_OVERDUE = "payment.overdue"
    
    # Eventos de Red
    NODE_ONLINE = "node.online"
    NODE_OFFLINE = "node.offline"
    NODE_CONFIG_CHANGED = "node.config_changed"
    
    # Eventos de WhatsApp
    WHATSAPP_MESSAGE_RECEIVED = "whatsapp.message_received"
    WHATSAPP_MESSAGE_SENT = "whatsapp.message_sent"
    
    # Eventos de Sistema
    SYSTEM_ERROR = "system.error"
    SYSTEM_WARNING = "system.warning"


# Instancia global del Event Bus (Singleton)
from typing import Optional

_event_bus_instance: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Retorna la instancia singleton del Event Bus"""
    global _event_bus_instance
    if _event_bus_instance is None:
        _event_bus_instance = EventBus()
    return _event_bus_instance
