from flask import Blueprint, request, jsonify, g
from src.application.services.auth import AuthService, login_required

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@auth_bp.route('/login', methods=['POST'])
def login():
    """Endpoint para iniciar sesión"""
    data = request.json
    
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({
            'success': False,
            'message': 'Se requiere usuario y contraseña'
        }), 400
        
    session_data, error = AuthService.authenticate_user(
        data['username'],
        data['password'],
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string
    )
    
    if error:
        return jsonify({
            'success': False,
            'message': error
        }), 401
    
    return jsonify({
        'success': True,
        'message': 'Autenticación exitosa',
        'data': session_data
    })


@auth_bp.route('/me', methods=['GET'])
@login_required
def verify_session():
    """
    Ruta protegida para validar si un token sigue siendo válido
    y obtener los datos del usuario actual (hidratación del frontend).
    """
    # g.user es inyectado por el decorador @login_required
    return jsonify({
        'success': True,
        'data': g.user.to_dict(),
        'tenant': {
            'id': getattr(g, 'tenant_id', None),
            'name': getattr(g, 'tenant_name', 'SGUBM'),
            'brand_color': getattr(g, 'brand_color', '#4f46e5'),
            'logo_path': getattr(g, 'logo_path', None)
        }
    })


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Destruye una sesión activa"""
    auth_header = request.headers.get('Authorization')
    
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        AuthService.logout(token)
        
    return jsonify({
        'success': True,
        'message': 'Sesión cerrada correctamente'
    })
