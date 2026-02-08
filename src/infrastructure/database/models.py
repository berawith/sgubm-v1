"""
Database Models - SQLAlchemy
Modelos de base de datos para el sistema
"""
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
import enum

Base = declarative_base()


class RouterStatus(enum.Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    WARNING = "warning"


class ClientStatus(enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    INACTIVE = "inactive"


class PaymentStatus(enum.Enum):
    PAID = "paid"
    PENDING = "pending"
    CANCELLED = "cancelled"


class Router(Base):
    """Modelo de Router (Node)"""
    __tablename__ = 'routers'
    
    id = Column(Integer, primary_key=True)
    alias = Column(String(100), nullable=False)
    host_address = Column(String(50), nullable=False, unique=True)
    api_username = Column(String(50), default='admin')
    api_password = Column(String(255), nullable=False)
    api_port = Column(Integer, default=8728)
    ssh_port = Column(Integer, default=22)
    zone = Column(String(100))
    status = Column(String(20), default='offline') # Enum cambiado a String por compatibilidad
    notes = Column(Text)
    monitored_interfaces = Column(Text) # JSON string with preferences
    last_error = Column(Text)

    # Configuración de Facturación (Zona)
    billing_day = Column(Integer, default=1)   # Día de generación de factura
    grace_period = Column(Integer, default=5)  # Días de gracia
    cut_day = Column(Integer, default=10)      # Día de corte (suspensión)

    
    # Métricas
    uptime = Column(String(50))
    cpu_usage = Column(Float, default=0)
    memory_usage = Column(Float, default=0)
    clients_connected = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_sync = Column(DateTime)
    last_online_at = Column(DateTime)
    last_billing_date = Column(DateTime) # Fecha del último ciclo de facturación completado
    
    # Relationships
    clients = relationship('Client', back_populates='router', cascade='all, delete-orphan')
    
    def to_dict(self):
        # Manejo robusto de status
        status_val = self.status if self.status else 'offline'
        # Si por alguna razón sigue llegando como enum (raro tras cambio a String)
        if hasattr(status_val, 'value'):
            status_val = status_val.value

        return {
            'id': self.id,
            'alias': self.alias,
            'host_address': self.host_address,
            'api_port': self.api_port,
            'ssh_port': self.ssh_port,
            'zone': self.zone,
            'status': status_val.lower() if status_val else 'offline',
            'uptime': self.uptime,
            'cpu_usage': self.cpu_usage,
            'memory_usage': self.memory_usage,
            'clients_connected': self.clients_connected,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_sync': self.last_sync.isoformat() if self.last_sync else None,
            'last_online_at': self.last_online_at.isoformat() if self.last_online_at else None,
            'last_error': self.last_error,
            'notes': self.notes,
            'monitored_interfaces': self.monitored_interfaces,
            'billing_day': self.billing_day,
            'grace_period': self.grace_period,
            'cut_day': self.cut_day
        }


class InternetPlan(Base):
    """Modelo de Plan de Internet Centralizado"""
    __tablename__ = 'internet_plans'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    download_speed = Column(Integer, nullable=False) # kbps
    upload_speed = Column(Integer, nullable=False)   # kbps
    monthly_price = Column(Float, default=0.0)
    currency = Column(String(10), default='COP')
    service_type = Column(String(50), default='pppoe') # pppoe, hotspot, queue
    mikrotik_profile = Column(String(100)) # Profile en MikroTik / Queue Type
    router_id = Column(Integer, ForeignKey('routers.id'), nullable=True) # Router asociado
    
    # Configuración avanzada
    burst_limit = Column(String(50))
    burst_threshold = Column(String(50))
    burst_time = Column(String(50))
    priority = Column(Integer, default=8)
    aggregation = Column(String(20)) # 1:1, 1:2, 1:4, etc.
    
    # PPPoE Specifics
    local_address = Column(String(50))  # IP local para el profile
    remote_address = Column(String(50)) # Pool de IPs remotas
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    clients = relationship('Client', back_populates='internet_plan')
    router = relationship('Router')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'download_speed': self.download_speed,
            'upload_speed': self.upload_speed,
            'monthly_price': self.monthly_price,
            'currency': self.currency,
            'service_type': self.service_type,
            'mikrotik_profile': self.mikrotik_profile,
            'router_id': self.router_id,
            'router_name': self.router.alias if self.router else 'Global',
            'burst_limit': self.burst_limit,
            'priority': self.priority,
            'local_address': self.local_address,
            'remote_address': self.remote_address
        }


class Client(Base):
    """Modelo de Cliente"""
    __tablename__ = 'clients'
    
    id = Column(Integer, primary_key=True)
    router_id = Column(Integer, ForeignKey('routers.id'), nullable=False)
    
    # Plans (Centralized)
    plan_id = Column(Integer, ForeignKey('internet_plans.id'), nullable=True)
    internet_plan = relationship('InternetPlan', back_populates='clients')
    
    # Información personal
    subscriber_code = Column(String(50), unique=True, nullable=False)
    legal_name = Column(String(200), nullable=False)
    identity_document = Column(String(50))
    email = Column(String(100))
    phone = Column(String(50))
    address = Column(Text)
    
    # Información de servicio
    username = Column(String(100), nullable=False)
    password = Column(String(100))
    ip_address = Column(String(50))
    mac_address = Column(String(50))
    plan_name = Column(String(100))
    download_speed = Column(String(20))
    upload_speed = Column(String(20))
    
    # Estado y balance
    status = Column(String(20), default='active') # Enum cambiado a String por compatibilidad
    account_balance = Column(Float, default=0.0)
    monthly_fee = Column(Float, default=0.0)
    
    # MikroTik specific
    mikrotik_id = Column(String(100))  # ID interno del router
    service_type = Column(String(50))  # pppoe, hotspot, queue, etc.
    
    # Estado conectado
    is_online = Column(Boolean, default=False)
    last_seen = Column(DateTime)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_payment_date = Column(DateTime)
    due_date = Column(DateTime)
    promise_date = Column(DateTime) # Fecha de promesa de pago
    
    # Relationships
    router = relationship('Router', back_populates='clients')
    payments = relationship('Payment', back_populates='client', cascade='all, delete-orphan')
    invoices = relationship('Invoice', back_populates='client', cascade='all, delete-orphan')
    
    def to_dict(self):
        # Manejo robusto de status
        status_val = self.status if self.status else 'active'
        if hasattr(status_val, 'value'):
            status_val = status_val.value

        return {
            'id': self.id,
            'router_id': self.router_id,
            'plan_id': self.plan_id,
            'subscriber_code': self.subscriber_code,
            'legal_name': self.legal_name,
            'identity_document': self.identity_document,
            'email': self.email,
            'phone': self.phone,
            'address': self.address,
            'username': self.username,
            'ip_address': self.ip_address,
            'mac_address': self.mac_address,
            'plan_name': self.plan_name,
            'download_speed': self.download_speed,
            'upload_speed': self.upload_speed,
            'status': status_val,
            'is_online': self.is_online,
            'last_seen': self.last_seen.isoformat() + 'Z' if self.last_seen else None,
            'account_balance': self.account_balance,
            'monthly_fee': self.monthly_fee,
            'service_type': self.service_type,
            'created_at': self.created_at.isoformat() + 'Z' if self.created_at else None,
            'last_payment_date': self.last_payment_date.isoformat() + 'Z' if self.last_payment_date else None,
            'due_date': self.due_date.isoformat() + 'Z' if self.due_date else None,
            'promise_date': self.promise_date.isoformat() + 'Z' if self.promise_date else None,
            'router': self.router.alias if self.router else None,
            'zone': self.router.zone if self.router else None
        }


class Payment(Base):
    """Modelo de Pago"""
    __tablename__ = 'payments'
    
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    
    # Información del pago
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default='COP') # COP, USD, VES
    payment_origin = Column(String(20), default='national') # national, international
    is_overpayment = Column(Boolean, default=False)
    payment_date = Column(DateTime, default=datetime.utcnow)
    payment_method = Column(String(50))  # cash, transfer, card, etc.
    reference = Column(String(100))
    notes = Column(Text)
    
    # Estado
    status = Column(String(20), default='paid') # Enum cambiado a String por compatibilidad
    
    # Período que cubre
    period_start = Column(DateTime)
    period_end = Column(DateTime)
    
    # Usuario que registró
    registered_by = Column(String(100))
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    client = relationship('Client', back_populates='payments')
    
    def to_dict(self):
        # Manejo robusto de status
        status_val = self.status if self.status else 'paid'
        if hasattr(status_val, 'value'):
            status_val = status_val.value

        return {
            'id': self.id,
            'client_id': self.client_id,
            'client_name': self.client.legal_name if self.client else None,
            'subscriber_code': self.client.subscriber_code if self.client else None,
            'account_balance': self.client.account_balance if self.client else 0,
            'monthly_fee': self.client.monthly_fee if self.client else 0,
            'client_status': self.client.status if self.client else 'active',
            'amount': self.amount,
            'currency': self.currency,
            'payment_origin': self.payment_origin,
            'is_overpayment': self.is_overpayment,
            'payment_date': self.payment_date.isoformat() if self.payment_date else None,
            'payment_method': self.payment_method,
            'reference': self.reference,
            'notes': self.notes,
            'status': status_val,
            'period_start': self.period_start.isoformat() if self.period_start else None,
            'period_end': self.period_end.isoformat() if self.period_end else None,
            'registered_by': self.registered_by,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class DeletedPayment(Base):
    """
    Papelera de Pagos
    Almacena pagos eliminados para auditoría y posible restauración.
    """
    __tablename__ = 'deleted_payments'
    
    id = Column(Integer, primary_key=True)
    original_id = Column(Integer) # ID original en la tabla payments
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default='COP')
    payment_date = Column(DateTime)
    payment_method = Column(String(50))
    reference = Column(String(100))
    notes = Column(Text)
    
    # Metadatos de eliminación
    deleted_at = Column(DateTime, default=datetime.utcnow)
    deleted_by = Column(String(100))
    reason = Column(Text)
    
    # Relationship (Sin cascade para no borrar el registro de la papelera)
    client = relationship('Client')
    
    def to_dict(self):
        return {
            'id': self.id,
            'original_id': self.original_id,
            'client_id': self.client_id,
            'client_name': self.client.legal_name if self.client else None,
            'subscriber_code': self.client.subscriber_code if self.client else None,
            'amount': self.amount,
            'currency': self.currency,
            'payment_date': self.payment_date.isoformat() if self.payment_date else None,
            'payment_method': self.payment_method,
            'reference': self.reference,
            'notes': self.notes,
            'deleted_at': self.deleted_at.isoformat() if self.deleted_at else None,
            'deleted_by': self.deleted_by,
            'reason': self.reason
        }


class NetworkSegment(Base):
    """Modelo de Segmento de Red"""
    __tablename__ = 'network_segments'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    cidr = Column(String(50), nullable=False)
    router_id = Column(Integer, ForeignKey('routers.id'), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'cidr': self.cidr,
            'router_id': self.router_id
        }



class SyncQueue(Base):
    """Cola de Sincronización (Sentinel)"""
    __tablename__ = 'sync_queue'
    
    id = Column(Integer, primary_key=True)
    router_id = Column(Integer, ForeignKey('routers.id'), nullable=False)
    client_id = Column(Integer, nullable=True) # Opcional, solo referencia
    operation = Column(String(50), nullable=False) # 'update', 'create', 'suspend', 'delete'
    payload = Column(Text, nullable=False) # JSON data
    status = Column(String(20), default='pending') # pending, retrying, failed, completed
    attempts = Column(Integer, default=0)
    last_error = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'router_id': self.router_id,
            'operation': self.operation,
            'status': self.status,
            'attempts': self.attempts,
            'created_at': self.created_at.isoformat()
        }


class ClientTrafficHistory(Base):
    """Historial de Tráfico de Cliente (Snapshots para Gráficas)"""
    __tablename__ = 'client_traffic_history'
    
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Velocidad en el momento del snapshot (bps)
    download_bps = Column(Float, default=0.0)
    upload_bps = Column(Float, default=0.0)
    
    # Acumulado total (opcional, para reportes de consumo mensual en MB/GB)
    download_bytes = Column(Float, default=0.0)
    upload_bytes = Column(Float, default=0.0)
    
    # Nuevo: Estado del cliente en el momento del snapshot
    is_online = Column(Boolean, default=False)
    
    # Nuevo: Puntaje de calidad de servicio (0-100) basado en estabilidad
    quality_score = Column(Float, default=100.0)
    
    # Nuevas Métricas para el "Golden Signal" Engine
    latency_ms = Column(Integer, default=0) # Latencia promedio (Ping)
    packet_loss_pct = Column(Float, default=0.0) # Pérdida de paquetes (%)

    # Relación
    client = relationship('Client')

    def to_dict(self):
        return {
            'timestamp': self.timestamp.isoformat(),
            'download_bps': self.download_bps,
            'upload_bps': self.upload_bps,
            'download_bytes': self.download_bytes,
            'upload_bytes': self.upload_bytes,
            'is_online': self.is_online,
            'quality_score': self.quality_score,
            'latency_ms': self.latency_ms,
            'packet_loss_pct': self.packet_loss_pct
        }


class Invoice(Base):
    """Modelo de Factura"""
    __tablename__ = 'invoices'
    
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    
    issue_date = Column(DateTime, default=datetime.utcnow) # Fecha de emisión
    due_date = Column(DateTime, nullable=False)            # Fecha de vencimiento
    
    total_amount = Column(Float, default=0.0)
    status = Column(String(20), default='unpaid') # unpaid, paid, overdue, cancelled
    pdf_path = Column(String(255)) # Ruta al archivo PDF generado
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    client = relationship('Client', back_populates='invoices')
    items = relationship('InvoiceItem', back_populates='invoice', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'client_id': self.client_id,
            'client_name': self.client.legal_name if self.client else None,
            'issue_date': self.issue_date.isoformat(),
            'due_date': self.due_date.isoformat(),
            'total_amount': self.total_amount,
            'status': self.status,
            'pdf_path': self.pdf_path,
            'created_at': self.created_at.isoformat(),
            'items': [item.to_dict() for item in self.items]
        }


class InvoiceItem(Base):
    """Ítem de Factura"""
    __tablename__ = 'invoice_items'
    
    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey('invoices.id'), nullable=False)
    
    description = Column(String(200), nullable=False)
    amount = Column(Float, nullable=False)
    
    # Relationship
    invoice = relationship('Invoice', back_populates='items')
    
    def to_dict(self):
        return {
            'id': self.id,
            'description': self.description,
            'amount': self.amount
        }


class AuditLog(Base):
    """
    Sistema de Kardex / Auditoría
    Registra cada operación realizada en el sistema.
    """
    __tablename__ = 'audit_logs'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer) # ID del usuario que realizó la acción
    username = Column(String(100))
    
    category = Column(String(50)) # 'accounting', 'client', 'system', 'router'
    operation = Column(String(100)) # 'payment_registered', 'client_created', 'mass_sync', etc.
    
    entity_type = Column(String(50)) # 'client', 'payment', 'invoice', etc.
    entity_id = Column(Integer)
    
    description = Column(Text)
    previous_state = Column(Text) # JSON string
    new_state = Column(Text) # JSON string
    
    # Metadatos técnicos
    ip_address = Column(String(50))
    user_agent = Column(Text)

    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'user_id': self.user_id,
            'username': self.username,
            'category': self.category,
            'operation': self.operation,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'description': self.description,
            'created_at': self.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        }


# Database initialization
def init_db(database_url='sqlite:///sgubm.db'):
    """Inicializa la base de datos"""
    # Para SQLite aumentamos el pool por el Sentinel y el Servidor Web corriendo juntos
    if 'sqlite' in database_url:
        engine = create_engine(
            database_url, 
            echo=False,
            pool_size=20,
            max_overflow=10,
            pool_recycle=3600,
            connect_args={'check_same_thread': False}
        )
    else:
        engine = create_engine(database_url, echo=False)
        
    Base.metadata.create_all(engine)
    return engine


def get_session(engine):
    """Crea una sesión de base de datos"""
    Session = sessionmaker(bind=engine)
    return Session()
