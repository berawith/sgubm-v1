from fastapi import APIRouter, Request, Depends, HTTPException
from typing import List, Optional
from werkzeug.security import generate_password_hash
import logging

from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import User, UserRole, RolePermission, CollectorAssignment
from src.application.services.auth import get_current_user, fastapi_permission_required

router = APIRouter(prefix="/api/users", tags=["Users"])
logger = logging.getLogger(__name__)

@router.get("/collectors")
async def get_collectors(user=Depends(get_current_user)):
    """Obtiene solo los usuarios con rol cobrador"""
    db = get_db()
    collectors = db.session.query(User).filter(User.role == UserRole.COLLECTOR.value).all()
    return [u.to_dict() for u in collectors]

@router.get("")
async def get_users(user=Depends(fastapi_permission_required('system:users', 'view'))):
    """Obtiene todos los usuarios"""
    db = get_db()
    users = db.session.query(User).all()
    return [u.to_dict() for u in users]

@router.post("")
async def create_user(request: Request, user=Depends(fastapi_permission_required('system:users', 'create'))):
    """Crea un nuevo usuario"""
    data = await request.json()
    db = get_db()
    session = db.session
    try:
        # Validations and Creation logic (simplified for initial migration)
        if session.query(User).filter_by(username=data['username']).first():
            raise HTTPException(status_code=400, detail="El nombre de usuario ya existe")
            
        new_user = User(
            username=data['username'],
            password_hash=generate_password_hash(data['password']),
            role=data['role'],
            full_name=data.get('full_name')
        )
        session.add(new_user)
        session.commit()
        return {"success": True, "data": new_user.to_dict()}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/permissions/me")
async def get_my_permissions(user=Depends(get_current_user)):
    """Obtiene la matriz de permisos del rol del usuario actual"""
    db = get_db()
    perms = db.session.query(RolePermission).filter_by(role_name=user.role).all()
    return [p.to_dict() for p in perms]
