from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from datetime import datetime, time
from typing import List, Optional

from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import UserRole, Client, Payment
from src.application.services.auth import get_current_user, fastapi_permission_required
from src.application.services.billing_service import BillingService

router = APIRouter(prefix="/api/payments", tags=["Payments"])

def _has_payment_access(user, client_id=None, router_id=None):
    """Lógica de validación de acceso (Cobrador vs Admin)"""
    if user.role not in [UserRole.ADMIN.value, UserRole.ADMIN_FEM.value, UserRole.PARTNER.value]:
        if user.role == UserRole.COLLECTOR.value:
            db = get_db()
            assigned_router_ids = []
            if user.assigned_router_id:
                assigned_router_ids.append(user.assigned_router_id)
            if hasattr(user, 'assignments') and user.assignments:
                assigned_router_ids.extend([a.router_id for a in user.assignments])
            
            if router_id:
                return router_id in assigned_router_ids
            if client_id:
                client = db.session.query(Client).get(client_id)
                if not client: return False
                return client.assigned_collector_id == user.id or client.router_id in assigned_router_ids
            return False
    return True

@router.get("")
async def get_payments(
    request: Request,
    client_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    method: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    user=Depends(get_current_user)
):
    """Obtiene listado de pagos con filtros"""
    db = get_db()
    payment_repo = db.get_payment_repository()
    
    start_dt = None
    end_dt = None
    
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        except ValueError: pass
            
    if end_date:
        try:
            if 'T' in end_date:
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            else:
                base_dt = datetime.fromisoformat(end_date)
                end_dt = datetime.combine(base_dt.date(), time(23, 59, 59, 999999))
        except ValueError: pass

    payments = payment_repo.get_filtered(
        client_id=client_id,
        start_date=start_dt,
        end_date=end_dt,
        method=method,
        search=search,
        limit=limit
    )
    
    is_restricted_role = user.role not in [UserRole.ADMIN.value, UserRole.ADMIN_FEM.value, UserRole.PARTNER.value]
    
    if is_restricted_role:
        assigned_router_ids = [user.assigned_router_id] if user.assigned_router_id else []
        if hasattr(user, 'assignments') and user.assignments:
            assigned_router_ids.extend([a.router_id for a in user.assignments])
            
        payments = [
            p for p in payments 
            if p.client and (p.client.assigned_collector_id == user.id or p.client.router_id in assigned_router_ids)
        ]
            
    return [p.to_dict() for p in payments]

@router.post("")
async def create_payment(request: Request, user=Depends(get_current_user)):
    """Registra un nuevo pago"""
    data = await request.json()
    client_id = data.get('client_id')
    amount = float(data.get('amount', 0))
    
    if not client_id or (amount <= 0 and not data.get('parts')):
        raise HTTPException(status_code=400, detail="Monto o componentes de pago requeridos")
        
    if not _has_payment_access(user, client_id=client_id):
        raise HTTPException(status_code=403, detail="No tienes permisos para este cliente")
        
    db = get_db()
    try:
        # Validación de duplicidad (pendientes)
        payment_repo = db.get_payment_repository()
        if payment_repo.get_filtered(client_id=client_id, status='pending'):
            raise HTTPException(status_code=409, detail="El cliente ya tiene un pago pendiente de confirmación.")
            
        service = BillingService()
        
        if user.role == UserRole.COLLECTOR.value:
            data['collector_id'] = user.id
            new_payment = service.register_payment(client_id, amount, data, status='pending')
            db.session.commit()
            return {"success": True, "is_report": True, "message": "Pago reportado exitosamente."}
            
        # Flujo Admin/Secretaria
        new_payment = service.register_payment(client_id, amount, data)
        db.session.commit()
        
        # Eventos Real-Time
        from src.application.events.event_bus import get_event_bus, SystemEvents
        event_bus = get_event_bus()
        event_bus.publish(SystemEvents.PAYMENT_RECEIVED, {'client_id': client_id, 'amount': amount, 'tenant_id': request.state.tenant_id if hasattr(request.state, 'tenant_id') else None})
        
        return {
            "success": True, 
            "message": "Pago registrado exitosamente",
            "payment_id": new_payment.id,
            "new_balance": new_payment.client.account_balance if new_payment.client else 0
        }
    except ValueError as ve:
        db.session.rollback()
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        db.session.rollback()
        raise HTTPException(status_code=500, detail="Error interno al procesar el pago")

@router.post("/reported/{report_id}/approve")
async def approve_reported_payment(report_id: int, user=Depends(fastapi_permission_required('finance:payments', 'edit'))):
    """Aprueba un pago reportado por un cobrador"""
    try:
        service = BillingService()
        payment = service.confirm_payment(report_id)
        get_db().session.commit()
        return {"success": True, "message": "Pago confirmado correctamente", "payment_id": payment.id}
    except Exception as e:
        get_db().session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
