"""
Database Models - SQLAlchemy
Modelos de base de datos para el sistema
"""
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
import enum

Base = declarative_base()
from sqlalchemy import event
from sqlalchemy.engine import Engine
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


from sqlalchemy.orm import Query
from flask import g, has_request_context

@event.listens_for(Query, "before_compile", retval=True)
def ensure_tenant_isolation(query):
    """
    Interceptor global de consultas para aplicar aislamiento multi-tenant.
    Si hay un contexto de request y un tenant_id en g, se aplica el filtro automáticamente
    a cualquier modelo que tenga la columna 'tenant_id'.
    """
    if not has_request_context():
        return query
        
    tenant_id = getattr(g, 'tenant_id', None)
    if tenant_id is None:
        return query

    # SUPERADMIN BYPASS: Si el usuario es el SuperAdministrador del sistema, no filtramos.
    # El usuario 'admin' del tenant 1 (main) suele ser el superadmin.
    user = getattr(g, 'user', None)
    if user and user.role == 'admin' and tenant_id == 1:
        # Nota: Aquí podríamos añadir una lógica más granular si se desea
        return query

    for column in query.column_descriptions:
        entity = column.get('entity')
        if entity and hasattr(entity, 'tenant_id'):
            # SUPERADMIN BYPASS: Si es el tenant 1 y es admin, no filtramos.
            # YA SE MANEJA ARRIBA, pero aquí es donde se aplica el filtro.
            # Usamos enable_assertions(False) para permitir filtrar después de limit() o offset()
            query = query.enable_assertions(False).filter(entity.tenant_id == tenant_id)
            
    return query


@event.listens_for(Base, "before_insert", propagate=True)
def set_tenant_id(mapper, connection, target):
    """
    Asigna automáticamente el tenant_id a cualquier modelo nuevo 
    si hay un contexto de request activo.
    """
    if has_request_context():
        tenant_id = getattr(g, 'tenant_id', None)
        if tenant_id and hasattr(target, 'tenant_id'):
            # Si el objeto no tiene tenant_id o es None, lo asignamos desde el contexto global
            if getattr(target, 'tenant_id', None) is None:
                setattr(target, 'tenant_id', tenant_id)


class Tenant(Base):
    """Modelo de Empresa/Inquilino para SaaS"""
    __tablename__ = 'tenants'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    subdomain = Column(String(50), unique=True, index=True) # ej: 'norte' para norte.sgubm.com
    brand_color = Column(String(20), default='#4f46e5')
    logo_path = Column(String(255))
    
    is_active = Column(Boolean, default=True)
    plan_type = Column(String(20), default='basic') # basic, pro, enterprise
    
    # Configuración personalizada (JSON string)
    settings = Column(Text) # Custom SMTP, WhatsApp API Keys, etc.
    
    created_at = Column(DateTime, default=datetime.now)
    trial_ends_at = Column(DateTime)
    
    # Relations
    users = relationship('User', back_populates='tenant')
    routers = relationship('Router', back_populates='tenant')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'subdomain': self.subdomain,
            'brand_color': self.brand_color,
            'logo_path': self.logo_path,
            'is_active': self.is_active,
            'plan_type': self.plan_type,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


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


class UserRole(enum.Enum):
    ADMIN = "admin"
    COLLECTOR = "collector"
    TECHNICAL = "tecnico"
    SECRETARY = "secretaria"
    ADMIN_FEM = "administradora"
    PARTNER = "socio"


class RolePermission(Base):
    """Matriz de Permisos Granulares por Rol y Módulo"""
    __tablename__ = 'role_permissions'
    
    id = Column(Integer, primary_key=True)
    role_name = Column(String(50), nullable=False) # 'admin', 'collector'
    module = Column(String(50), nullable=False) # 'clients', 'finance', 'routers', 'system', 'whatsapp', etc.
    
    # Privilegios granulares
    can_view = Column(Boolean, default=False)
    can_create = Column(Boolean, default=False)
    can_edit = Column(Boolean, default=False)
    can_delete = Column(Boolean, default=False)
    can_print = Column(Boolean, default=False)
    can_revert = Column(Boolean, default=False)
    
    __table_args__ = (
        UniqueConstraint('role_name', 'module', name='uq_role_module_permission'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'role_name': self.role_name,
            'module': self.module,
            'can_view': self.can_view,
            'can_create': self.can_create,
            'can_edit': self.can_edit,
            'can_delete': self.can_delete,
            'can_print': self.can_print,
            'can_revert': self.can_revert
        }


class CollectorTransfer(Base):
    """Registro de envíos de dinero del cobrador a la empresa"""
    __tablename__ = 'collector_transfers'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    amount = Column(Float, nullable=False)
    method = Column(String(50), default='transfer')  # transfer, cash, yape, etc.
    notes = Column(Text)
    sent_at = Column(DateTime, default=datetime.now)
    created_at = Column(DateTime, default=datetime.now)
    
    user = relationship('User', foreign_keys=[user_id])
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'amount': self.amount,
            'method': self.method,
            'notes': self.notes,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class User(Base):
    """Modelo de Usuario para control de acceso (RBAC)"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True) # Se permitirá null temporalmente para migración
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False) # Guardaremos el hash, nunca en texto plano
    role = Column(String(20), default='collector') # admin, collector
    full_name = Column(String(100))
    identity_document = Column(String(50))
    phone_number = Column(String(50))
    email = Column(String(100))
    address = Column(Text)
    profit_percentage = Column(Float, default=0.0)
    bonus_amount = Column(Float, default=0.0)
    assigned_zone = Column(String(100))
    is_active = Column(Boolean, default=True)
    
    # Si es collector, a qué router/zona está asignado (opcional si es admin)
    assigned_router_id = Column(Integer, ForeignKey('routers.id', ondelete='SET NULL'), nullable=True) # DEPRECATED, kept for compatibility
    
    created_at = Column(DateTime, default=datetime.now)
    last_login = Column(DateTime, nullable=True)
    
    # Relación
    tenant = relationship('Tenant', back_populates='users')
    assigned_router = relationship('Router', foreign_keys=[assigned_router_id])
    assignments = relationship('CollectorAssignment', back_populates='user', cascade='all, delete-orphan', lazy='joined')

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'username': self.username,
            'role': self.role,
            'full_name': self.full_name,
            'identity_document': self.identity_document,
            'phone_number': self.phone_number,
            'email': self.email,
            'address': self.address,
            'profit_percentage': self.profit_percentage,
            'bonus_amount': self.bonus_amount,
            'assigned_zone': self.assigned_zone,
            'is_active': self.is_active,
            'assigned_router_id': self.assigned_router_id,
            'assigned_router_name': self.assigned_router.alias if self.assigned_router else 'N/A',
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'assignments': [a.to_dict() for a in self.assignments]
        }


class CollectorAssignment(Base):
    """Asignación de Cobrador a Router con comisiones específicas"""
    __tablename__ = 'collector_assignments'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    router_id = Column(Integer, ForeignKey('routers.id', ondelete='CASCADE'), nullable=False)
    
    # Comisiones específicas para este Router
    profit_percentage = Column(Float, default=0.0)
    bonus_amount = Column(Float, default=0.0)
    assigned_zone = Column(String(100))
    
    # Relaciones
    user = relationship('User', back_populates='assignments')
    router = relationship('Router')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'router_id': self.router_id,
            'router_name': self.router.alias if self.router else 'N/A',
            'profit_percentage': self.profit_percentage,
            'bonus_amount': self.bonus_amount,
            'assigned_zone': self.assigned_zone
        }


class UserSession(Base):
    """Sesiones activas de usuarios (Tokens)"""
    __tablename__ = 'user_sessions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    token = Column(String(100), unique=True, nullable=False, index=True)
    ip_address = Column(String(50))
    user_agent = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    expires_at = Column(DateTime, nullable=False)
    
    user = relationship('User')


class Router(Base):
    """Modelo de Router (Node)"""
    __tablename__ = 'routers'
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True)
    alias = Column(String(100), nullable=False)
    host_address = Column(String(50), nullable=False, unique=True)
    api_username = Column(String(50), default='admin')
    api_password = Column(String(255), nullable=False)
    api_port = Column(Integer, default=8728)
    ssh_port = Column(Integer, default=22)
    zone = Column(String(100), index=True)
    status = Column(String(20), default='offline', index=True) # Estandarizado a minúsculas
    notes = Column(Text)
    monitored_interfaces = Column(Text) # JSON string with preferences
    last_error = Column(Text)

    # Configuración de Facturación (Zona)
    billing_day = Column(Integer, default=1)   # Día de generación de factura
    grace_period = Column(Integer, default=5)  # Días de gracia
    cut_day = Column(Integer, default=10)      # Día de corte (suspensión)

    # Configuración de Gestión (New)
    management_method = Column(String(50), default='mixed') # pppoe, dhcp, mixed
    pppoe_ranges = Column(Text) # JSON/String with IP ranges for PPPoE
    dhcp_ranges = Column(Text)  # JSON/String with IP ranges for DHCP/Simple Queues
    exclusion_keywords = Column(Text) # Comma-separated words to exclude

    
    # Métricas
    uptime = Column(String(50))
    cpu_usage = Column(Float, default=0)
    memory_usage = Column(Float, default=0)
    clients_connected = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    last_sync = Column(DateTime)
    last_online_at = Column(DateTime)
    last_billing_date = Column(DateTime) # Fecha del último ciclo de facturación completado
    
    # Relationships
    tenant = relationship('Tenant', back_populates='routers')
    clients = relationship('Client', back_populates='router', cascade='all, delete-orphan')
    
    def to_dict(self):
        # El status ahora es garantizado string en DB
        status_val = str(self.status).lower() if self.status else 'offline'

        return {
            'id': self.id,
            'alias': self.alias,
            'host_address': self.host_address,
            'api_username': self.api_username,  # Necesario para editar
            'api_password': self.api_password,  # Solicitado por usuario para ver/editar
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
            'cut_day': self.cut_day,
            'management_method': self.management_method,
            'pppoe_ranges': self.pppoe_ranges,
            'dhcp_ranges': self.dhcp_ranges,
            'exclusion_keywords': self.exclusion_keywords
        }


class InternetPlan(Base):
    """Modelo de Plan de Internet Centralizado"""
    __tablename__ = 'internet_plans'

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True)
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
    
    created_at = Column(DateTime, default=datetime.now)
    
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
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True)
    router_id = Column(Integer, ForeignKey('routers.id'), nullable=False)
    
    # Plans (Centralized)
    plan_id = Column(Integer, ForeignKey('internet_plans.id'), nullable=True)
    internet_plan = relationship('InternetPlan', back_populates='clients')
    
    # Información personal
    subscriber_code = Column(String(50), unique=True, nullable=False, index=True)
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
    status = Column(String(20), default='active', index=True) # Enum cambiado a String por compatibilidad
    account_balance = Column(Float, default=0.0)
    monthly_fee = Column(Float, default=0.0)
    billing_enabled = Column(Boolean, default=True) # Habilitar/Deshabilitar facturación para este cliente
    
    # MikroTik specific
    mikrotik_id = Column(String(100))  # ID interno del router
    service_type = Column(String(50))  # pppoe, hotspot, queue, etc.
    mikrotik_queue_name = Column(String(100), index=True) # Nombre pre-resuelto de la cola
    mikrotik_interface_name = Column(String(100), index=True) # Nombre pre-resuelto de la interfaz
    
    # Estado conectado
    is_online = Column(Boolean, default=False)
    last_seen = Column(DateTime)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    last_payment_date = Column(DateTime)
    due_date = Column(DateTime)
    promise_date = Column(DateTime) # Fecha de promesa de pago
    broken_promises_count = Column(Integer, default=0) # Contador de promesas incumplidas (consecutivas)
    
    # Asignación de Cobrador (New)
    assigned_collector_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    
    # Relationships
    router = relationship('Router', back_populates='clients')
    assigned_collector = relationship('User', foreign_keys=[assigned_collector_id])
    payments = relationship('Payment', back_populates='client', cascade='all, delete-orphan')
    invoices = relationship('Invoice', back_populates='client', cascade='all, delete-orphan')
    traffic_history = relationship('ClientTrafficHistory', back_populates='client', cascade='all, delete-orphan')
    promise_history = relationship('PaymentPromise', back_populates='client', cascade='all, delete-orphan')
    deleted_payment_records = relationship('DeletedPayment', back_populates='client', cascade='all, delete-orphan')
    pending_operations = relationship('PendingOperation', back_populates='client', cascade='all, delete-orphan')
    
    def to_dict(self):
        status_val = str(self.status).lower() if self.status else 'active'

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
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'account_balance': self.account_balance,
            'monthly_fee': self.monthly_fee,
            'service_type': self.service_type,
            'mikrotik_queue_name': self.mikrotik_queue_name,
            'mikrotik_interface_name': self.mikrotik_interface_name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_payment_date': self.last_payment_date.isoformat() if self.last_payment_date else None,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'promise_date': self.promise_date.isoformat() if self.promise_date else None,
            'broken_promises_count': self.broken_promises_count or 0,
            'assigned_collector_id': self.assigned_collector_id,
            'assigned_collector_name': self.assigned_collector.username if self.assigned_collector else None,
            'router': self.router.alias if self.router else None,
            'zone': self.router.zone if self.router else None,
            'billing_enabled': self.billing_enabled if hasattr(self, 'billing_enabled') else True,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Payment(Base):
    """Modelo de Pago"""
    __tablename__ = 'payments'
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True)
    client_id = Column(Integer, ForeignKey('clients.id', ondelete='CASCADE'), nullable=False)
    
    # Información del pago
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default='COP') # COP, USD, VES
    payment_origin = Column(String(20), default='national') # national, international
    is_overpayment = Column(Boolean, default=False)
    payment_date = Column(DateTime, default=datetime.now, index=True)
    payment_method = Column(String(50), index=True)  # cash, transfer, card, etc.
    reference = Column(String(100))
    notes = Column(Text)
    
    # --- ERP Enterprise Fields ---
    exchange_rate = Column(Float, default=1.0)
    base_amount = Column(Float) # Monto en la moneda base del sistema (ej. USD/VES)
    fx_variance = Column(Float, default=0.0) # Diferencia en cambio (Ganancia/Pérdida en moneda base)
    tax_amount = Column(Float, default=0.0)
    tax_details = Column(Text) # JSON string con desglose (IGTF, IVA, etc.)
    transaction_hash = Column(String(64), index=True) # Integridad de auditoría
    # ----------------------------
    
    # Estado
    status = Column(String(20), default='paid', index=True) # Enum cambiado a String por compatibilidad
    alert_count = Column(Integer, default=0) # Alertas enviadas cuando está en pending
    rejection_reason = Column(String(500)) # Motivo del rechazo de un pago reportado
    
    # Período que cubre
    period_start = Column(DateTime)
    period_end = Column(DateTime)
    
    # Usuario que registró
    registered_by = Column(String(100))
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    client = relationship('Client', back_populates='payments')
    details = relationship('PaymentDetail', back_populates='payment', cascade='all, delete-orphan')
    
    def to_dict(self):
        status_val = str(self.status).lower() if self.status else 'paid'

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
            'alert_count': self.alert_count,
            'payment_date': self.payment_date.isoformat() if self.payment_date else None,
            'payment_method': self.payment_method,
            'reference': self.reference,
            'notes': self.notes,
            'status': status_val,
            'rejection_reason': self.rejection_reason,
            'period_start': self.period_start.isoformat() if self.period_start else None,
            'period_end': self.period_end.isoformat() if self.period_end else None,
            'registered_by': self.registered_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'exchange_rate': self.exchange_rate,
            'base_amount': self.base_amount,
            'fx_variance': self.fx_variance,
            'tax_amount': self.tax_amount,
            'tax_details': self.tax_details,
            'transaction_hash': self.transaction_hash,
            'details': [d.to_dict() for d in self.details]
        }


class PaymentDetail(Base):
    """Detalle de un componente de pago mixto"""
    __tablename__ = 'payment_details'
    
    id = Column(Integer, primary_key=True)
    payment_id = Column(Integer, ForeignKey('payments.id', ondelete='CASCADE'), nullable=False)
    
    amount = Column(Float, nullable=False)
    currency = Column(String(10), nullable=False)
    method = Column(String(50), nullable=False)
    exchange_rate = Column(Float, default=1.0)
    base_amount = Column(Float) # Monto en la moneda base (USD)
    reference = Column(String(100))
    notes = Column(Text)
    
    # Relationships
    payment = relationship('Payment', back_populates='details')

    def to_dict(self):
        return {
            'id': self.id,
            'payment_id': self.payment_id,
            'amount': self.amount,
            'currency': self.currency,
            'method': self.method,
            'exchange_rate': self.exchange_rate,
            'base_amount': self.base_amount,
            'reference': self.reference,
            'notes': self.notes
        }


class DeletedPayment(Base):
    """
    Papelera de Pagos
    Almacena pagos eliminados para auditoría y posible restauración.
    """
    __tablename__ = 'deleted_payments'
    
    id = Column(Integer, primary_key=True)
    original_id = Column(Integer) # ID original en la tabla payments
    client_id = Column(Integer, ForeignKey('clients.id', ondelete='CASCADE'), nullable=False)
    
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default='COP')
    payment_date = Column(DateTime)
    payment_method = Column(String(50))
    reference = Column(String(100))
    notes = Column(Text)
    
    # Metadatos de eliminación
    deleted_at = Column(DateTime, default=datetime.now)
    deleted_by = Column(String(100))
    reason = Column(Text)
    
    # Relationship (Sin cascade para no borrar el registro de la papelera)
    client = relationship('Client', back_populates='deleted_payment_records')
    
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
    
    created_at = Column(DateTime, default=datetime.now)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'cidr': self.cidr,
            'router_id': self.router_id
        }






class PendingOperation(Base):
    """Modelo de Operación Pendiente - Para sincronización con MikroTik cuando router está offline"""
    __tablename__ = 'pending_operations'
    
    id = Column(Integer, primary_key=True)
    operation_type = Column(String(50), nullable=False)  # 'suspend', 'activate', 'restore'
    client_id = Column(Integer, ForeignKey('clients.id', ondelete='CASCADE'), nullable=False)
    router_id = Column(Integer, ForeignKey('routers.id', ondelete='CASCADE'), nullable=False)
    target_status = Column(String(20))  # Estado objetivo del cliente
    ip_address = Column(String(50))  # IP del cliente
    operation_data = Column(Text)  # JSON con datos adicionales
    created_at = Column(DateTime, default=datetime.now)
    attempts = Column(Integer, default=0)
    last_attempt = Column(DateTime)
    error_message = Column(Text)
    status = Column(String(20), default='pending')  # 'pending', 'completed', 'failed'
    
    # Relaciones
    client = relationship('Client', back_populates='pending_operations')
    router = relationship('Router', backref='pending_operations_router') 
    
    def to_dict(self):
        return {
            'id': self.id,
            'operation_type': self.operation_type,
            'client_id': self.client_id,
            'router_id': self.router_id,
            'target_status': self.target_status,
            'ip_address': self.ip_address,
            'operation_data': self.operation_data,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'attempts': self.attempts,
            'last_attempt': self.last_attempt.isoformat() if self.last_attempt else None,
            'error_message': self.error_message,
            'status': self.status
        }


class ClientTrafficHistory(Base):
    """Historial de Tráfico de Cliente (Snapshots para Gráficas)"""
    __tablename__ = 'client_traffic_history'
    
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('clients.id', ondelete='CASCADE'), nullable=False)
    timestamp = Column(DateTime, default=datetime.now)
    
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
    jitter_ms = Column(Float, default=0.0) # Varianza de latencia (Estabilidad)

    # Relación
    client = relationship('Client', back_populates='traffic_history')

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
            'packet_loss_pct': self.packet_loss_pct,
            'jitter_ms': self.jitter_ms
        }


class Invoice(Base):
    """Modelo de Factura"""
    __tablename__ = 'invoices'
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True)
    client_id = Column(Integer, ForeignKey('clients.id', ondelete='CASCADE'), nullable=False)
    
    issue_date = Column(DateTime, default=datetime.now, index=True) # Fecha de emisión
    due_date = Column(DateTime, nullable=False, index=True)            # Fecha de vencimiento
    
    total_amount = Column(Float, default=0.0)
    status = Column(String(20), default='unpaid', index=True) # unpaid, paid, overdue, cancelled
    pdf_path = Column(String(255)) # Ruta al archivo PDF generado
    notes = Column(Text) # Notas o descripción de la factura
    
    # --- ERP Enterprise Fields ---
    currency = Column(String(10), default='COP')
    exchange_rate = Column(Float, default=1.0)
    subtotal_amount = Column(Float, default=0.0)
    tax_amount = Column(Float, default=0.0)
    tax_details = Column(Text) # JSON con desglose
    is_fiscal = Column(Boolean, default=False) # Si es factura legal SENIAT/DIAN
    base_amount = Column(Float, default=0.0)
    transaction_hash = Column(String(64), index=True)
    # ----------------------------
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
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
            'currency': self.currency,
            'exchange_rate': self.exchange_rate,
            'subtotal': self.subtotal_amount,
            'tax_amount': self.tax_amount,
            'tax_details': self.tax_details,
            'is_fiscal': self.is_fiscal,
            'created_at': self.created_at.isoformat(),
            'items': [item.to_dict() for item in self.items]
        }


class InvoiceItem(Base):
    """Ítem de Factura"""
    __tablename__ = 'invoice_items'
    
    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey('invoices.id', ondelete='CASCADE'), nullable=False)
    
    description = Column(String(200), nullable=False)
    unit_price = Column(Float, nullable=False)
    quantity = Column(Integer, default=1)
    total = Column(Float, default=0.0)
    
    # Relationship
    invoice = relationship('Invoice', back_populates='items')
    
    def to_dict(self):
        return {
            'id': self.id,
            'description': self.description,
            'unit_price': self.unit_price,
            'quantity': self.quantity,
            'total': self.total
        }


class AuditLog(Base):
    """
    Sistema de Kardex / Auditoría
    Registra cada operación realizada en el sistema.
    """
    __tablename__ = 'audit_logs'
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True)
    timestamp = Column(DateTime, default=datetime.now)
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


class PaymentPromise(Base):
    """Historial de Promesas de Pago y Seguimiento de Cumplimiento"""
    __tablename__ = 'payment_promises'
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True)
    client_id = Column(Integer, ForeignKey('clients.id', ondelete='CASCADE'), nullable=False)
    
    promise_date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    
    # status: 'pending', 'fulfilled', 'broken'
    status = Column(String(20), default='pending')
    
    notes = Column(Text)
    
    # Relación
    client = relationship('Client', back_populates='promise_history')
    
    def to_dict(self):
        return {
            'id': self.id,
            'client_id': self.client_id,
            'promise_date': self.promise_date.isoformat(),
            'created_at': self.created_at.isoformat(),
            'status': self.status,
            'notes': self.notes
        }


class Expense(Base):
    """Modelo de Gasto / Deducible"""
    __tablename__ = 'expenses'
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True)
    description = Column(String(255), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default='COP')
    expense_date = Column(DateTime, default=datetime.now)
    
    # Categorización
    category = Column(String(50)) # 'fixed' (Fijo), 'variable' (Variable/Deducible)
    is_recurring = Column(Boolean, default=False) # Si es recurrente mensual
    
    # Filtros de Asignación (New)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    router_id = Column(Integer, ForeignKey('routers.id', ondelete='CASCADE'), nullable=True)
    
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    created_by = Column(String(100)) # Usuario que registró

    # --- ERP Enterprise Fields ---
    base_amount = Column(Float)
    exchange_rate = Column(Float, default=1.0)
    tax_deductible = Column(Boolean, default=True)
    tax_details = Column(Text)
    transaction_hash = Column(String(64), index=True)
    # ----------------------------
    
    def to_dict(self):
        return {
            'id': self.id,
            'description': self.description,
            'amount': self.amount,
            'currency': self.currency,
            'expense_date': self.expense_date.isoformat() if self.expense_date else None,
            'category': self.category,
            'is_recurring': self.is_recurring,
            'user_id': self.user_id,
            'router_id': self.router_id,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'created_by': self.created_by,
            'base_amount': self.base_amount,
            'exchange_rate': self.exchange_rate,
            'tax_deductible': self.tax_deductible,
            'tax_details': self.tax_details
        }


class WhatsAppMessage(Base):
    """Modelo para persistencia de mensajes de WhatsApp"""
    __tablename__ = 'whatsapp_messages'
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    client_id = Column(Integer, ForeignKey('clients.id', ondelete='SET NULL'), nullable=True)
    phone = Column(String(50), nullable=False)
    
    message_text = Column(Text, nullable=False)
    is_outgoing = Column(Boolean, default=False) # True si es enviado por el sistema
    
    # Metadatos del agente
    intent_identified = Column(String(100))
    ai_response_id = Column(String(100)) # ID de respuesta de Gemini/Meta
    
    timestamp = Column(DateTime, default=datetime.now)
    
    # Relación
    client = relationship('Client', backref='whatsapp_history')

    def to_dict(self):
        return {
            'id': self.id,
            'client_id': self.client_id,
            'client_name': self.client.legal_name if self.client else 'Unknown',
            'client_cedula': self.client.identity_document if self.client else None,
            'client_code': self.client.subscriber_code if self.client else None,
            'phone': self.phone,
            'message_text': self.message_text,
            'is_outgoing': self.is_outgoing,
            'intent': self.intent_identified,
            'timestamp': self.timestamp.isoformat() if self.timestamp else datetime.now().isoformat()
        }


class SupportTicket(Base):
    """Tickets de soporte/revisión para reportar fallas de clientes"""
    __tablename__ = 'support_tickets'
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True)
    client_id = Column(Integer, ForeignKey('clients.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    subject = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String(20), default='open') # open, in_progress, resolved
    image_path = Column(String(255), nullable=True) # Ruta de la captura de pantalla o imagen anexada
    created_at = Column(DateTime, default=datetime.now)
    resolved_at = Column(DateTime, nullable=True)
    
    # New Resolution Fields (Minimalist Premium V3)
    actual_failure = Column(Text, nullable=True)
    resolution_details = Column(Text, nullable=True)
    technicians = Column(Text, nullable=True)
    materials_used = Column(Text, nullable=True)
    support_cost = Column(Float, default=0.0)
    admin_observations = Column(Text, nullable=True)
    support_date = Column(DateTime, nullable=True) # Fecha efectiva del trabajo
    
    # Relations
    client = relationship('Client')
    user = relationship('User')
    
    def to_dict(self):
        return {
            'id': self.id,
            'client_id': self.client_id,
            'client_name': self.client.legal_name if self.client else None,
            'user_id': self.user_id,
            'user_name': self.user.username if self.user else None,
            'subject': self.subject,
            'description': self.description,
            'status': self.status,
            'image_path': self.image_path,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'actual_failure': self.actual_failure,
            'resolution_details': self.resolution_details,
            'technicians': self.technicians,
            'materials_used': self.materials_used,
            'support_cost': self.support_cost,
            'admin_observations': self.admin_observations,
            'support_date': self.support_date.isoformat() if self.support_date else None
        }


class SystemSetting(Base):
    """Modelo para configuración general del sistema"""
    __tablename__ = 'system_settings'
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text)
    description = Column(String(255))
    category = Column(String(50), default='general')
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            'key': self.key,
            'value': self.value,
            'category': self.category,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class SystemIncident(Base):
    """
    RECICLADOR - Centinela de Errores y Fallos del Sistema
    Captura excepciones, fallos de red y errores críticos para reparación proactiva.
    """
    __tablename__ = 'system_incidents'
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True)
    
    # Clasificación
    severity = Column(String(20), default='error') # critical, error, warning, info
    category = Column(String(50)) # 'api', 'mikrotik', 'database', 'system', 'auth'
    module = Column(String(100)) # Nombre del archivo o módulo donde ocurrió
    
    # Detalles del error
    error_type = Column(String(100)) # e.g., 'ValueError', 'mikrotik.ConnectionError'
    message = Column(Text, nullable=False)
    stack_trace = Column(Text)
    
    # Contexto de la Petición (JSON)
    url = Column(String(255))
    method = Column(String(10))
    request_params = Column(Text) # JSON string
    request_payload = Column(Text) # JSON string (obfuscated)
    
    # Contexto de Usuario
    user_id = Column(Integer)
    username = Column(String(100))
    ip_address = Column(String(50))
    
    # Estado de Resolución
    status = Column(String(20), default='new') # new, investigating, resolved, recurring, ignored
    resolution_notes = Column(Text)
    resolved_at = Column(DateTime)
    resolved_by = Column(String(100))
    
    # Inteligencia Artificial (Feedback)
    ai_analysis = Column(Text) # Sugerencia de reparación por IA
    root_cause = Column(String(255))
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Metadata técnica (JSON)
    environment_meta = Column(Text) # Versión del server, OS, python ver, etc.

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'severity': self.severity,
            'category': self.category,
            'module': self.module,
            'error_type': self.error_type,
            'message': self.message,
            'stack_trace': self.stack_trace,
            'url': self.url,
            'method': self.method,
            'user_id': self.user_id,
            'username': self.username,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'ai_analysis': self.ai_analysis
        }


class SystemNotification(Base):
    """
    Control de notificaciones interactivas para el administrador.
    Permite flujos de aprobación (Ciclo de Facturación) y alertas críticas.
    """
    __tablename__ = 'system_notifications'
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True)
    
    title = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String(30), default='info') # 'approval_required', 'alert', 'info'
    action_key = Column(String(50)) # e.g. 'monthly_billing_cycle_2024_03'
    
    status = Column(String(20), default='pending') # pending, accepted, rejected, dismissed
    
    # Metadata para la acción (JSON)
    action_data = Column(Text) 
    
    expires_at = Column(DateTime)
    remind_at = Column(DateTime)
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'title': self.title,
            'message': self.message,
            'type': self.type,
            'action_key': self.action_key,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'remind_at': self.remind_at.isoformat() if self.remind_at else None
        }


# Database initialization
def init_db(database_url='sqlite:///sgubm.db'):
    """Inicializa la base de datos"""
    # Para SQLite aumentamos el pool por el Sentinel y el Servidor Web corriendo juntos
    if 'sqlite' in database_url:
        engine = create_engine(
            database_url, 
            echo=False,
            pool_size=50,          # Incrementar a 50
            max_overflow=20,       # 20 de desbordamiento en picos
            pool_recycle=1800,     # Reciclar cada 30 min
            pool_timeout=45,       # Tolerancia de bloqueo de 45 segs
            connect_args={
                'check_same_thread': False,
                'timeout': 45.0,     # Time out nativo de SQLite muy alto
            }
        )
        
        # Activar PRAGMAS de alta concurrencia como WAL y SYNCHRONOUS
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA cache_size=-64000") # Usar 64MB de RAM en caché
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.close()
            
    else:
        engine = create_engine(database_url, echo=False)
        
    Base.metadata.create_all(engine)
    return engine


def get_session(engine):
    """Crea una sesión de base de datos"""
    Session = sessionmaker(bind=engine)
    return Session()
