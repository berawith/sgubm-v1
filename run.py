"""
SGUBM-V1 - Application Entry Point
Punto de entrada de la aplicación con inyección de dependencias
"""
from flask import Flask
from flask_cors import CORS
import logging
from src.infrastructure.config.settings import get_config
from src.application.events.event_bus import get_event_bus, SystemEvents

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """
    Factory Pattern para crear la aplicación Flask
Los módulos se registran aquí de forma desacoplada
    """
    # Cargar configuración
    config = get_config()
    
    # Crear aplicación
    app = Flask(__name__,
                static_folder='src/presentation/web/static',
                template_folder='src/presentation/web/templates')
    
    app.config['SECRET_KEY'] = config.security.secret_key
    app.config['DEBUG'] = config.system.debug_mode
    
    # Enable CORS
    CORS(app)
    
    # Inicializar Event Bus
    event_bus = get_event_bus()
    
    # Registrar manejadores de eventos globales
    _register_event_handlers(event_bus)
    
    # Registrar blueprints (módulos API)
    _register_blueprints(app)
    
    logger.info(f"Application started in {config.system.environment} mode")
    
    return app


def _register_event_handlers(event_bus):
    """Registra manejadores de eventos del sistema"""
    
    # Manejador cuando se crea un cliente
    def on_client_created(data):
        logger.info(f"Event received: Client created - {data.get('client_id')}")
    
    # Manejador cuando se suspende un cliente
    def on_client_suspended(data):
        logger.warning(f"Event received: Client suspended - {data.get('client_id')}")
        # Aquí se puede disparar notificación SMS/Email automáticamente
    
    event_bus.subscribe(SystemEvents.CLIENT_CREATED, on_client_created)
    event_bus.subscribe(SystemEvents.CLIENT_SUSPENDED, on_client_suspended)


def _register_blueprints(app: Flask):
    """Registra los módulos API (blueprints)"""
    
    from src.presentation.api.dashboard_controller import dashboard_bp
    from src.presentation.api.routers_controller import routers_bp
    from src.presentation.api.clients_controller import clients_bp
    from src.presentation.api.payments_controller import payments_bp
    
    # Registrar blueprints
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(routers_bp)
    app.register_blueprint(clients_bp)
    app.register_blueprint(payments_bp)
    
    logger.info('✅ Blueprints registered: dashboard, routers, clients, payments')


if __name__ == '__main__':
    app = create_app()
    config = get_config()
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=config.system.debug_mode
    )
