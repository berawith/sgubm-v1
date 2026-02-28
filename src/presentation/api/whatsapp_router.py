from fastapi import APIRouter, Request, Depends, HTTPException
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from src.infrastructure.database.db_manager import get_db
from src.application.services.whatsapp_agent_service import WhatsAppAgentService
from src.application.services.auth import get_current_user, fastapi_permission_required

router = APIRouter(prefix="/api/whatsapp", tags=["WhatsApp"])
logger = logging.getLogger(__name__)

# Global state for WhatsApp (Bridge connection)
_whatsapp_status = {"connected": False, "qr": None, "last_update": None, "pairing_code": None}

@router.post("/webhook")
async def webhook(request: Request):
    """Recibe eventos del Bridge de WhatsApp"""
    data = await request.json()
    logger.debug(f"Received WhatsApp webhook: {data}")
    db = get_db()
    agent_service = WhatsAppAgentService(db)
    
    # Logic for processing webhook... (Simplified for initial migration)
    return {"success": True}

@router.get("/status")
async def get_status(user=Depends(fastapi_permission_required('whatsapp:config', 'view'))):
    """Retorna el estado actual de la conexión"""
    return _whatsapp_status

@router.post("/status")
async def update_status(request: Request):
    """Actualiza el estado desde el Bridge"""
    data = await request.json()
    _whatsapp_status.update({
        "connected": data.get("connected", False),
        "qr": data.get("qr"),
        "pairing_code": data.get("pairing_code"),
        "last_update": datetime.now().isoformat()
    })
    return {"success": True}

@router.get("/conversations")
async def get_conversations(user=Depends(fastapi_permission_required('whatsapp:chats', 'view'))):
    """Retorna hilos de conversación"""
    db = get_db()
    repo = db.get_whatsapp_repository()
    db_conversations = repo.get_latest_conversations()
    return [m.to_dict() for m in db_conversations]
