from fastapi import APIRouter, Request, Depends, HTTPException
from typing import List, Optional
import logging

from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import InternetPlan, Client, Router, UserRole
from src.application.services.auth import get_current_user, fastapi_permission_required
from src.infrastructure.mikrotik.adapter import MikroTikAdapter
from src.application.services.audit_service import AuditService

router = APIRouter(prefix="/api/plans", tags=["Plans"])
logger = logging.getLogger(__name__)

@router.get("")
async def get_plans(user=Depends(get_current_user)):
    """Obtiene todos los planes de internet"""
    db = get_db()
    plans = db.session.query(InternetPlan).all()
    
    result = []
    for p in plans:
        count = db.session.query(Client).filter(Client.plan_id == p.id).count()
        data = p.to_dict()
        data['clients_count'] = count
        result.append(data)
    return result

@router.post("")
async def create_plan(request: Request, user=Depends(fastapi_permission_required('system:admin', 'create'))):
    """Crea un nuevo plan"""
    data = await request.json()
    db = get_db()
    try:
        new_plan = InternetPlan(
            name=data.get('name'),
            download_speed=data.get('download_speed'),
            upload_speed=data.get('upload_speed'),
            monthly_price=data.get('monthly_price'),
            service_type=data.get('service_type', 'pppoe'),
            router_id=data.get('router_id')
        )
        db.session.add(new_plan)
        db.session.commit()
        return new_plan.to_dict()
    except Exception as e:
        db.session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
