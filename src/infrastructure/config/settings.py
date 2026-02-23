"""
Configuración Centralizada del Sistema
Un único punto de verdad para toda la configuración
"""
import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()


@dataclass
class DatabaseConfig:
    """Configuración de base de datos"""
    driver: str = os.getenv("DB_DRIVER", "postgresql")
    host: str = os.getenv("DB_HOST", "localhost")
    port: int = int(os.getenv("DB_PORT", "5432"))
    name: str = os.getenv("DB_NAME", "sgubm_isp")
    user: str = os.getenv("DB_USER", "postgres")
    password: str = os.getenv("DB_PASSWORD", "")
    
    @property
    def connection_string(self) -> str:
        """Genera string de conexión"""
        if self.driver == "sqlite":
            return f"sqlite:///{self.name}.db"
        return f"{self.driver}://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


@dataclass
class SecurityConfig:
    """Configuración de seguridad"""
    secret_key: str = os.getenv("SECRET_KEY", "change-this-in-production")
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    password_min_length: int = 8
    enable_2fa: bool = os.getenv("ENABLE_2FA", "false").lower() == "true"
    encryption_key: Optional[str] = os.getenv("ENCRYPTION_KEY")


@dataclass
class MikroTikConfig:
    """Configuración de integración MikroTik"""
    default_api_port: int = 8728
    connection_timeout: int = int(os.getenv("MT_TIMEOUT", "10"))
    max_retries: int = 3
    sync_interval_minutes: int = int(os.getenv("MT_SYNC_INTERVAL", "5"))
    enable_auto_sync: bool = os.getenv("MT_AUTO_SYNC", "true").lower() == "true"


@dataclass
class BillingConfig:
    """Configuración de facturación"""
    default_currency: str = os.getenv("CURRENCY", "USD")
    default_tax_rate: float = float(os.getenv("TAX_RATE", "0.12"))
    late_fee_days: int = int(os.getenv("LATE_FEE_DAYS", "3"))
    auto_suspend_days: int = int(os.getenv("AUTO_SUSPEND_DAYS", "15"))
    enable_auto_billing: bool = os.getenv("AUTO_BILLING", "true").lower() == "true"
    non_cumulative_debt: bool = os.getenv("NON_CUMULATIVE_DEBT", "true").lower() == "true"
    suspension_freeze_until: Optional[str] = os.getenv("SUSPENSION_FREEZE_UNTIL")


@dataclass
class NotificationConfig:
    """Configuración de notificaciones"""
    smtp_host: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    sms_provider: str = os.getenv("SMS_PROVIDER", "twilio")
    sms_api_key: str = os.getenv("SMS_API_KEY", "")
    whatsapp_enabled: bool = os.getenv("WHATSAPP_ENABLED", "false").lower() == "true"


@dataclass
class SystemConfig:
    """Configuración general del sistema"""
    environment: str = os.getenv("ENVIRONMENT", "development")
    debug_mode: bool = os.getenv("DEBUG", "true").lower() == "true"
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    max_upload_size_mb: int = int(os.getenv("MAX_UPLOAD_MB", "10"))
    session_lifetime_hours: int = int(os.getenv("SESSION_HOURS", "8"))
    timezone: str = os.getenv("TIMEZONE", "America/New_York")
    
    @property
    def is_production(self) -> bool:
        return self.environment == "production"
    
    @property
    def is_development(self) -> bool:
        return self.environment == "development"


class Config:
    """
    Clase principal de configuración
    Acceso centralizado a toda la configuración del sistema
    """
    
    def __init__(self):
        self.database = DatabaseConfig()
        self.security = SecurityConfig()
        self.mikrotik = MikroTikConfig()
        self.billing = BillingConfig()
        self.notification = NotificationConfig()
        self.system = SystemConfig()
    
    def validate(self) -> bool:
        """Valida que la configuración sea correcta"""
        errors = []
        
        # Validar secret key en producción
        if self.system.is_production and self.security.secret_key == "change-this-in-production":
            errors.append("SECRET_KEY must be changed in production")
        
        # Validar configuración de base de datos
        if not self.database.name:
            errors.append("Database name is required")
        
        # Validar encryption key si está habilitado
        if self.security.enable_2fa and not self.security.encryption_key:
            errors.append("ENCRYPTION_KEY is required when 2FA is enabled")
        
        if errors:
            raise ValueError(f"Configuration errors: {', '.join(errors)}")
        
        return True
    
    def to_dict(self) -> dict:
        """Serializa configuración (sin datos sensibles)"""
        return {
            "environment": self.system.environment,
            "debug": self.system.debug_mode,
            "database_driver": self.database.driver,
            "mikrotik_sync_enabled": self.mikrotik.enable_auto_sync,
            "auto_billing_enabled": self.billing.enable_auto_billing
        }


# Instancia singleton de configuración
_config_instance: Optional[Config] = None


def get_config() -> Config:
    """
    Retorna la instancia singleton de configuración
    
    Usage:
        from infrastructure.config.settings import get_config
        
        config = get_config()
        db_string = config.database.connection_string
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
        _config_instance.validate()
    return _config_instance
