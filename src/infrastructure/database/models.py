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
    
    # Métricas
    uptime = Column(String(50))
    cpu_usage = Column(Float, default=0)
    memory_usage = Column(Float, default=0)
    clients_connected = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_sync = Column(DateTime)
    
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
            'status': status_val,
            'uptime': self.uptime,
            'cpu_usage': self.cpu_usage,
            'memory_usage': self.memory_usage,
            'clients_connected': self.clients_connected,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_sync': self.last_sync.isoformat() if self.last_sync else None,
            'notes': self.notes
        }


class Client(Base):
    """Modelo de Cliente"""
    __tablename__ = 'clients'
    
    id = Column(Integer, primary_key=True)
    router_id = Column(Integer, ForeignKey('routers.id'), nullable=False)
    
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
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_payment_date = Column(DateTime)
    due_date = Column(DateTime)
    
    # Relationships
    router = relationship('Router', back_populates='clients')
    payments = relationship('Payment', back_populates='client', cascade='all, delete-orphan')
    
    def to_dict(self):
        # Manejo robusto de status
        status_val = self.status if self.status else 'active'
        if hasattr(status_val, 'value'):
            status_val = status_val.value

        return {
            'id': self.id,
            'router_id': self.router_id,
            'subscriber_code': self.subscriber_code,
            'legal_name': self.legal_name,
            'identity_document': self.identity_document,
            'email': self.email,
            'phone': self.phone,
            'address': self.address,
            'username': self.username,
            'ip_address': self.ip_address,
            'plan_name': self.plan_name,
            'download_speed': self.download_speed,
            'upload_speed': self.upload_speed,
            'status': status_val,
            'account_balance': self.account_balance,
            'monthly_fee': self.monthly_fee,
            'service_type': self.service_type,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_payment_date': self.last_payment_date.isoformat() if self.last_payment_date else None,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'router': self.router.alias if self.router else None
        }


class Payment(Base):
    """Modelo de Pago"""
    __tablename__ = 'payments'
    
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    
    # Información del pago
    amount = Column(Float, nullable=False)
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
        return {
            'id': self.id,
            'client_id': self.client_id,
            'client_name': self.client.legal_name if self.client else None,
            'subscriber_code': self.client.subscriber_code if self.client else None,
            'amount': self.amount,
            'payment_date': self.payment_date.isoformat() if self.payment_date else None,
            'payment_method': self.payment_method,
            'reference': self.reference,
            'notes': self.notes,
            'status': self.status.value if self.status else 'paid',
            'period_start': self.period_start.isoformat() if self.period_start else None,
            'period_end': self.period_end.isoformat() if self.period_end else None,
            'registered_by': self.registered_by,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# Database initialization
def init_db(database_url='sqlite:///sgubm.db'):
    """Inicializa la base de datos"""
    engine = create_engine(database_url, echo=False)
    Base.metadata.create_all(engine)
    return engine


def get_session(engine):
    """Crea una sesión de base de datos"""
    Session = sessionmaker(bind=engine)
    return Session()
