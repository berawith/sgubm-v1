"""
Domain Entities - Entidades del Núcleo del Negocio
Solo contienen lógica de negocio, sin dependencias externas
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from uuid import uuid4


# ============================================================================
# ENUMERATIONS
# ============================================================================
class ClientStatus(Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING_INSTALL = "pending_install"
    CANCELLED = "cancelled"


class ManagementMethod(Enum):
    PPPOE = "pppoe"
    HOTSPOT = "hotspot"
    SIMPLE_QUEUE = "simple_queue"
    PCQ = "pcq"
    HYBRID = "hybrid"


class PaymentStatus(Enum):
    PENDING = "pending"
    PARTIAL = "partial"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class NodeStatus(Enum):
    ACTIVE = "active"
    MAINTENANCE = "maintenance"
    OFFLINE = "offline"


# ============================================================================
# VALUE OBJECTS
# ============================================================================
@dataclass(frozen=True)
class BurstConfig:
    """Configuración de ráfagas de velocidad"""
    limit_download: str  # Ej: "20M"
    limit_upload: str    # Ej: "5M"
    threshold_download: str  # Ej: "15M"
    threshold_upload: str    # Ej: "3M"
    time: str  # Ej: "8s/8s"
    
    def to_dict(self) -> Dict[str, str]:
        return {
            "limit_download": self.limit_download,
            "limit_upload": self.limit_upload,
            "threshold_download": self.threshold_download,
            "threshold_upload": self.threshold_upload,
            "time": self.time
        }


@dataclass(frozen=True)
class Coordinates:
    """Coordenadas geográficas"""
    latitude: float
    longitude: float
    
    def to_tuple(self) -> tuple:
        return (self.latitude, self.longitude)


# ============================================================================
# DOMAIN ENTITIES
# ============================================================================
@dataclass
class Node:
    """
    Nodo de Servicio (Router/Servidor)
    Entidad del dominio puro - sin dependencias de infraestructura
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    alias: str = ""
    host_address: str = ""
    api_port: int = 8728
    management_user: str = ""
    management_password: str = ""  # Será encriptado en infraestructura
    coordinates: Optional[Coordinates] = None
    theoretical_capacity: str = ""  # Ej: "1Gbps"
    status: NodeStatus = NodeStatus.ACTIVE
    
    # Capabilities (descubiertos por análisis)
    supports_pppoe: bool = False
    supports_hotspot: bool = False
    supports_simple_queue: bool = False
    supports_pcq: bool = False
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def update_status(self, new_status: NodeStatus) -> None:
        """Actualiza estado del nodo"""
        self.status = new_status
        self.updated_at = datetime.utcnow()
    
    def enable_capability(self, method: ManagementMethod) -> None:
        """Habilita una capacidad detectada"""
        if method == ManagementMethod.PPPOE:
            self.supports_pppoe = True
        elif method == ManagementMethod.HOTSPOT:
            self.supports_hotspot = True
        elif method == ManagementMethod.SIMPLE_QUEUE:
            self.supports_simple_queue = True
        elif method == ManagementMethod.PCQ:
            self.supports_pcq = True


@dataclass
class NetworkSegment:
    """Segmento de Red (Pool de IPs)"""
    id: str = field(default_factory=lambda: str(uuid4()))
    node_id: str = ""
    name: str = ""
    cidr: str = ""  # Ej: "192.168.10.0/24"
    gateway: str = ""
    range_start: str = ""
    range_end: str = ""
    current_usage: int = 0
    technology: str = "NAT"  # NAT, PUBLIC, CGNAT
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def increment_usage(self) -> None:
        """Incrementa contador de uso"""
        self.current_usage += 1
    
    def decrement_usage(self) -> None:
        """Decrementa contador de uso"""
        if self.current_usage > 0:
            self.current_usage -= 1


@dataclass
class ServicePlan:
    """Plan de Servicio Comercial"""
    id: str = field(default_factory=lambda: str(uuid4()))
    commercial_name: str = ""
    base_cost: float = 0.0
    currency: str = "USD"
    download_speed: str = ""  # Ej: "50M"
    upload_speed: str = ""    # Ej: "10M"
    burst_config: Optional[BurstConfig] = None
    guaranteed_service: float = 80.0  # Porcentaje CIR
    traffic_priority: int = 4  # 1-8
    pcq_aggregation: Optional[str] = None  # Ej: "1:4"
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def calculate_price_with_tax(self, tax_rate: float) -> float:
        """Calcula precio con impuestos"""
        return self.base_cost * (1 + tax_rate)
    
    def has_burst(self) -> bool:
        """Verifica si tiene ráfagas configuradas"""
        return self.burst_config is not None


@dataclass
class BillingZone:
    """Zona de Facturación"""
    id: str = field(default_factory=lambda: str(uuid4()))
    code: str = ""  # Auto-generado: ZN01, ZN02, etc.
    name: str = ""
    cutoff_day: int = 15  # Día del mes (1-30)
    billing_day: int = 1   # Día de generación de factura
    due_day: int = 10      # Día de vencimiento
    tolerance_days: int = 3  # Días de gracia
    late_fee_percentage: float = 10.0  # Recargo por mora
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def calculate_late_fee(self, amount: float) -> float:
        """Calcula recargo por mora"""
        return amount * (self.late_fee_percentage / 100)


@dataclass
class Client:
    """Cliente (CRM)"""
    id: str = field(default_factory=lambda: str(uuid4()))
    subscriber_code: str = ""  # Código único de abonado
    person_type: str = "natural"  # natural, juridica
    legal_name: str = ""
    identity_document: str = ""
    contact_data: Dict[str, str] = field(default_factory=dict)
    credit_status: str = "normal"  # normal, overdue, uncollectable
    account_balance: float = 0.0
    billing_zone_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def add_charge(self, amount: float) -> None:
        """Añade cargo a la cuenta"""
        self.account_balance += amount
    
    def register_payment(self, amount: float) -> None:
        """Registra pago"""
        self.account_balance -= amount
    
    def is_overdue(self) -> bool:
        """Verifica si está en mora"""
        return self.credit_status == "overdue"


@dataclass
class Subscription:
    """
    Suscripción de Servicio
    Une Cliente + Plan + Nodo + Datos Técnicos
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    client_id: str = ""
    plan_id: str = ""
    node_id: str = ""
    installation_address: str = ""
    installation_coordinates: Optional[Coordinates] = None
    status: ClientStatus = ClientStatus.PENDING_INSTALL
    management_method: ManagementMethod = ManagementMethod.PPPOE
    
    # Parámetros técnicos (dinámicos según método)
    technical_params: Dict[str, Any] = field(default_factory=dict)
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    activated_at: Optional[datetime] = None
    suspended_at: Optional[datetime] = None
    
    def activate(self) -> None:
        """Activa la suscripción"""
        self.status = ClientStatus.ACTIVE
        self.activated_at = datetime.utcnow()
        self.suspended_at = None
    
    def suspend(self) -> None:
        """Suspende la suscripción"""
        self.status = ClientStatus.SUSPENDED
        self.suspended_at = datetime.utcnow()
    
    def cancel(self) -> None:
        """Cancela la suscripción"""
        self.status = ClientStatus.CANCELLED
    
    def get_technical_param(self, key: str) -> Optional[Any]:
        """Obtiene parámetro técnico"""
        return self.technical_params.get(key)
    
    def set_technical_param(self, key: str, value: Any) -> None:
        """Establece parámetro técnico"""
        self.technical_params[key] = value


@dataclass
class Invoice:
    """Documento de Cobro (Factura)"""
    id: str = field(default_factory=lambda: str(uuid4()))
    fiscal_number: str = ""
    client_id: str = ""
    billing_period: str = ""  # Ej: "2024-03"
    issue_date: datetime = field(default_factory=datetime.utcnow)
    due_date: Optional[datetime] = None
    items: List[Dict[str, Any]] = field(default_factory=list)
    subtotal: float = 0.0
    taxes: float = 0.0
    discounts: float = 0.0
    total: float = 0.0
    status: PaymentStatus = PaymentStatus.PENDING
    
    def add_item(self, description: str, amount: float) -> None:
        """Añade ítem a la factura"""
        self.items.append({
            "description": description,
            "amount": amount
        })
        self.recalculate()
    
    def recalculate(self) -> None:
        """Recalcula totales"""
        self.subtotal = sum(item["amount"] for item in self.items)
        self.total = self.subtotal + self.taxes - self.discounts
    
    def mark_as_paid(self) -> None:
        """Marca como pagada"""
        self.status = PaymentStatus.PAID
    
    def is_overdue(self) -> bool:
        """Verifica si está vencida"""
        if self.due_date and datetime.utcnow() > self.due_date:
            return self.status not in [PaymentStatus.PAID, PaymentStatus.CANCELLED]
        return False


@dataclass
class Payment:
    """Transacción de Pago"""
    id: str = field(default_factory=lambda: str(uuid4()))
    invoice_id: str = ""
    client_id: str = ""
    method: str = "cash"  # cash, transfer, card, online
    external_reference: Optional[str] = None
    amount: float = 0.0
    payment_date: datetime = field(default_factory=datetime.utcnow)
    cashier_user_id: Optional[str] = None
    notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Serializa a diccionario"""
        return {
            "id": self.id,
            "invoice_id": self.invoice_id,
            "amount": self.amount,
            "method": self.method,
            "date": self.payment_date.isoformat()
        }
