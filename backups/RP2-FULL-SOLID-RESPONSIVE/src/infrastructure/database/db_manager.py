"""
Database Manager
Gestor centralizado de conexión a base de datos
"""
from sqlalchemy.orm import Session, scoped_session, sessionmaker
from src.infrastructure.database.models import init_db
from src.infrastructure.database.repositories import RouterRepository, ClientRepository, PaymentRepository
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
    
    def get_router_repository(self) -> RouterRepository:
        """Retorna repositorio de routers"""
        return RouterRepository(self.session)
    
    def get_client_repository(self) -> ClientRepository:
        """Retorna repositorio de clientes"""
        return ClientRepository(self.session)
    
    def get_payment_repository(self) -> PaymentRepository:
        """Retorna repositorio de pagos"""
        return PaymentRepository(self.session)
    
    def remove_session(self):
        """Remueve la sesión del hilo actual (importante para Flask)"""
        if self._session_factory:
            self._session_factory.remove()


# Singleton instance
_db_manager = None


def get_db() -> DatabaseManager:
    """
    Retorna la instancia singleton del gestor de base de datos
    
    Usage:
        db = get_db()
        router_repo = db.get_router_repository()
        routers = router_repo.get_all()
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager
