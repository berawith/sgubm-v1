from flask import Blueprint, request, jsonify, g
from src.application.services.auth import login_required, admin_required, permission_required
from src.infrastructure.database.models import User, RolePermission, CollectorAssignment, get_session
from src.infrastructure.database.models import init_db
import os
from werkzeug.security import generate_password_hash

users_bp = Blueprint('users', __name__, url_prefix='/api/users')

from src.infrastructure.database.db_manager import get_db

@users_bp.route('/collectors', methods=['GET'])
@login_required
def get_collectors():
    """
    Obtiene solo los usuarios con rol cobrador.
    Accesible para Roles Operativos (Secretaria, Técnico, etc) sin permisos de Admin.
    """
    db = get_db()
    session = db.session
    try:
        from src.infrastructure.database.models import UserRole
        collectors = session.query(User).filter(User.role == UserRole.COLLECTOR.value).all()
        return jsonify([user.to_dict() for user in collectors])
    finally:
        # No cerramos manualmente si usamos scoped_session manejado por la app
        pass

@users_bp.route('', methods=['GET'])
@permission_required('system:users', 'view')
def get_users():
    """Obtiene todos los usuarios (Solo Admin)"""
    db = get_db()
    session = db.session
    try:
        users = session.query(User).all()
        return jsonify([user.to_dict() for user in users])
    finally:
        pass

@users_bp.route('', methods=['POST'])
@permission_required('system:users', 'create')
def create_user():
    """Crea un nuevo usuario (Solo Admin)"""
    data = request.json
    if not data or not data.get('username') or not data.get('password') or not data.get('role'):
        return jsonify({'success': False, 'message': 'Faltan campos obligatorios'}), 400
    
    db = get_db()
    session = db.session
    try:
        # Verificar duplicados
        exist = session.query(User).filter_by(username=data['username']).first()
        if exist:
            return jsonify({'success': False, 'message': 'El nombre de usuario ya existe'}), 400
        
        new_user = User(
            username=data['username'],
            password_hash=generate_password_hash(data['password']),
            role=data['role'],
            assigned_router_id=data.get('assigned_router_id'),
            full_name=data.get('full_name'),
            identity_document=data.get('identity_document'),
            phone_number=data.get('phone_number'),
            email=data.get('email'),
            address=data.get('address'),
            profit_percentage=float(data.get('profit_percentage') or 0.0),
            bonus_amount=float(data.get('bonus_amount') or 0.0),
            assigned_zone=data.get('assigned_zone')
        )
        session.add(new_user)
        
        # Procesar asignaciones de router si se proporcionan
        assignments_data = data.get('assignments', [])
        for a_data in assignments_data:
            assignment = CollectorAssignment(
                router_id=a_data.get('router_id'),
                profit_percentage=float(a_data.get('profit_percentage') or 0.0),
                bonus_amount=float(a_data.get('bonus_amount') or 0.0),
                assigned_zone=a_data.get('assigned_zone')
            )
            new_user.assignments.append(assignment)
            
        session.commit()
        return jsonify({'success': True, 'data': new_user.to_dict()}), 201
    except Exception as e:
        session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        session.close()

@users_bp.route('/<int:user_id>', methods=['PUT'])
@permission_required('system:users', 'edit')
def update_user(user_id):
    """Actualiza un usuario existente (Solo Admin)"""
    data = request.json
    db = get_db()
    session = db.session
    try:
        user = session.query(User).get(user_id)
        if not user:
            return jsonify({'success': False, 'message': 'Usuario no encontrado'}), 404
        
        if 'username' in data: user.username = data['username']
        if 'role' in data: user.role = data['role']
        if 'assigned_router_id' in data: user.assigned_router_id = data['assigned_router_id']
        if 'full_name' in data: user.full_name = data['full_name']
        if 'identity_document' in data: user.identity_document = data['identity_document']
        if 'phone_number' in data: user.phone_number = data['phone_number']
        if 'email' in data: user.email = data['email']
        if 'address' in data: user.address = data['address']
        if 'profit_percentage' in data: user.profit_percentage = float(data.get('profit_percentage') or 0.0)
        if 'bonus_amount' in data: user.bonus_amount = float(data.get('bonus_amount') or 0.0)
        if 'assigned_zone' in data: user.assigned_zone = data['assigned_zone']
        if 'password' in data and data['password']:
            user.password_hash = generate_password_hash(data['password'])
            
        # Sincronizar asignaciones de router
        if 'assignments' in data:
            # Si se están pasando nuevas asignaciones de MultiRouter (como un cobrador),
            # limpiamos explícitamente el legacy assigned_router_id para evitar conflictos de datos heredados.
            if user.role == 'collector' and len(data['assignments']) > 0:
                user.assigned_router_id = None
                
            # Al usar cascade="all, delete-orphan", limpiar la lista borrará los registros antiguos
            user.assignments = []
            for a_data in data['assignments']:
                assignment = CollectorAssignment(
                    router_id=a_data.get('router_id'),
                    profit_percentage=float(a_data.get('profit_percentage') or 0.0),
                    bonus_amount=float(a_data.get('bonus_amount') or 0.0),
                    assigned_zone=a_data.get('assigned_zone')
                )
                user.assignments.append(assignment)
                
        session.commit()
        return jsonify({'success': True, 'data': user.to_dict()})
    except Exception as e:
        session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        pass

@users_bp.route('/<int:user_id>', methods=['DELETE'])
@permission_required('system:users', 'delete')
def delete_user(user_id):
    """Elimina un usuario (Solo Admin)"""
    db = get_db()
    session = db.session
    try:
        user = session.query(User).get(user_id)
        if not user:
            return jsonify({'success': False, 'message': 'Usuario no encontrado'}), 404
        
        # Impedir borrar al admin principal si es el unico
        if user.username == 'admin':
            return jsonify({'success': False, 'message': 'No se puede eliminar el usuario administrador principal'}), 403
            
        session.delete(user)
        session.commit()
        return jsonify({'success': True, 'message': 'Usuario eliminado'})
    except Exception as e:
        session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        pass

@users_bp.route('/permissions/me', methods=['GET'])
@login_required
def get_my_permissions():
    """Obtiene la matriz de permisos del rol del usuario actual (sin requerir admin)"""
    user = g.user
    db = get_db()
    session = db.session
    try:
        perms = session.query(RolePermission).filter_by(role_name=user.role).all()
        return jsonify([p.to_dict() for p in perms])
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        pass


@users_bp.route('/permissions/<role_name>', methods=['GET'])
@permission_required('system:rbac', 'view')
def get_role_permissions(role_name):
    """Obtiene la matriz de permisos de un rol especifico"""
    db = get_db()
    session = db.session
    try:
        perms = session.query(RolePermission).filter_by(role_name=role_name).all()
        return jsonify([p.to_dict() for p in perms])
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        pass

@users_bp.route('/permissions/<role_name>', methods=['POST'])
@permission_required('system:rbac', 'edit')
def update_role_permissions(role_name):
    """Actualiza la matriz de permisos de un rol especifico"""
    if role_name == 'admin':
        return jsonify({'success': False, 'message': 'Por seguridad, los permisos del administrador principal no pueden ser modificados.'}), 403
        
    data = request.json
    if not data or 'permissions' not in data:
        return jsonify({'success': False, 'message': 'Datos de permisos invalidos'}), 400
        
    db = get_db()
    session = db.session
    try:
        for perm_update in data['permissions']:
            perm_id = perm_update.get('id')
            if not perm_id:
                continue
                
            db_perm = session.query(RolePermission).get(perm_id)
            if db_perm and db_perm.role_name == role_name:
                db_perm.can_view = perm_update.get('can_view', False)
                db_perm.can_create = perm_update.get('can_create', False)
                db_perm.can_edit = perm_update.get('can_edit', False)
                db_perm.can_delete = perm_update.get('can_delete', False)
                db_perm.can_print = perm_update.get('can_print', False)
                db_perm.can_revert = perm_update.get('can_revert', False)
                
        session.commit()
        return jsonify({'success': True, 'message': 'Permisos actualizados correctamente'})
    except Exception as e:
        session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        session.close()
