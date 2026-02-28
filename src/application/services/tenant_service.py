
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Tenant
import json

class TenantService:
    """Servicio para gestión de Inquilinos (Tenants)"""

    @staticmethod
    def get_by_subdomain(subdomain: str) -> Tenant:
        """Obtiene un tenant por su subdominio"""
        session = get_db().session
        return session.query(Tenant).filter(Tenant.subdomain == subdomain, Tenant.is_active == True).first()

    @staticmethod
    def get_by_id(tenant_id: int) -> Tenant:
        """Obtiene un tenant por su ID"""
        session = get_db().session
        return session.query(Tenant).get(tenant_id)

    @staticmethod
    def resolve_from_host(host: str) -> Tenant:
        """
        Resuelve el tenant basado en el hostname (subdominio).
        Ej: 'cliente1.sgubm.com' -> cliente1
        """
        if not host or '.' not in host:
            return None
            
        parts = host.split('.')
        # Asumiendo estructura: subdominio.dominio.tld o subdominio.localhost:port
        if len(parts) >= 2:
            subdomain = parts[0]
            if subdomain in ['www', 'app', 'api']:
                return None
            return TenantService.get_by_subdomain(subdomain)
        return None

    @staticmethod
    def get_settings(tenant_id: int) -> dict:
        """Retorna las configuraciones personalizadas del tenant"""
        tenant = TenantService.get_by_id(tenant_id)
        if not tenant or not tenant.settings:
            return {}
        try:
            return json.loads(tenant.settings)
        except:
            return {}

    @staticmethod
    def update_settings(tenant_id: int, settings: dict):
        """Actualiza las configuraciones del tenant"""
        session = get_db().session
        tenant = session.query(Tenant).get(tenant_id)
        if tenant:
            current_settings = TenantService.get_settings(tenant_id)
            current_settings.update(settings)
            tenant.settings = json.dumps(current_settings)
            session.commit()
            return True
        return False
