from fastapi import APIRouter, Request, Depends, HTTPException
from datetime import datetime, timedelta
from typing import List, Optional

from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Router, Client, UserRole
from src.application.services.auth import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

@router.get("/stats")
async def get_stats(request: Request, router_id: Optional[int] = None, user=Depends(get_current_user)):
    """Retorna estadísticas generales del sistema"""
    db = get_db()
    router_repo = db.get_router_repository()
    client_repo = db.get_client_repository()
    payment_repo = db.get_payment_repository()
    
    is_restricted_role = user.role not in [UserRole.ADMIN.value, UserRole.ADMIN_FEM.value, UserRole.PARTNER.value]
    
    if is_restricted_role:
        assigned_router_ids = set()
        if hasattr(user, 'assignments') and user.assignments:
            for assignment in user.assignments:
                assigned_router_ids.add(assignment.router_id)
        elif user.assigned_router_id:
            assigned_router_ids.add(user.assigned_router_id)
            
        allowed_router_ids = list(assigned_router_ids)
        if router_id:
            router_ids = [router_id] if router_id in allowed_router_ids else []
        else:
            router_ids = allowed_router_ids
            
        if router_ids:
            routers = db.session.query(Router).filter(Router.id.in_(router_ids)).all()
        else:
            routers = []
    else:
        if router_id:
            routers = [router_repo.get_by_id(router_id)]
            routers = [r for r in routers if r]
        else:
            routers = router_repo.get_all()
        
    router_ids = [r.id for r in routers]
    clients_raw = client_repo.get_all()
    if is_restricted_role:
        clients_raw = [c for c in clients_raw if c.router_id in router_ids]
        
    # Stats calculation...
    total_clients = sum(1 for c in clients_raw if c.status != 'deleted')
    active_clients = sum(1 for c in clients_raw if c.status == 'active')
    suspended_clients = sum(1 for c in clients_raw if c.status == 'suspended')
    online_clients = sum(1 for c in clients_raw if c.status == 'active' and c.is_online)
    total_debt = sum((c.account_balance or 0) for c in clients_raw if (c.account_balance or 0) > 0)
    
    # Revenue
    today = datetime.now()
    month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    revenue = payment_repo.get_total_by_date_range(
        month_start, today, 
        router_ids=router_ids if (is_restricted_role or router_id) else None
    )
    
    return {
        'total_servers': len(routers),
        'total_clients': total_clients,
        'active_clients': active_clients,
        'suspended_clients': suspended_clients,
        'online_clients': online_clients,
        'offline_clients': active_clients - online_clients,
        'monthly_revenue': float(revenue or 0),
        'total_pending_debt': float(total_debt or 0)
    }

@router.get("/activity/recent")
async def get_recent_activity(user=Depends(get_current_user)):
    """Retorna actividad reciente del sistema"""
    db = get_db()
    activities = []
    # Simplified activity logic for migration
    return activities
