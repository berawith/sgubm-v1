"""
MikroTik Operations Wrapper - Envoltorio para operaciones con manejo de offline
Todas las operaciones de MikroTik deben usar estas funciones para garantizar sincronización
"""
import logging
from src.infrastructure.mikrotik.adapter import MikroTikAdapter
from src.application.services.sync_service import SyncService

logger = logging.getLogger(__name__)


def safe_suspend_client(db, client, router, audit_service=None, audit_details=None, commit: bool = True, adapter=None):
    """
    Suspende un cliente con manejo de router offline Y validación de address list
    Permite reutilizar una conexión existente (adapter) para operaciones en lote.
    
    Args:
        db: Database manager
        client: Objeto Client
        router: Objeto Router
        audit_service: Servicio de auditoría (opcional) 
        audit_details: Detalles para auditoría (opcional)
        commit: Si debe realizar commit inmediato (default True)
        adapter: Instancia opcional de MikroTikAdapter conectada
        
    Returns:
        Dict con status, message y details
    """
    sync_service = SyncService(db)
    client_id = client.id
    client_ip = client.ip_address
    client_dict = client.to_dict()
    client_repo = db.get_client_repository()
    
    should_disconnect = False

    try:
        # Usar adaptador proporcionado o crear uno nuevo
        if adapter is None:
            adapter = MikroTikAdapter()
            if not adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
                raise Exception(f"No se pudo conectar al router {router.host_address}")
            should_disconnect = True
        
        # Usar método del adaptador que maneja toda la lógica de suspensión
        adapter.suspend_client_service(client_dict)
        
        message = "Cliente bloqueado en MikroTik y sistema"
        already_blocked = False 
        
        if should_disconnect:
            adapter.disconnect()
        
        # Actualizar estado en BD usando repositorio
        client_repo.update(client_id, {'status': 'suspended'}, commit=commit)
        
        # Auditar
        if audit_service and audit_details:
            audit_service.log_action(
                action_type='client_suspended',
                entity_type='client',
                entity_id=client_id,
                details=f"{audit_details}",
                commit=commit
            )
        
        return {
            'status': 'success', 
            'message': message,
            'synced': True,
            'already_blocked': already_blocked
        }
        
    except Exception as e:
        logger.warning(f"⚠️ No se pudo suspender en MikroTik: {e}")
        
        # Encolar operación pendiente
        sync_service.queue_operation(
            operation_type='suspend',
            client_id=client_id,
            router_id=router.id,
            ip_address=client_ip,
            target_status='suspended',
            commit=commit
        )
        
        # Actualizar solo en BD usando repositorio
        client_repo.update(client_id, {'status': 'suspended'}, commit=commit)
        
        # Auditar
        if audit_service and audit_details:
            audit_service.log_action(
                action_type='client_suspended_queued',
                entity_type='client',
                entity_id=client_id,
                details=f"{audit_details} (encolado para sincronización)",
                commit=commit
            )
        
        logger.info(f"📋 Cliente {client_id} suspendido en sistema, encolado para MikroTik")
        return {
            'status': 'queued', 
            'message': 'Cliente suspendido en sistema (pendiente sincronización MikroTik)', 
            'synced': False
        }


def safe_activate_client(db, client, router, audit_service=None, audit_details=None, commit: bool = True, adapter=None):
    """
    Activa un cliente con manejo de router offline Y validación de address list
    Permite reutilizar una conexión existente (adapter) para operaciones en lote.
    
    Args:
        db: Database manager
        client: Objeto Client
        router: Objeto Router
        audit_service: Servicio de auditoría (opcional)
        audit_details: Detalles para auditoría (opcional)
        commit: Si debe realizar commit inmediato (default True)
        adapter: Instancia opcional de MikroTikAdapter conectada
        
    Returns:
        Dict con status, message y details
    """
    sync_service = SyncService(db)
    client_id = client.id
    client_ip = client.ip_address
    client_dict = client.to_dict()
    client_repo = db.get_client_repository()
    
    should_disconnect = False

    try:
        # Usar adaptador proporcionado o crear uno nuevo
        if adapter is None:
            adapter = MikroTikAdapter()
            if not adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
                raise Exception(f"No se pudo conectar al router {router.host_address}")
            should_disconnect = True
        
        # Verificar y restaurar servicio
        adapter.restore_client_service(client_dict)
        
        message = "Cliente desbloqueado de MikroTik y activado"
        was_blocked = True 
        
        if should_disconnect:
            adapter.disconnect()
        
        # Actualizar estado en BD usando repositorio (seguro)
        client_repo.update(client_id, {'status': 'active'}, commit=commit)
        
        # Auditar
        if audit_service and audit_details:
            audit_service.log_action(
                action_type='client_activated',
                entity_type='client',
                entity_id=client_id,
                details=f"{audit_details} (desbloqueado de MikroTik)",
                commit=commit
            )
        
        return {
            'status': 'success',
            'message': message,
            'synced': True,
            'was_blocked': was_blocked
        }
        
    except Exception as e:
        logger.warning(f"⚠️ No se pudo activar en MikroTik: {e}")
        
        # Encolar operación pendiente
        sync_service.queue_operation(
            operation_type='activate',
            client_id=client_id,
            router_id=router.id,
            ip_address=client_ip,
            target_status='active',
            commit=commit
        )
        
        # Actualizar solo en BD usando repositorio
        client_repo.update(client_id, {'status': 'active'}, commit=commit)
        
        # Auditar
        if audit_service and audit_details:
            audit_service.log_action(
                action_type='client_activated_queued',
                entity_type='client',
                entity_id=client_id,
                details=f"{audit_details} (encolado para sincronización)",
                commit=commit
            )
        
        logger.info(f"📋 Cliente {client_id} activado en sistema, encolado para MikroTik")
        return {
            'status': 'queued',
            'message': 'Cliente activado en sistema (pendiente sincronización MikroTik)',
            'synced': False
        }


def trigger_sync_if_online(db, router):
    """
    Intenta sincronizar operaciones pendientes si el router está online
    
    Args:
        db: Database manager
        router: Objeto Router
    """
    if router.status != 'online':
        logger.info(f"⏸️ Router {router.id} offline, no se puede sincronizar")
        return
    
    sync_service = SyncService(db)
    result = sync_service.sync_router_operations(router.id, router.to_dict())
    
    if result['completed'] > 0:
        logger.info(f"🔄 Sincronizadas {result['completed']} operaciones pendientes para router {router.id}")
    
    return result
