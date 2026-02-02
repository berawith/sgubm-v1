"""
Database Manager
Gestor centralizado de conexión a base de datos
"""
from sqlalchemy.orm import Session
from src.infrastructure.database.models import init_db, get_session
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
            self._session = get_session(self._engine)
    
    @property
    def session(self) -> Session:
        """Retorna la sesión actual"""
        if self._session is None:
            self._session = get_session(self._engine)
        return self._session
    
    def get_router_repository(self) -> RouterRepository:
        """Retorna repositorio de routers"""
        return RouterRepository(self.session)
    
    def get_client_repository(self) -> ClientRepository:
        """Retorna repositorio de clientes"""
        return ClientRepository(self.session)
    
    def get_payment_repository(self) -> PaymentRepository:
        """Retorna repositorio de pagos"""
        return PaymentRepository(self.session)
    
    def close(self):
        """Cierra la sesión"""
        if self._session:
            self._session.close()


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
