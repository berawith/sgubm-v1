"""
Database Manager
Gestor centralizado de conexión a base de datos
"""
from sqlalchemy.orm import Session, scoped_session, sessionmaker
from src.infrastructure.database.models import init_db
from src.infrastructure.database.repository_registry import RouterRepository, ClientRepository, PaymentRepository
from src.infrastructure.config.settings import get_config

class DatabaseManager:
    """Gestor de base de datos con patrón Singleton"""
    
    _instance = None
    _engine = None
    _session = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._engine is None:
            config = get_config()
            database_url = config.database.connection_string
            self._engine = init_db(database_url)
            
            # Crear factory de sesiones y envolverla en scoped_session para hilo/request local
            session_factory = sessionmaker(bind=self._engine)
            self._session_factory = scoped_session(session_factory)
    
    @property
    def session(self) -> Session:
        """Retorna la sesión actual (scopada por hilo)"""
        return self._session_factory()

    @property
    def session_factory(self):
        """Retorna la factory scopada directamente"""
        return self._session_factory
    
    def get_router_repository(self) -> RouterRepository:
        """Retorna repositorio de routers"""
        return RouterRepository(self.session)
    
    def get_client_repository(self) -> ClientRepository:
        """Retorna repositorio de clientes"""
        return ClientRepository(self.session)
    
    def get_payment_repository(self) -> PaymentRepository:
        """Retorna repositorio de pagos"""
        return PaymentRepository(self.session)

    def get_deleted_payment_repository(self) -> 'DeletedPaymentRepository': # type: ignore
        """Retorna repositorio de pagos eliminados"""
        from src.infrastructure.database.repository_registry import DeletedPaymentRepository
        return DeletedPaymentRepository(self.session)

    def get_traffic_repository(self) -> 'TrafficRepository': # type: ignore
        """Retorna repositorio de historial de tráfico"""
        from src.infrastructure.database.repository_registry import TrafficRepository
        return TrafficRepository(self.session)

    def get_invoice_repository(self) -> 'InvoiceRepository': # type: ignore
        """Retorna repositorio de facturas"""
        from src.infrastructure.database.repository_registry import InvoiceRepository
        return InvoiceRepository(self.session)

    def get_whatsapp_repository(self) -> 'WhatsAppRepository': # type: ignore
        """Retorna repositorio de historial de WhatsApp"""
        from src.infrastructure.database.repository_registry import WhatsAppRepository
        return WhatsAppRepository(self.session)

    def get_system_setting_repository(self) -> 'SystemSettingRepository': # type: ignore
        """Retorna repositorio de configuración del sistema"""
        from src.infrastructure.database.repository_registry import SystemSettingRepository
        return SystemSettingRepository(self.session)

    def get_expense_repository(self) -> 'ExpenseRepository': # type: ignore
        """Retorna repositorio de gastos"""
        from src.infrastructure.database.repository_registry import ExpenseRepository
        return ExpenseRepository(self.session)


    def remove_session(self):
        """Remueve la sesión del hilo actual (importante para Flask)"""
        if self._session_factory:
            self._session_factory.remove()


# Centralized app reference to avoid circular imports in background threads
_app = None
_db_manager = None

def set_app(app):
    global _app
    _app = app

def get_app():
    global _app
    return _app

def get_db() -> DatabaseManager:
    """
    Retorna la instancia singleton del gestor de base de datos
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager
