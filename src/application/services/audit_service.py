import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import AuditLog

logger = logging.getLogger(__name__)

class AuditService:
    @staticmethod
    def log(
        operation: str,
        category: str = 'system',
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        description: str = "",
        previous_state: Any = None,
        new_state: Any = None,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        ip_address: Optional[str] = None
    ):
        """
        Registra un evento en el sistema de Kardex (AuditLog).
        """
        try:
            db = get_db()
            session = db.session
            
            # Serializar estados si son diccionarios
            prev_json = json.dumps(previous_state) if isinstance(previous_state, dict) else str(previous_state) if previous_state else None
            new_json = json.dumps(new_state) if isinstance(new_state, dict) else str(new_state) if new_state else None
            
            log_entry = AuditLog(
                category=category,
                operation=operation,
                entity_type=entity_type,
                entity_id=entity_id,
                description=description,
                previous_state=prev_json,
                new_state=new_json,
                user_id=user_id,
                username=username,
                ip_address=ip_address,
                timestamp=datetime.utcnow()
            )
            
            session.add(log_entry)
            session.commit()
            logger.info(f"📝 Audit: {operation} on {entity_type}:{entity_id} - {description}")
            return True
        except Exception as e:
            logger.error(f"❌ Error al registrar log de auditoría: {e}")
            return False

    @staticmethod
    def log_accounting(operation: str, amount: float, client_id: int, description: str, **kwargs):
        """Helper para eventos contables"""
        # Permitir que kwargs sobrescriba el entity_id y entity_type por defecto (paciente/cliente)
        log_data = {
            'category': 'accounting',
            'operation': operation,
            'entity_type': 'client',
            'entity_id': client_id,
            'description': f"{description} (Monto: {amount})"
        }
        log_data.update(kwargs)
        
        return AuditService.log(**log_data)
