from fastapi import APIRouter, Request, Depends, HTTPException, Query
from typing import List, Optional
import logging
from sqlalchemy import desc

from src.infrastructure.database.db_manager import get_db
from src.application.services.billing_service import BillingService
from src.application.services.auth import get_current_user, fastapi_permission_required
from src.infrastructure.database.models import Invoice, Client

router = APIRouter(prefix="/api/billing", tags=["Billing"])
logger = logging.getLogger(__name__)
billing_service = BillingService()

@router.post("/run-cycle")
async def run_billing_cycle(request: Request, user=Depends(fastapi_permission_required('system:admin', 'execute'))):
    """Ejecutar ciclo completo de facturación"""
    data = await request.json()
    try:
        billing_service.process_daily_cycle(**data)
        return {"success": True, "message": "Ciclo iniciado"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/invoices")
async def get_invoices(
    client_id: Optional[int] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    user=Depends(get_current_user)
):
    """Listar facturas con filtros"""
    db = get_db()
    query = db.session.query(Invoice)
    if client_id: query = query.filter(Invoice.client_id == client_id)
    if status: query = query.filter(Invoice.status == status)
    if search:
        query = query.join(Client).filter(Client.legal_name.ilike(f"%{search}%"))
    
    invoices = query.order_by(desc(Invoice.issue_date)).limit(limit).all()
    return [inv.to_dict() for inv in invoices]

@router.get("/invoices/{invoice_id}")
async def get_invoice(invoice_id: int, user=Depends(get_current_user)):
    """Obtener detalle de una factura"""
    db = get_db()
    inv = db.session.query(Invoice).get(invoice_id)
    if not inv: raise HTTPException(status_code=404, detail="Factura no encontrada")
    return inv.to_dict()
