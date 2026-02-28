import uuid
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, g
from werkzeug.security import generate_password_hash, check_password_hash

from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import User, UserSession, UserRole, RolePermission

class AuthService:
    """Servicio para Manejo de Usuarios, Autenticación y Sesiones"""
    
    SESSION_DURATION_DAYS = 7 # Duración por defecto de una sesión

    @staticmethod
    def init_default_permissions():
        """Inicializa la matriz de permisos por defecto si está vacía"""
        session = get_db().session
        try:
            if session.query(RolePermission).count() == 0:
                modules = [
                    'dashboard',
                    'clients:list', 'clients:import', 'clients:trash',
                    'finance:payments', 'finance:invoices', 'finance:promises', 
                    'finance:reports', 'finance:expenses',
                    'routers:list', 'routers:monitoring',
                    'whatsapp:chats', 'whatsapp:config',
                    'system:users', 'system:rbac', 'system:reciclador',
                    'clients:support', 'clients:actions',
                    'collector-finance'
                ]
                
                for mod in modules:
                    # Admins (Masculino y Femenino): Full Access
                    session.add(RolePermission(
                        role_name=UserRole.ADMIN.value,
                        module=mod,
                        can_view=True, can_create=True, can_edit=True, can_delete=True,
                        can_print=True, can_revert=True
                    ))
                    session.add(RolePermission(
                        role_name=UserRole.ADMIN_FEM.value,
                        module=mod,
                        can_view=True, can_create=True, can_edit=True, can_delete=True,
                        can_print=True, can_revert=True
                    ))
                    
                    # Socio: Permisos de solo lectura en todo (Consultor Ejecutivo)
                    session.add(RolePermission(
                        role_name=UserRole.PARTNER.value,
                        module=mod,
                        can_view=True, can_create=False, can_edit=False, can_delete=False
                    ))
                    
                    # Técnico: Acceso a Clientes, Routers, Dashboard, Whatsapp
                    is_tech_mod = mod in ['clients', 'routers', 'dashboard', 'whatsapp']
                    session.add(RolePermission(
                        role_name=UserRole.TECHNICAL.value,
                        module=mod,
                        can_view=is_tech_mod, 
                        can_create=is_tech_mod, 
                        can_edit=is_tech_mod, 
                        can_delete=False
                    ))
                    
                    # Secretaria: Acceso a Clientes, Finanzas, Dashboard, Whatsapp
                    is_sec_mod = mod in ['clients', 'finance', 'dashboard', 'whatsapp']
                    session.add(RolePermission(
                        role_name=UserRole.SECRETARY.value,
                        module=mod,
                        can_view=is_sec_mod,
                        can_create=is_sec_mod,
                        can_edit=False,
                        can_delete=False
                    ))
                    
                    # Collector: Acceso muy restringido a Clientes y Dashboard (Finanzas en modo solo lectura)
                    is_collector_module = mod in ['clients', 'finance', 'dashboard']
                    session.add(RolePermission(
                        role_name=UserRole.COLLECTOR.value,
                        module=mod,
                        can_view=is_collector_module, 
                        can_create=(mod == 'clients'),
                        can_edit=False, 
                        can_delete=False
                    ))
                
                session.commit()
                print("🔒 Matriz de Permisos (RBAC) inicializada con éxito.")
        except Exception as e:
            session.rollback()
            print(f"⚠️ Error inicializando matriz de permisos: {str(e)}")

    @staticmethod
    def check_permission(role_name, module, action):
        """Verifica si un rol tiene permiso para una acción en un módulo específico"""
        import logging
        logger = logging.getLogger(__name__)
        
        if not role_name:
            return False
            
        r_name = str(role_name).lower().strip()
        
        # "SuperAdmin" bypass - siempre tienen acceso total
        # Soportamos múltiples alias para roles administrativos
        admin_roles = ['admin', 'administradora', 'administrador', UserRole.ADMIN.value, UserRole.ADMIN_FEM.value]
        if r_name in admin_roles:
            return True
            
        logger.info(f"Checking permission: Role={r_name}, Module={module}, Action={action}")
        
        session = get_db().session
        try:
            perm = session.query(RolePermission).filter(
                RolePermission.role_name == r_name,
                RolePermission.module == module
            ).first()
            
            if not perm:
                return False
                
            action_map = {
                'view': perm.can_view,
                'create': perm.can_create,
                'edit': perm.can_edit,
                'delete': perm.can_delete,
                'print': getattr(perm, 'can_print', False),
                'revert': getattr(perm, 'can_revert', False)
            }
            
            return action_map.get(action, False)
        except Exception as e:
            logger.error(f"Error checking permissions: {e}")
            return False

    @staticmethod
    def create_user(username, password, role="collector", full_name=None, assigned_router_id=None):
        """Crea un usuario en el sistema con contraseña hasheada"""
        session = get_db().session
        try:
            # Check if user exists
            if session.query(User).filter(User.username == username).first():
                return None, "El nombre de usuario ya existe"
                
            hashed_pw = generate_password_hash(password, method='scrypt')
            
            new_user = User(
                username=username,
                password_hash=hashed_pw,
                role=role,
                full_name=full_name,
                assigned_router_id=assigned_router_id
            )
            
            session.add(new_user)
            session.commit()
            return new_user.to_dict(), None
        except Exception as e:
            session.rollback()
            return None, str(e)

    @staticmethod
    def authenticate_user(username, password, ip_address=None, user_agent=None):
        """Verifica credenciales y crea una sesión si son válidas"""
        session = get_db().session
        
        user = session.query(User).filter(User.username == username, User.is_active == True).first()
        
        if not user or not check_password_hash(user.password_hash, password):
            return None, "Credenciales inválidas o usuario inactivo"
            
        # Update last login
        user.last_login = datetime.now()
        
        # Generar token de sesión seguro
        token = str(uuid.uuid4())
        expires = datetime.now() + timedelta(days=AuthService.SESSION_DURATION_DAYS)
        
        user_session = UserSession(
            user_id=user.id,
            token=token,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=expires
        )
        
        session.add(user_session)
        session.commit()
        
        return {
            "token": token,
            "tenant_id": user.tenant_id,
            "user": user.to_dict()
        }, None

    @staticmethod
    def validate_session(token):
        """Valida si un token existe y no ha expirado"""
        if not token:
            return None
            
        session = get_db().session
        user_session = session.query(UserSession).filter(UserSession.token == token).first()
        
        if not user_session:
            return None
            
        if user_session.expires_at < datetime.now():
            # Session expired, delete it
            session.delete(user_session)
            session.commit()
            return None
            
        return user_session.user

    @staticmethod
    def logout(token):
        """Destruye una sesión activa"""
        if not token:
            return True
            
        session = get_db().session
        user_session = session.query(UserSession).filter(UserSession.token == token).first()
        
        if user_session:
            session.delete(user_session)
            session.commit()
            
        return True
        
    @staticmethod
    def get_all_users():
        session = get_db().session
        return [u.to_dict() for u in session.query(User).all()]

# Decorators para Flask
def login_required(f):
    """
    Decorador para proteger rutas API elementales.
    Solo valida que el token exista y no haya expirado.
    Soporta token via: Header Authorization, Query Param (?token=), Cookie (auth_token)
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        
        # 1. Intentar header Authorization (primario - AJAX)
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        
        # 2. Fallback: Query parameter (para URLs abiertas en nuevas pestañas, ej: /print?token=xxx)
        if not token:
            token = request.args.get('token')
        
        # 3. Fallback: Cookie (para sesión persistente)
        if not token:
            token = request.cookies.get('auth_token')
        
        if not token:
            return jsonify({'success': False, 'message': 'No se proporcionó token de autenticación'}), 401
            
        user = AuthService.validate_session(token)
        
        if not user:
            return jsonify({'success': False, 'message': 'Sesión inválida o expirada'}), 401
            
        if not user.is_active:
            return jsonify({'success': False, 'message': 'El usuario ha sido desactivado'}), 403
            
        g.user = user
        g.tenant_id = user.tenant_id
        return f(*args, **kwargs)
        
    return decorated_function

def permission_required(module, action='view'):
    """
    Decorador avanzado de RBAC Granular.
    Verifica que el usuario actual tenga `action` en `module`.
    Si el rol es 'admin', el método `check_permission` lo aprueba automáticamente.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 1. Validar Bearer Token clásico
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                return jsonify({'success': False, 'error': 'No auth token'}), 401
                
            token = auth_header.split(' ')[1]
            user = AuthService.validate_session(token)
            
            if not user:
                return jsonify({'success': False, 'error': 'Session expired'}), 401
                
            if not user.is_active:
                return jsonify({'success': False, 'error': 'User deactivated'}), 403
            
            # 2. Validar Privilegios Granulares contra Base de Datos
            has_permission = AuthService.check_permission(user.role, module, action)
            
            if not has_permission:
                return jsonify({
                    'success': False, 
                    'error': f'Permiso Denegado. Se requiere privilegio [{action}] en el módulo [{module}].'
                }), 403
                
            g.user = user
            g.tenant_id = user.tenant_id
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Se mantiene para retrocompatibilidad pero ahora usa la lógica de bypass robusta
def admin_required(f):
    """
    Decorador para proteger rutas que solo el administrador puede ver/ejecutar.
    Usa el sistema granular pero garantiza el bypass de SuperAdmin.
    """
    return permission_required('system:users', 'view')(f)
