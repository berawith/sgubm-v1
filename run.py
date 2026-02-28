"""
SGUBM-V1 - Application Entry Point
Punto de entrada de la aplicación con inyección de dependencias
"""
from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO
import logging
from src.infrastructure.config.settings import get_config
from src.application.events.event_bus import get_event_bus, SystemEvents
from src.presentation.api.websocket_events import register_socket_events
from src.application.services.automation_manager import AutomationManager

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
    
    # Registrar app para hilos secundarios
    from src.infrastructure.database.db_manager import set_app
    set_app(app)
    
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
    
    # Asegurar usuario admin por defecto
    _ensure_default_admin(app)
    
    # Inicializar SocketIO
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
    register_socket_events(socketio)
    app.socketio = socketio
    
    logger.info(f"Application started in {config.system.environment} mode")
    
    # Manejador de limpieza de DB al terminar el request
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        from src.infrastructure.database.db_manager import get_db
        get_db().remove_session()

    @app.before_request
    def resolve_tenant():
        """Resuelve el tenant dinámicamente desde el subdominio"""
        from flask import request, g
        from src.application.services.tenant_service import TenantService
        
        host = request.host
        tenant = TenantService.resolve_from_host(host)
        if tenant:
            g.tenant_id = tenant.id
            g.tenant_name = tenant.name
            g.brand_color = tenant.brand_color
            g.logo_path = tenant.logo_path

    # Log de depuración para cada petición
    @app.before_request
    def log_request_info():
        from flask import request
        # Loguear solo si no es socket.io para no inundar el log
        if not request.path.startswith('/socket.io'):
            logger.info(f"📥 PETICIÓN: [{request.method}] {request.path} - Headers: {dict(request.headers)}")
    
    from src.presentation.api.health_controller import health_bp
    app.register_blueprint(health_bp)

    # Manejador de errores para SPA: redirigir rutas no-API a index.html
    @app.errorhandler(404)
    def handle_404(e):
        from flask import request, render_template, jsonify
        # REGLA SENIOR: Si no es GET, NUNCA es una página HTML
        if request.method != 'GET' or request.path.startswith('/api/'):
            return jsonify({
                'success': False,
                'error': 'Resource not found',
                'method': request.method,
                'path': request.path
            }), 404
            
        return render_template('index.html')

    # Manejador global de errores 500 para evitar fugas de HTML en la API
    @app.errorhandler(Exception)
    def handle_exception(e):
        from flask import request, jsonify
        import traceback
        
        # ENVIAR AL RECICLADOR (SENTINEL)
        try:
            from src.application.services.reciclador_service import RecicladorService
            RecicladorService.capture(e, category='api', severity='error')
        except:
            pass
            
        # Log the full traceback
        logger.error(f"❌ Unhandled Exception on {request.path}: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Si es un error de API, retornar JSON
        if request.path.startswith('/api/'):
            return jsonify({
                'success': False,
                'error': 'Internal Server Error',
                'message': str(e),
                'traceback': traceback.format_exc() if config.system.debug_mode else None
            }), 500
            
        # Para otras rutas, dejar que Flask maneje el error normalmente o mostrar página de error
        return "Internal Server Error", 500
    
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
    from src.presentation.api.billing_controller import billing_bp
    from src.presentation.api.plans_controller import plans_bp
    from src.presentation.api.sync_controller import sync_bp
    from src.presentation.api.reports_controller import reports_bp
    from src.presentation.api.whatsapp_controller import whatsapp_bp
    from src.presentation.api.auth_controller import auth_bp
    from src.presentation.api.support_controller import support_bp
    from src.presentation.api.reciclador_controller import reciclador_bp
    
    # Registrar blueprints
    from src.presentation.api.auth_controller import auth_bp
    from src.presentation.api.users_controller import users_bp
    from src.presentation.api.collector_finance_controller import collector_finance_bp
    
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(routers_bp)
    app.register_blueprint(clients_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(plans_bp)
    app.register_blueprint(sync_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(whatsapp_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(collector_finance_bp)
    app.register_blueprint(support_bp)
    app.register_blueprint(reciclador_bp)
    
    logger.info('✅ Blueprints registered: auth, users, dashboard, routers, clients, payments, billing, plans, sync, reports, whatsapp, collector_finance, support, reciclador')


def _ensure_default_admin(app: Flask):
    """Crea un usuario administrador por defecto si no existen usuarios"""
    with app.app_context():
        from src.infrastructure.database.db_manager import get_db
        from src.infrastructure.database.models import User, UserRole
        from src.application.services.auth import AuthService
        from werkzeug.security import generate_password_hash
        
        session = get_db().session
        try:
            # Siempre inicializar permisos
            AuthService.init_default_permissions()
            
            # Verificar si ya existe algún usuario
            if session.query(User).count() == 0:
                logger.info("Initializing default administrator...")
                admin = User(
                    username="admin",
                    password_hash=generate_password_hash("admin123", method='scrypt'),
                    role=UserRole.ADMIN.value,
                    full_name="Administrador del Sistema"
                )
                session.add(admin)
                session.commit()
                logger.info("✅ Default admin created: admin / admin123")
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to create default admin: {e}")


import threading
import time
import os
import signal

# Track active socket connections for auto-shutdown
active_connections = 0
last_activity_time = time.time()
shutdown_event = threading.Event()
ever_had_connection = False  # Flag para saber si alguna vez hubo una conexión

def idle_shutdown_checker():
    """Checks periodically if any clients are connected. If not, shuts down the server."""
    global active_connections, last_activity_time, ever_had_connection
    # Give the user 2 minutes to open the browser after first start
    time.sleep(120) 
    
    while not shutdown_event.is_set():
        now = time.time()
        # Solo apagar si:
        # 1. No hay conexiones activas
        # 2. Ha pasado más de 5 minutos sin actividad
        # 3. Al menos una vez hubo una conexión (para evitar apagar antes de que alguien se conecte)
        idle_time = now - last_activity_time
        if active_connections == 0 and idle_time > 300 and ever_had_connection:
            logger.info(f"🔌 No active connections detected for {int(idle_time)}s. Shutting down system automatically...")
            # Trigger clean shutdown
            AutomationManager.get_instance().stop()
            # Kills the process (including threads)
            os.kill(os.getpid(), signal.SIGTERM)
            break
        time.sleep(10)  # Verificar cada 10 segundos en lugar de 5

if __name__ == '__main__':
    app = create_app()
    config = get_config()

    # Iniciar Automatización (Solo una vez, no en hilos de request)
    AutomationManager.get_instance().start()

    # AUTO-APAGADO DESHABILITADO - El servidor permanece activo indefinidamente
    # Si deseas reactivar el auto-apagado, descomenta las siguientes líneas:
    # shutdown_thread = threading.Thread(target=idle_shutdown_checker, daemon=True)
    # shutdown_thread.start()

    @app.socketio.on('connect')
    def handle_connect():
        global active_connections, last_activity_time, ever_had_connection
        active_connections += 1
        last_activity_time = time.time()
        ever_had_connection = True  # Marcar que hubo al menos una conexión
        logger.info(f"🟢 Client connected. Active: {active_connections}")

    @app.socketio.on('disconnect')
    def handle_disconnect():
        global active_connections, last_activity_time
        active_connections = max(0, active_connections - 1)
        last_activity_time = time.time()
        logger.info(f"🔴 Client disconnected. Active: {active_connections}")

    # FORZAR MODO SINGLE-PROCESS PARA ESTABILIDAD DE MONITOREO
    logger.info(f"🚀 Real-Time Server starting at http://0.0.0.0:5000 (Protected Mode)")
    app.socketio.run(app, host='0.0.0.0', port=5000, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)
