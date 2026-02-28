from fastapi import APIRouter, Request, Depends, HTTPException, Query
from typing import List, Optional
from sqlalchemy import func
from datetime import datetime, timedelta
import logging

from src.infrastructure.database.db_manager import get_db
from src.application.services.sync_service import SyncService
from src.application.services.mikrotik_operations import trigger_sync_if_online
from src.application.services.auth import fastapi_permission_required
from src.infrastructure.database.models import PendingOperation

router = APIRouter(prefix="/api/sync", tags=["Sync"])
logger = logging.getLogger(__name__)

@router.get("/pending")
async def get_pending_operations(router_id: Optional[int] = None, user=Depends(fastapi_permission_required('routers:monitoring', 'view'))):
    """Obtiene todas las operaciones pendientes"""
    try:
        db = get_db()
        sync_service = SyncService(db)
        operations = sync_service.get_pending_operations(router_id)
        return {
            'success': True,
            'operations': [op.to_dict() for op in operations],
            'total': len(operations)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_sync_stats(user=Depends(fastapi_permission_required('routers:monitoring', 'view'))):
    """Obtiene estadísticas de sincronización"""
    db = get_db()
    session = db.session
    try:
        total_pending = session.query(PendingOperation).filter(PendingOperation.status == 'pending').count()
        total_completed = session.query(PendingOperation).filter(PendingOperation.status == 'completed').count()
        total_failed = session.query(PendingOperation).filter(PendingOperation.status == 'failed').count()
        
        return {
            'success': True,
            'stats': {
                'total_pending': total_pending,
                'total_completed': total_completed,
                'total_failed': total_failed
            }
        }
    finally:
        session.close()

@router.post("/force/{router_id}")
async def force_sync(router_id: int, user=Depends(fastapi_permission_required('routers:monitoring', 'edit'))):
    """Fuerza la sincronización de un router"""
    db = get_db()
    r = db.get_router_repository().get_by_id(router_id)
    if not r: raise HTTPException(status_code=404, detail="Router no encontrado")
    if r.status != 'online': raise HTTPException(status_code=400, detail="Router offline")
    
    result = trigger_sync_if_online(db, r)
    return {"success": True, "result": result}
