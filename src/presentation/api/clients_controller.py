"""
Clients API Controller - DATOS REALES
Endpoints para gestión completa de clientes con importación MikroTik y filtrado por Segmentos
"""
from flask import Blueprint, jsonify, request, g
from datetime import datetime, timedelta
from typing import List, Dict, Any
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client, Payment, Invoice, Router, PaymentPromise, NetworkSegment, InternetPlan, CollectorAssignment
from src.infrastructure.mikrotik.adapter import MikroTikAdapter
from src.application.services.sync_service import SyncService
from src.application.services.audit_service import AuditService
from src.application.services.auth import login_required, admin_required, UserRole, permission_required
from src.application.services.monitoring_manager import MonitoringManager
import logging
import json
from ipaddress import ip_network, ip_address

logger = logging.getLogger(__name__)

clients_bp = Blueprint('clients', __name__, url_prefix='/api/clients')


def _has_client_access(user, client):
    """
    Verifica si un usuario (especialmente COLLECTOR) tiene permiso para acceder a un cliente específico.
    Considera asignaciones directas, asignaciones por router (CollectorAssignment) y legacy.
    """
    if user.role not in [UserRole.ADMIN.value, UserRole.ADMIN_FEM.value, UserRole.PARTNER.value]:
        if user.role == UserRole.COLLECTOR.value:
            # 1. Asignación directa
            if client.assigned_collector_id == user.id:
                return True
            
            # 2. Asignación por Routers (CollectorAssignment)
            db = get_db()
            assigned_routers = db.session.query(CollectorAssignment.router_id).filter(
                CollectorAssignment.user_id == user.id
            ).all()
            router_ids = [r[0] for r in assigned_routers]
            
            # 3. Retrocompatibilidad: assigned_router_id legacy
            if user.assigned_router_id:
                router_ids.append(user.assigned_router_id)
                
            if client.router_id in router_ids:
                return True
            
            return False
            
        # Para otros roles (tecnico, secretaria), nos basamos en los permisos de módulo
        # ya que suelen tener acceso a todos los clientes del router que gestionan o global.
    return True


@clients_bp.route('', methods=['GET'])
@login_required
def get_clients():
    """Obtiene todos los clientes con filtros combinados - Filtrado RBAC"""
    db = get_db()
    client_repo = db.get_client_repository()
    
    router_id = request.args.get('router_id', type=int)
    plan_id = request.args.get('plan_id', type=int)
    status = request.args.get('status')
    search = request.args.get('search')
    
    user = g.user
    is_restricted_role = user.role not in [UserRole.ADMIN.value, UserRole.ADMIN_FEM.value, UserRole.PARTNER.value]
    
    # Custom filtering for COLLECTOR role
    assigned_collector_id = None
    if is_restricted_role:
        if user.role == UserRole.COLLECTOR.value:
            assigned_collector_id = user.id
            # If collector has a router assigned but we want to allow cross-router assignments, 
            # we handle this in the repository filter or here.
        elif user.assigned_router_id:
            router_id = user.assigned_router_id
        else:
            return jsonify([])
            
    # Use the new combined filtering method (assumed to handle assigned_collector_id if passed)
    # If the repo doesn't support it yet, we'll need to update it too.
    # Let's check the repo later, but for now we'll pass it.
    clients = client_repo.get_filtered(
        router_id=router_id, 
        status=status, 
        search=search, 
        plan_id=plan_id,
        assigned_collector_id=assigned_collector_id
    )
    
    return jsonify([c.to_dict() for c in clients])


@clients_bp.route('/<int:client_id>', methods=['GET'])
@login_required
def get_client(client_id):
    """Obtiene un cliente específico"""
    db = get_db()
    client_repo = db.get_client_repository()
    client = client_repo.get_by_id(client_id)
    if not client:
        return jsonify({'error': 'Cliente no encontrado'}), 404
        
    if not _has_client_access(g.user, client):
        return jsonify({'error': 'No tienes permisos para ver este cliente'}), 403
            
    return jsonify(client.to_dict())


@clients_bp.route('', methods=['POST'])
@admin_required
def create_client():
    """Crea un nuevo cliente"""
    data = request.json
    db = get_db()
    client_repo = db.get_client_repository()
    pvievas_id = 2 # Puerto Vivas
    PRICE_PUERTO_VIVAS = 70000.0
    PRICE_GENERAL = 90000.0

    # Plan Synchronization
    plan_id = data.get('plan_id')
    if plan_id:
        plan = db.session.query(InternetPlan).get(plan_id)
        if plan:
            data['plan_name'] = plan.name
            data['monthly_fee'] = plan.monthly_price
            # Convert kbps to M format if possible for backwards compatibility/display
            def format_speed(kb):
                if not kb: return "0"
                if kb >= 1000: return f"{kb//1000}M"
                return f"{kb}k"
            
            data['download_speed'] = format_speed(plan.download_speed)
            data['upload_speed'] = format_speed(plan.upload_speed)
            data['service_type'] = plan.service_type

    # Defaults Logic
    if 'monthly_fee' not in data or not data.get('monthly_fee'):
        rid_int = 0
        try:
             rid_int = int(data.get('router_id', 0))
        except: pass
        
        if rid_int == pvievas_id:
            data['monthly_fee'] = PRICE_PUERTO_VIVAS
        else:
            data['monthly_fee'] = PRICE_GENERAL

    if 'plan_name' not in data or not data.get('plan_name') or data.get('plan_name') == 'default':
        data['plan_name'] = 'Plan_Basico_15M'
        
    if 'download_speed' not in data or not data.get('download_speed'):
        data['download_speed'] = '15M'
        
    if 'upload_speed' not in data or not data.get('upload_speed'):
        data['upload_speed'] = '15M'

    # Parsear fechas de string a objeto datetime para SQLite
    for date_field in ['due_date', 'last_payment_date', 'promise_date']:
        if date_field in data and data[date_field]:
            try:
                if isinstance(data[date_field], str):
                    # Manejar formato YYYY-MM-DD o ISO
                    val = data[date_field].split('T')[0] # Quedarse solo con la fecha si es ISO
                    data[date_field] = datetime.strptime(val, '%Y-%m-%d')
            except Exception as e:
                logger.warning(f"Error parsing {date_field}: {e}")
                del data[date_field]

    # VALIDACIÓN DE IP ÚNICA POR ROUTER
    ip_addr = data.get('ip_address')
    target_router_id = data.get('router_id')

    if ip_addr and ip_addr != 'N/A' and ip_addr != '' and target_router_id:
        existing = client_repo.get_all()
        # Verificar duplicados en EL MISMO ROUTER, excluyendo 'deleted'
        dupes = [c for c in existing if c.ip_address == ip_addr and c.router_id == int(target_router_id) and c.status != 'deleted']
        if dupes:
            return jsonify({'error': f'La IP {ip_addr} ya está asignada en este router al cliente {dupes[0].legal_name}'}), 400

    try:
        # Handle assigned_collector_id
        if 'assigned_collector_id' in data:
            # Basic validation: must be a collector or at least exist
            pass
            
        client = client_repo.create(data)
        
        try:
            if client.router_id:
                router = db.get_router_repository().get_by_id(client.router_id)
                if router and router.status == 'online':
                    adapter = MikroTikAdapter()
                    if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port, timeout=3):
                        adapter.create_client_service(client.to_dict())
                        adapter.disconnect()
                else:
                    # Encolar en Sentinel usando el servicio centralizado
                    sync_service = SyncService(db)
                    sync_service.queue_operation(
                        operation_type='create',
                        client_id=client.id,
                        router_id=client.router_id,
                        ip_address=client.ip_address,
                        target_status='active',
                        operation_data=json.dumps(client.to_dict())
                    )
                    logger.warning(f"Router offline. Tarea de CREACIÓN encolada para Cliente {client.id}")
        except Exception as e:
            logger.error(f"Error provisioning client on MikroTik (queued): {e}")

        # Auditoría de creación
        from src.application.services.audit_service import AuditService
        AuditService.log(
            operation='client_created',
            category='client',
            entity_type='client',
            entity_id=client.id,
            description=f"Cliente creado: {client.subscriber_code}",
            new_state=client.to_dict()
        )
        
        # REAL-TIME SYNC
        from src.application.events.event_bus import get_event_bus, SystemEvents
        get_event_bus().publish(SystemEvents.CLIENT_CREATED, {
            'event_type': SystemEvents.CLIENT_CREATED,
            'client_id': client.id,
            'tenant_id': g.tenant_id,
            'client_name': client.full_name
        })
        
        return jsonify(client.to_dict()), 201
    except Exception as e:
        logger.error(f"Error creating client: {str(e)}")
        return jsonify({'error': str(e)}), 400


@clients_bp.route('/<int:client_id>', methods=['PUT'])
@admin_required
def update_client(client_id):
    """Actualiza un cliente"""
    data = request.json
    db = get_db()
    router_repo = db.get_router_repository()
    client_repo = db.get_client_repository()
    
    # Obtener datos actuales antes de actualizar para MikroTik sync
    old_client = client_repo.get_by_id(client_id)
    if not old_client:
        return jsonify({'error': 'Cliente no encontrado'}), 404
        
    old_username = old_client.username
    old_ip = old_client.ip_address
    router_id = old_client.router_id
    
    # Plan Synchronization (on update)
    plan_id = data.get('plan_id')
    if plan_id:
        plan = db.session.query(InternetPlan).get(plan_id)
        if plan:
            data['plan_name'] = plan.name
            data['monthly_fee'] = plan.monthly_price
            
            def format_speed(kb):
                if not kb: return "0"
                if kb >= 1000: return f"{kb//1000}M"
                return f"{kb}k"
            
            data['download_speed'] = format_speed(plan.download_speed)
            data['upload_speed'] = format_speed(plan.upload_speed)
            data['service_type'] = plan.service_type

    # Parsear fechas de string a objeto datetime para SQLite
    for date_field in ['due_date', 'last_payment_date', 'promise_date']:
        if date_field in data and data[date_field]:
            try:
                if isinstance(data[date_field], str):
                    # Manejar formato YYYY-MM-DD o ISO
                    val = data[date_field].split('T')[0] # Quedarse solo con la fecha si es ISO
                    data[date_field] = datetime.strptime(val, '%Y-%m-%d')
            except Exception as e:
                logger.warning(f"Error parsing {date_field}: {e}")
                del data[date_field] # Evitar error de tipo en el repo si el formato es inválido

    # VALIDACIÓN DE IP ÚNICA EN UPDATE (POR ROUTER)
    new_ip = data.get('ip_address')
    # Usar el router_id del payload si viene, si no el del cliente actual
    target_router_id = data.get('router_id', old_client.router_id)
    
    if new_ip and new_ip != 'N/A' and new_ip != '':
        # Solo validar si cambió la IP o cambió el Router
        if new_ip != old_ip or target_router_id != old_client.router_id:
            existing = client_repo.get_all()
            dupes = [c for c in existing if c.ip_address == new_ip and c.router_id == int(target_router_id) and c.id != client_id and c.status != 'deleted']
            if dupes:
                 return jsonify({'error': f'La IP {new_ip} ya está en uso en este router por {dupes[0].legal_name}'}), 400

    try:
        # Handle assigned_collector_id update
        
        # Actualizar en Base de Datos
        updated_client = client_repo.update(client_id, data)
        
        # SINCRONIZACIÓN CON MIKROTIK (Sentinel Logic)
        if router_id:
            router = router_repo.get_by_id(router_id)
            if router:
                sync_success = False
                
                # Intentar sincronización directa si está online
                if router.status == 'online':
                    # Fallback robusto: crear sesión dedicada
                    adapter = MikroTikAdapter()
                    try:
                        if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port, timeout=3):
                            sync_data = updated_client.to_dict()
                            sync_success = adapter.update_client_service(old_username, sync_data, old_ip=old_ip)
                            adapter.disconnect()
                    except Exception as e:
                        logger.error(f"Direct sync failed: {e}")

                
                # 2. Si falló o estaba offline, al SENTINEL usando SyncService
                if not sync_success:
                    sync_service = SyncService(db)
                    sync_service.queue_operation(
                        operation_type='update',
                        client_id=client_id,
                        router_id=router.id,
                        ip_address=updated_client.ip_address,
                        target_status=updated_client.status,
                        operation_data=json.dumps({
                            'old_username': old_username, 
                            'old_ip': old_ip, 
                            **updated_client.to_dict()
                        })
                    )
                    logger.warning(f"Router offline/error. Tarea de ACTUALIZACIÓN encolada para Cliente {client_id}")

        logger.info(f"Cliente actualizado: {updated_client.legal_name}")
        
        # Auditoría de actualización
        from src.application.services.audit_service import AuditService
        AuditService.log(
            operation='client_updated',
            category='client',
            entity_type='client',
            entity_id=client_id,
            description=f"Cliente actualizado: {updated_client.subscriber_code}",
            previous_state={'username': old_username, 'ip': old_ip, 'router_id': router_id},
            new_state=data
        )
        
        # REAL-TIME SYNC
        from src.application.events.event_bus import get_event_bus, SystemEvents
        get_event_bus().publish(SystemEvents.CLIENT_UPDATED, {
            'event_type': SystemEvents.CLIENT_UPDATED,
            'client_id': client_id,
            'tenant_id': g.tenant_id,
            'action': 'edited'
        })
        
        return jsonify(updated_client.to_dict())
    except Exception as e:
        logger.error(f"Error updating client {client_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500


@clients_bp.route('/<int:client_id>', methods=['DELETE'])
@admin_required
def delete_client(client_id):
    """Elimina un cliente. Soporta 'scope=local' (Soft Delete) o 'scope=global' (Hard Delete + Mikrotik)"""
    scope = request.args.get('scope', 'global')
    db = get_db()
    client_repo = db.get_client_repository()
    router_repo = db.get_router_repository()
    
    client = client_repo.get_by_id(client_id)
    if not client:
        return jsonify({'error': 'Cliente no encontrado'}), 404

    if scope == 'local':
        # Soft Delete / Archive
        # Marcamos como eliminado (pendiente: decidir si usar tabla aparte o status)
        # Por ahora usamos status='deleted' y un timestamp si existiera, o notas.
        # Dado que el usuario menciona "tabla de clientes eliminados", usar status es un paso intermedio válido.
        # PRECAUCIÓN: Si se 'restaura', hay que validar conflictos de IP/User.
        
        # Para evitar conflictos de unicidad (subscriber_code, etc) si se crea otro, 
        # deberíamos alterar esos campos o asumir que 'deleted' no libera el código.
        # Asumiremos que el código se mantiene reservado para este cliente archivado.
        
        client_repo.update(client_id, {'status': 'deleted'})
        logger.info(f"Cliente {client_id} archivado (Soft Delete).")
        
        # Auditoría de archivado
        AuditService.log(
            operation='client_archived',
            category='client',
            entity_type='client',
            entity_id=client_id,
            description=f"Cliente archivado (Soft Delete): {client.legal_name}",
            previous_state={'status': client.status},
            new_state={'status': 'deleted'}
        )
        
        return jsonify({'message': 'Cliente archivado correctamente'}), 200

    else:
        # Global / Hard Delete (SISTEMA SOLAMENTE - Mantenido por petición de usuario)
        
        # Auditoría de eliminación permanente (ANTES de borrar para tener acceso a los datos)
        AuditService.log(
            operation='client_deleted_permanent',
            category='client',
            entity_type='client',
            entity_id=client_id,
            description=f"Cliente eliminado permanentemente: {client.legal_name} ({client.username})",
            previous_state=client.to_dict()
        )

        # 2. Eliminar de BD
        success = client_repo.delete(client_id)
        if not success:
             return jsonify({'error': 'Error al eliminar de BD'}), 500
        
        logger.info(f"Cliente {client_id} eliminado permanentemente (Global).")
        return jsonify({'message': 'Cliente eliminado correctamente'}), 200


@clients_bp.route('/bulk-restore', methods=['POST'])
@admin_required
def bulk_restore_clients():
    """Restaura múltiples clientes archivados"""
    data = request.json
    ids = data.get('ids', [])
    if not ids:
        return jsonify({'error': 'No se proporcionaron IDs'}), 400
        
    db = get_db()
    client_repo = db.get_client_repository()
    
    restored = 0
    for cid in ids:
        if client_repo.update(cid, {'status': 'active'}):
            restored += 1
            AuditService.log(
                operation='client_restored',
                category='client',
                entity_type='client',
                entity_id=cid,
                description=f"Cliente {cid} restaurado masivamente."
            )
            
    return jsonify({'message': f'{restored} clientes restaurados correctamente', 'count': restored}), 200


@clients_bp.route('/bulk-delete', methods=['POST'])
@admin_required
def bulk_delete_clients():
    """Elimina permanentemente múltiples clientes (SOLO SISTEMA)"""
    data = request.json
    ids = data.get('ids', [])
    if not ids:
        return jsonify({'error': 'No se proporcionaron IDs'}), 400
        
    db = get_db()
    client_repo = db.get_client_repository()
    
    deleted = 0
    for cid in ids:
        # Petición de usuario: SOLO SISTEMA
        if client_repo.delete(cid):
            deleted += 1
            AuditService.log(
                operation='client_deleted_permanent',
                category='client',
                entity_type='client',
                entity_id=cid,
                description=f"Cliente {cid} eliminado permanentemente (Masivo, Solo Sistema)."
            )
            
    return jsonify({'message': f'{deleted} clientes eliminados correctamente', 'count': deleted}), 200


@clients_bp.route('/empty-trash', methods=['POST'])
@admin_required
def empty_trash():
    """Vacía la papelera por completo (SOLO SISTEMA)"""
    db = get_db()
    client_repo = db.get_client_repository()
    
    # Obtener todos los eliminados
    deleted_clients = client_repo.get_filtered(status='deleted')
    count = 0
    for c in deleted_clients:
        if client_repo.delete(c.id):
            count += 1
            
    AuditService.log(
        operation='trash_emptied',
        category='client',
        entity_type='client',
        description=f"Papelera vaciada completamente: {count} clientes eliminados (Solo Sistema)."
    )
            
    return jsonify({'message': f'Papelera vaciada: {count} clientes eliminados', 'count': count}), 200
@clients_bp.route('/<int:client_id>/suspend', methods=['POST'])
@admin_required
def suspend_client(client_id):
    """Suspende un cliente con manejo inteligente de MikroTik"""
    print(f"DEBUG: Entering suspend_client for ID {client_id}")
    try:
        from src.application.services.mikrotik_operations import safe_suspend_client
        
        db = get_db()
        router_repo = db.get_router_repository()
        client_repo = db.get_client_repository()
        
        client = client_repo.get_by_id(client_id)
        if not client:
            return jsonify({'error': 'Cliente no encontrado'}), 404
        
        if not client.router_id:
            return jsonify({'error': 'Cliente sin router asignado'}), 400
        
        router = router_repo.get_by_id(client.router_id)
        if not router:
            return jsonify({'error': 'Router no encontrado'}), 404
        
        # Usar función segura con validación y manejo de offline
        result = safe_suspend_client(
            db=db,
            client=client,
            router=router,
            audit_service=AuditService,
            audit_details=f'Suspensión manual - Cliente: {client.legal_name}'
        )
        
        logger.info(f"📋 suspend_client result: {result}")
        
        # REAL-TIME SYNC
        from src.application.events.event_bus import get_event_bus, SystemEvents
        get_event_bus().publish(SystemEvents.CLIENT_UPDATED, {
            'event_type': SystemEvents.CLIENT_UPDATED,
            'client_id': client_id,
            'tenant_id': g.tenant_id,
            'action': 'suspended'
        })

        return jsonify({
            'success': True,
            'client': client.to_dict(),
            'sync_status': result['status'],
            'message': result['message'],
            'already_blocked': result.get('already_blocked', False)
        })
    except Exception as e:
        logger.error(f"❌ Error crítico en suspend_client (manual): {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Ocurrió un error inesperado al suspender al cliente. Por favor, revise los logs del servidor.'
        }), 500



@clients_bp.route('/<int:client_id>/promise', methods=['POST'])
@permission_required('finance:promises', 'create')
def register_promise(client_id):
    """Registra una promesa de pago y reactiva servicio de forma segura"""
    from src.application.services.mikrotik_operations import safe_activate_client
    data = request.json
    db = get_db()
    client_repo = db.get_client_repository()
    router_repo = db.get_router_repository()
    
    client = client_repo.get_by_id(client_id)
    if not client:
        return jsonify({'error': 'Cliente no encontrado'}), 404
    
    # Validar acceso a nivel de fila
    if not _has_client_access(g.user, client):
        return jsonify({'error': 'No tienes permisos para registrar promesas a este cliente'}), 403
    
    promise_date_str = data.get('promise_date')
    
    if not promise_date_str:
        client.promise_date = None
        client_repo.update(client)
        return jsonify(client.to_dict())
    
    try:
        promise_date = datetime.strptime(promise_date_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        client.promise_date = promise_date
        client_repo.update(client)
        
        # Crear registro en historial
        new_promise = PaymentPromise(
            client_id=client.id,
            promise_date=promise_date,
            status='pending',
            notes=f"Promesa registrada individualmente hasta {promise_date_str}"
        )
        db.session.add(new_promise)
        db.session.commit()
        
        # Reactivación segura si estaba suspendido
        if client.status == 'suspended':
            router = router_repo.get_by_id(client.router_id)
            if router:
                safe_activate_client(
                    db=db,
                    client=client,
                    router=router,
                    audit_service=AuditService,
                    audit_details=f"Reactivación por promesa hasta {promise_date_str}"
                )
        
        return jsonify(client.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@clients_bp.route('/<int:client_id>/activate', methods=['POST'])
@admin_required
def activate_client(client_id):
    """Activa un cliente con manejo inteligente de MikroTik y promesa opcional"""
    from src.application.services.mikrotik_operations import safe_activate_client
    
    data = request.json or {}
    promise_days = data.get('promise_days')
    
    db = get_db()
    router_repo = db.get_router_repository()
    client_repo = db.get_client_repository()
    # audit = AuditService(db)  <-- Removed incorrect instantiation

    
    client = client_repo.get_by_id(client_id)
    if not client:
        return jsonify({'error': 'Cliente no encontrado'}), 404
    
    if not client.router_id:
        return jsonify({'error': 'Cliente sin router asignado'}), 400
    
    router = router_repo.get_by_id(client.router_id)
    if not router:
        return jsonify({'error': 'Router no encontrado'}), 404
    
    # 1. Aplicar promesa si se especifica
    if promise_days:
        promise_date = datetime.now() + timedelta(days=int(promise_days))
        client.promise_date = promise_date
        client_repo.update(client)
        
        # Registrar en historial
        new_promise = PaymentPromise(
            client_id=client.id,
            promise_date=promise_date,
            status='pending',
            notes=f"Activación individual con {promise_days} días de prórroga"
        )
        db.session.add(new_promise)
        db.session.commit()
        
        logger.info(f"🤝 Promesa de pago individual: {client.legal_name} por {promise_days} días")

    # 2. Usar función segura con validación y manejo de offline
    result = safe_activate_client(
        db=db,
        client=client,
        router=router,
        audit_service=AuditService,
        audit_details=f'Activación manual {"con promesa" if promise_days else ""} - Cliente: {client.legal_name}'
    )
    
    # REAL-TIME SYNC
    from src.application.events.event_bus import get_event_bus, SystemEvents
    get_event_bus().publish(SystemEvents.CLIENT_UPDATED, {
        'event_type': SystemEvents.CLIENT_UPDATED,
        'client_id': client_id,
        'tenant_id': g.tenant_id,
        'action': 'activated'
    })

    return jsonify({
        'success': True,
        'client': client.to_dict(),
        'sync_status': result['status'],
        'message': result['message']
    })


@clients_bp.route('/<int:client_id>/restore', methods=['POST'])
@admin_required
def restore_client(client_id):
    """Restaura un cliente archivado (deleted -> active)"""
    db = get_db()
    client_repo = db.get_client_repository()
    
    client = client_repo.get_by_id(client_id)
    if not client:
        return jsonify({'error': 'Cliente no encontrado'}), 404
        
    if client.status != 'deleted':
        return jsonify({'error': 'El cliente no está archivado'}), 400
        
    # Restaurar estado
    client = client_repo.update(client_id, {'status': 'active'})
    
    # Auditoría de restauración
    AuditService.log(
        operation='client_restored',
        category='client',
        entity_type='client',
        entity_id=client_id,
        description=f"Cliente restaurado del archivo: {client.legal_name}",
        previous_state={'status': 'deleted'},
        new_state={'status': 'active'}
    )
    
    logger.info(f"Cliente restaurado del archivo: {client.legal_name}")
    return jsonify(client.to_dict())


@clients_bp.route('/<int:client_id>/payments', methods=['POST'])
@login_required
def register_payment(client_id):
    """Registra un pago para el cliente y restaura servicio si aplica - LOGICA UNIFICADA"""
    data = request.json
    db = get_db()
    
    user = g.user
    
    client_repo = db.get_client_repository()
    client = client_repo.get_by_id(client_id)
    
    if not client:
        return jsonify({'error': 'Cliente no encontrado'}), 404
        
    if not _has_client_access(user, client):
        return jsonify({'error': 'No tienes permisos para registrar pagos a este cliente'}), 403
    
    try:
        from src.application.services.billing_service import BillingService
        service = BillingService()
        
        amount = float(data.get('amount') or 0)
        
        # Usar lógica centralizada (maneja balance, facturas, promesas y reactivación segura)
        service.register_payment(client_id, amount, data)
        
        # COMMIT FINAL: Si llegamos aquí sin errores, guardamos todo atómicamente
        db.session.commit()
        
        # Obtener el cliente actualizado para la respuesta
        client_repo = db.get_client_repository()
        updated_client = client_repo.get_by_id(client_id)
        
        logger.info(f"✅ Pago registrado exitosamente para {updated_client.legal_name} (${amount})")
        return jsonify(updated_client.to_dict()), 201
        
    except ValueError as ve:
        db = get_db()
        db.session.rollback()
        logger.warning(f"⚠️ Error de validación al registrar pago: {ve}")
        return jsonify({'error': str(ve)}), 400
    except Exception as e:
        db = get_db()
        db.session.rollback()
        logger.error(f"❌ Error crítico registrando pago para cliente {client_id}: {e}")
        return jsonify({'error': 'Error interno al procesar el pago'}), 500



@clients_bp.route('/<int:client_id>/adjust-balance', methods=['POST'])
@admin_required
def adjust_balance(client_id):
    """Corregir manualmente el balance del cliente"""
    data = request.json
    db = get_db()
    client_repo = db.get_client_repository()
    
    new_balance = data.get('new_balance')
    reason = data.get('reason', 'Ajuste manual de balance')
    
    if new_balance is None:
        return jsonify({'error': 'Nuevo balance requerido'}), 400
        
    try:
        new_balance = float(new_balance)
        client = client_repo.get_by_id(client_id)
        if not client:
            return jsonify({'error': 'Cliente no encontrado'}), 404
            
        old_balance = client.account_balance or 0.0
        
        # Actualizar balance usando 'set'
        updated_client = client_repo.update_balance(client_id, new_balance, operation='set')
        
        # Auditoría crítica
        AuditService.log(
            operation='balance_manually_adjusted',
            category='accounting_critical',
            entity_type='client',
            entity_id=client_id,
            description=f"Balance ajustado manualmente: ${old_balance} -> ${new_balance}. Motivo: {reason}",
            previous_state={'balance': old_balance},
            new_state={'balance': new_balance, 'reason': reason}
        )
        
        return jsonify(updated_client.to_dict())
    except ValueError:
        return jsonify({'error': 'El balance debe ser un número válido'}), 400
    except Exception as e:
        logger.error(f"Error ajustando balance para cliente {client_id}: {e}")
        return jsonify({'error': str(e)}), 500


@clients_bp.route('/update-name-by-ip', methods=['POST'])
@admin_required
def update_client_name_by_ip():
    """Actualiza el nombre de usuario de un cliente basándose en su IP"""
    data = request.json
    ip_address = data.get('ip_address')
    new_username = data.get('new_username')
    
    if not ip_address or not new_username:
        return jsonify({'error': 'IP y nuevo nombre requeridos'}), 400
    
    db = get_db()
    client_repo = db.get_client_repository()
    
    # Buscar cliente por IP
    clients = client_repo.get_all()
    client = next((c for c in clients if c.ip_address == ip_address), None)
    
    if not client:
        return jsonify({'error': 'No se encontró cliente con esa IP'}), 404
    
    old_username = client.username
    client = client_repo.update(client.id, {'username': new_username})
    
    logger.info(f"Nombre actualizado automaticamente por IP {ip_address}: '{old_username}' -> '{new_username}'")
    
    return jsonify({
        'success': True,
        'client_id': client.id,
        'old_username': old_username,
        'new_username': new_username,
        'ip_address': ip_address
    })


@clients_bp.route('/lookup-identity', methods=['POST'])
@admin_required
def lookup_client_identity():
    """Busca identidad de un cliente (MAC/IP) directamente en el router en tiempo real"""
    data = request.json
    router_id = data.get('router_id')
    ip_address = data.get('ip_address')
    username = data.get('username')
    
    if not router_id:
        return jsonify({'error': 'Router ID requerido'}), 400
        
    db = get_db()
    router = db.get_router_repository().get_by_id(router_id)
    if not router:
        return jsonify({'error': 'Router no encontrado'}), 404
        
    adapter = MikroTikAdapter()
    try:
        if not adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
             return jsonify({'error': 'No se pudo conectar al router'}), 503
             
        found_mac = None
        found_ip = None
        
        # 1. Buscar en DHCP Leases
        leases = adapter.get_dhcp_leases()
        for l in leases:
            if ip_address and l.get('address') == ip_address:
                found_mac = l.get('mac-address')
                break
            if username and (l.get('host-name') == username or l.get('comment') == username):
                found_mac = l.get('mac-address')
                found_ip = l.get('address')
                break
                
        # 2. Buscar en ARP Table si no se encontró MAC
        if not found_mac and ip_address:
            arp = adapter.get_arp_table()
            for a in arp:
                if a.get('address') == ip_address:
                    found_mac = a.get('mac-address')
                    break
                    
        # 3. Buscar en PPPoE (Active Sessions) si falta IP o MAC
        # El Caller ID en PPPoE es la MAC address
        if (not found_ip or not found_mac) and username:
            try:
                active = adapter._api_connection.get_resource('/ppp/active').get(name=username)
                if active:
                    session = active[0]
                    if not found_ip:
                         found_ip = session.get('address')
                    if not found_mac:
                         found_mac = session.get('caller-id')
            except Exception as e:
                logger.warning(f"Error checking PPPoE active for {username}: {e}")
                
        adapter.disconnect()
        
        return jsonify({
            'success': True,
            'ip_address': found_ip or ip_address,
            'mac_address': found_mac
        })
    except Exception as e:
        logger.error(f"Error in lookup-identity: {e}")
        return jsonify({'error': str(e)}), 500


@clients_bp.route('/preview-import/<int:router_id>', methods=['GET'])
@admin_required
def preview_import_clients(router_id):
    """
    Escanea clientes del router (PPPoE + Simple Queues) y filtra por Segmentos de Red declarados.
    Soporta scan_type: 'mixed', 'pppoe', 'dhcp_arp_queues'
    """
    scan_type = request.args.get('scan_type', 'mixed')
    db = get_db()
    router_repo = db.get_router_repository()
    client_repo = db.get_client_repository()
    
    router = router_repo.get_by_id(router_id)
    if not router:
        return jsonify({'error': 'Router no encontrado'}), 404
    
    # 1. Obtener Rangos IP Válidos (Segmentos de Red y legacy ranges)
    allowed_networks = []
    
    # Prioridad 1: Tabla NetworkSegment (Nueva lógica centralizada)
    segments = db.session.query(NetworkSegment).filter(NetworkSegment.router_id == router_id).all()
    for s in segments:
        try:
            allowed_networks.append(ip_network(s.cidr, strict=False))
        except Exception as e:
            logger.warning(f"Segmento inválido en BD: {s.cidr} - {e}")

    # Prioridad 2: Fallback a campos legacy si existen
    if router.pppoe_ranges:
        for r in router.pppoe_ranges.split(','):
            if r.strip():
                try:
                    net = ip_network(r.strip(), strict=False)
                    if net not in allowed_networks: allowed_networks.append(net)
                except: pass
    if router.dhcp_ranges:
        for r in router.dhcp_ranges.split(','):
            if r.strip():
                try:
                    net = ip_network(r.strip(), strict=False)
                    if net not in allowed_networks: allowed_networks.append(net)
                except: pass
        
    has_segments_filter = len(allowed_networks) > 0

    # POLÍTICA ESTRICTA: Si no hay segmentos declarados, BLOQUEAR importación
    if not has_segments_filter:
        logger.warning(f"⚠️ Router {router_id} ({router.alias}): No tiene segmentos de red declarados. Importación BLOQUEADA.")
        return jsonify({
            'router_alias': router.alias, 'router_id': router_id,
            'total_found': 0, 'segments_filter_active': False,
            'clients': [],
            'error_message': f'⚠️ El router {router.alias} no tiene segmentos de red internos declarados. Configura al menos un segmento antes de importar.',
            'summary': {
                'discovered_no_queue': 0, 'pppoe_secrets': 0,
                'simple_queues': 0, 'needs_provisioning': False,
                'name_changes': 0, 'ip_changes': 0
            }
        })

    logger.info(f"Filtrando importación ({scan_type}) de router {router_id} ({router.alias}) por {len(allowed_networks)} segmentos: {[str(n) for n in allowed_networks]}")

    # Get exclusion keywords from router config
    exclusion_raw = router.exclusion_keywords or ""
    dynamic_keywords = [k.strip().upper() for k in exclusion_raw.split(',') if k.strip()]

    def is_ip_allowed(ip_str):
        """Verifica ESTRICTAMENTE si una IP está en los segmentos permitidos"""
        if not ip_str: return False
        
        # Limpiar IP (quitar máscara si viene tipo 192.168.1.5/32)
        clean_ip = ip_str.split('/')[0]
        if clean_ip.startswith('169.254') or clean_ip == '0.0.0.0': return False
            
        try:
            addr = ip_address(clean_ip)
            return any(addr in net for net in allowed_networks)
        except ValueError:
            return False

    def is_management_equipment(name, comment=''):
        """Verifica si un nombre/comentario corresponde a equipos de gestión o palabras clave excluidas"""
        if not name and not comment: return False
        text_to_check = f"{name or ''} {comment or ''}".upper()
        
        # 1. Patrones dinámicos del router
        for pattern in dynamic_keywords:
            if pattern in text_to_check: return True
        
        # 2. Patrones base (Mantenemos solo infraestructura crítica)
        management_patterns = [
            'GESTION', 'GESTION-AP', 'CORE-', 'BACKBONE', 'SWITCH', 'ROUTER-',
            'MIKROTIK', 'INFRAESTRUCTURA', 'ADMIN', 'MANAGEMENT', 'TOWER', 'TORRE', 
            'PTP-', 'ENLACE', 'APB', 'HS-IP-BINDING'
        ]
        for pattern in management_patterns:
            if pattern in text_to_check: return True
        return False

    def get_suggested_plan(ip_str):
        """Sugiere un nombre de plan basado en el segmento de red de la IP"""
        if not ip_str or ip_str == '0.0.0.0': return 'Sin Plan'
        try:
            addr = ip_address(ip_str.split('/')[0])
            for net in allowed_networks:
                if addr in net:
                    # HEURÍSTICA: Intentar mapear basado en el nombre del segmento o tipo
                    # 172.16.41.0/24 -> SQ Plan (MI JARDIN AIRE)
                    # 10.10.10.0/24 -> PLAN_30Mbps (MI JARDIN PPPoE)
                    net_str = str(net)
                    if net_str == '172.16.41.0/24': return 'SQ Plan'
                    if net_str == '10.10.10.0/24': return 'PLAN_30Mbps'
                    
                    # Fallback por nombre de segmento si está disponible
                    # (Como allowed_networks son objetos ip_network, no tenemos el nombre aquí fácilmente
                    # salvo que lo hayamos guardado)
            return 'Sin Plan'
        except:
            return 'Sin Plan'

    adapter = MikroTikAdapter()
    
    try:
        connected = adapter.connect(
            host=router.host_address, username=router.api_username,
            password=router.api_password, port=router.api_port, timeout=10
        )
        
        if not connected:
            return jsonify({'error': 'No se pudo conectar al router. Verifica que esté en línea.'}), 503
            
        existing_clients = client_repo.get_all()
        # Mapeos para búsqueda rápida
        existing_usernames_map = {c.username.lower(): c for c in existing_clients}
        existing_clients_by_ip = {c.ip_address: c for c in existing_clients if c.ip_address}
        existing_ips_set = set(existing_clients_by_ip.keys())
        
        preview_list = []
        seen_ips = set()
        seen_mikrotik_usernames = set() 
        management_ips = set()

        # --- A. SCAN PPPOE SECRETS ---
        if scan_type in ['mixed', 'pppoe']:
            try:
                ppp_secrets = adapter.get_all_pppoe_secrets()
                all_profiles = adapter.get_ppp_profiles()
                all_pools = adapter.get_ip_pools()
                
                pool_map = {p.get('name'): p.get('ranges') for p in all_pools}
                allowed_profiles = set()
                
                for p in all_profiles:
                    p_name = p.get('name')
                    remote = p.get('remote-address')
                    if remote and is_ip_allowed(remote):
                        allowed_profiles.add(p_name)
                    else:
                        pool_range = pool_map.get(remote)
                        if pool_range:
                            first_ip = pool_range.split(',')[0].split('-')[0]
                            if is_ip_allowed(first_ip): allowed_profiles.add(p_name)

                for secret in ppp_secrets:
                    name = secret.get('name', '')
                    remote_addr = secret.get('remote_address', '')
                    profile_name = secret.get('profile', '')
                    comment = secret.get('comment', '')
                    
                    if is_management_equipment(name, comment):
                        if remote_addr: management_ips.add(remote_addr)
                        continue
                    
                    # POLÍTICA ESTRICTA: Si tiene IP, DEBE estar permitida.
                    if remote_addr and remote_addr != '0.0.0.0' and not is_ip_allowed(remote_addr):
                        continue
                    
                    # Si no tiene IP, validamos contra el profile (permitir dinámicos si el pool del profile está en segmento)
                    if not remote_addr or remote_addr == '0.0.0.0':
                        if profile_name not in allowed_profiles:
                            continue

                    if not name: continue
                    
                    # DETECCIÓN DE CAMBIOS (IP y Nombre)
                    existing_client = existing_usernames_map.get(name.lower())
                    existing_by_ip = existing_clients_by_ip.get(remote_addr) if remote_addr and remote_addr != '0.0.0.0' else None
                    
                    is_duplicate = existing_client is not None or existing_by_ip is not None
                    name_changed = False
                    ip_changed = False
                    db_ip = None
                    client_id = None

                    if existing_by_ip:
                         client_id = existing_by_ip.id
                         if existing_by_ip.username.lower() != name.lower():
                              name_changed = True
                    elif existing_client:
                         client_id = existing_client.id
                         if existing_client.ip_address != remote_addr:
                              ip_changed = True
                              db_ip = existing_client.ip_address
                    
                    seen_mikrotik_usernames.add(name.lower())
                    if remote_addr: seen_ips.add(remote_addr)

                    preview_list.append({
                        'type': 'pppoe', 'username': name, 'password': secret.get('password', ''),
                        'ip_address': remote_addr or 'Dinámica', 'profile': profile_name or 'default',
                        'status': 'disabled' if secret.get('disabled') else 'active',
                        'exists_in_db': is_duplicate, 
                        'db_status': existing_client.status if existing_client else (existing_by_ip.status if existing_by_ip else None),
                        'name_changed': name_changed,
                        'ip_changed': ip_changed,
                        'old_username': existing_by_ip.username if name_changed else None,
                        'db_ip': db_ip,
                        'client_id': client_id,
                        'mikrotik_id': secret.get('mikrotik_id', '')
                    })
            except Exception as e:
                logger.error(f"Error scanning PPPoE: {e}")

        # --- B. SCAN SIMPLE QUEUES ---
        if scan_type in ['mixed', 'dhcp_arp_queues']:
            try:
                queues = adapter._api_connection.get_resource('/queue/simple').get()
                for q in queues:
                    name = q.get('name', '')
                    target = q.get('target', '') 
                    comment = q.get('comment', '')
                    
                    if is_management_equipment(name, comment):
                        target_ip = target.split('/')[0] if target else ''
                        if target_ip: management_ips.add(target_ip)
                        continue

                    if not is_ip_allowed(target): continue
                    if not name or name.startswith('<pppoe-'): continue 
                    
                    queue_ip = target.split('/')[0] if target else ''
                    
                    # DETECCIÓN DE CAMBIOS
                    existing_client = existing_usernames_map.get(name.lower())
                    existing_by_ip = existing_clients_by_ip.get(queue_ip) if queue_ip else None
                    
                    is_duplicate = existing_client is not None or existing_by_ip is not None
                    name_changed = False
                    ip_changed = False
                    db_ip = None
                    client_id = None

                    if existing_by_ip:
                         client_id = existing_by_ip.id
                         if existing_by_ip.username.lower() != name.lower():
                              name_changed = True
                    elif existing_client:
                         client_id = existing_client.id
                         if existing_client.ip_address != queue_ip:
                              ip_changed = True
                              db_ip = existing_client.ip_address
                    
                    if name.lower() in seen_mikrotik_usernames: continue 
                    seen_mikrotik_usernames.add(name.lower())
                    if queue_ip: seen_ips.add(queue_ip)

                    preview_list.append({
                        'type': 'simple_queue', 'username': name, 'password': '',
                        'ip_address': queue_ip or 'Sin IP', 'profile': q.get('max-limit', ''),
                        'status': 'disabled' if q.get('disabled') == 'true' else 'active',
                        'exists_in_db': is_duplicate, 
                        'db_status': existing_client.status if existing_client else (existing_by_ip.status if existing_by_ip else None),
                        'name_changed': name_changed,
                        'ip_changed': ip_changed,
                        'old_username': existing_by_ip.username if name_changed else None,
                        'db_ip': db_ip,
                        'client_id': client_id,
                        'mikrotik_id': q.get('.id')
                    })
            except Exception as e:
                 logger.error(f"Error scanning Queues: {e}")

        # --- C. SCAN DHCP LEASES && ARP ---
        if scan_type in ['mixed', 'dhcp_arp_queues']:
            try:
                dhcp_leases = adapter.get_dhcp_leases()
                arp_table = adapter.get_arp_table()
                network_devices = {} 
                
                for lease in dhcp_leases:
                    ip = lease.get('address')
                    host_name = lease.get('host-name', '')
                    comment = lease.get('comment', '')
                    if is_management_equipment(host_name, comment):
                        if ip: management_ips.add(ip)
                        continue

                    if not ip or not is_ip_allowed(ip): continue
                    if ip in seen_ips: continue
                    
                    network_devices[ip] = {
                        'mac': lease.get('mac-address', ''),
                        'host': lease.get('host-name', lease.get('comment', f"Device-{ip.split('.')[-1]}")),
                        'source': 'DHCP'
                    }
                
                for arp in arp_table:
                    ip = arp.get('address')
                    if is_management_equipment(arp.get('comment', '')):
                        if ip: management_ips.add(ip)
                        continue

                    if not ip or not is_ip_allowed(ip): continue
                    if ip in seen_ips or ip in network_devices or ip in management_ips: continue
                    
                    network_devices[ip] = {
                        'mac': arp.get('mac-address', ''),
                        'host': arp.get('comment', f"ARP-Device-{ip.split('.')[-1]}"),
                        'source': 'ARP'
                    }
                
                for ip, info in network_devices.items():
                    username = info['host'].replace(' ', '_')
                    if username.lower() in seen_mikrotik_usernames:
                        username = f"{username}_{ip.split('.')[-1]}"

                    # DETECCIÓN DE CAMBIOS para Discovered
                    existing_client = existing_usernames_map.get(username.lower())
                    existing_by_ip = existing_clients_by_ip.get(ip)
                    
                    is_duplicate = existing_client is not None or existing_by_ip is not None
                    ip_changed = False
                    db_ip = None
                    client_id = None

                    if existing_by_ip:
                         client_id = existing_by_ip.id
                    elif existing_client:
                         client_id = existing_client.id
                         if existing_client.ip_address != ip:
                              ip_changed = True
                              db_ip = existing_client.ip_address

                    preview_list.append({
                        'type': 'discovered', 'username': username, 'password': 'N/A',
                        'ip_address': ip, 'profile': get_suggested_plan(ip), 'status': 'active',
                        'exists_in_db': is_duplicate, 
                        'ip_changed': ip_changed,
                        'db_ip': db_ip,
                        'client_id': client_id,
                        'mikrotik_id': f"new-{info['source']}", 'mac': info['mac']
                    })
            except Exception as e:
                logger.error(f"Error in advanced sync scanning: {e}")

        adapter.disconnect()
        
        # Contar clientes por tipo
        discovered_count = sum(1 for c in preview_list if c.get('type') == 'discovered')
        pppoe_count = sum(1 for c in preview_list if c.get('type') == 'pppoe')
        queue_count = sum(1 for c in preview_list if c.get('type') == 'simple_queue')
        ip_changes_count = sum(1 for c in preview_list if c.get('ip_changed', False))
        name_changes_count = sum(1 for c in preview_list if c.get('name_changed', False))
        
        return jsonify({
            'router_alias': router.alias, 'router_id': router_id,
            'total_found': len(preview_list), 'segments_filter_active': has_segments_filter,
            'clients': preview_list,
            'summary': {
                'discovered_no_queue': discovered_count, 'pppoe_secrets': pppoe_count,
                'simple_queues': queue_count, 'needs_provisioning': discovered_count > 0,
                'name_changes': name_changes_count,
                'ip_changes': ip_changes_count
            }
        })
        
    except Exception as e:
        logger.error(f"Error en preview import: {str(e)}")
        return jsonify({'error': str(e)}), 500


@clients_bp.route('/execute-import', methods=['POST'])
def execute_import_clients():
    """Importa clientes seleccionados"""
    data = request.json
    router_id = data.get('router_id')
    import_mode = data.get('import_mode', 'standard') # modes: standard, prorate, full_debt
    clients_to_import = data.get('clients', [])
    
    if not router_id or not clients_to_import:
        return jsonify({'error': 'Datos insuficientes'}), 400
        
    db = get_db()
    client_repo = db.get_client_repository()
    
    imported_count = 0
    errors = []
    
    current_total = len(client_repo.get_all())
    
    # CONSTANTES (Centralizadas)
    # PUERTO VIVAS (ID 2) -> 70.000
    # RESTO -> 90.000
    pvievas_id = 2 # Puerto Vivas
    PRICE_PUERTO_VIVAS = 70000.0
    PRICE_GENERAL = 90000.0
    
    # OPTIMIZACIÓN: Cargar clientes existentes en memoria UNA sola vez (O(1) lookup)
    # Creamos un Set de usernames normalizados para búsqueda rápida
    existing_clients_list = client_repo.get_all()
    existing_usernames = {c.username.lower() for c in existing_clients_list}
    
    # Determinar el siguiente número secuencial de CLI-XXXX basado en el máximo actual
    import re
    max_num = 0
    for c in existing_clients_list:
        if c.subscriber_code and c.subscriber_code.startswith('CLI-'):
            match = re.search(r'CLI-(\d+)', c.subscriber_code)
            if match:
                try:
                    num = int(match.group(1))
                    if num > max_num:
                        max_num = num
                except:
                    pass
    
    for item in clients_to_import:
        try:
            username = item.get('username')
            if not username: continue

            # Check duplicado (Optimizado)
            if username.lower() in existing_usernames:
                continue
                
            subscriber_code = f"CLI-{max_num + 1 + imported_count:04d}"
            legal_name = username.replace('_', ' ').replace('.', ' ').title()
            
            # Determinar tarifa
            try:
               rid_int = int(router_id)
            except:
               rid_int = 0

            fee = PRICE_GENERAL
            if rid_int == pvievas_id:
                fee = PRICE_PUERTO_VIVAS
            
            client_data = {
                'router_id': router_id,
                'subscriber_code': subscriber_code,
                'legal_name': legal_name,
                'username': username,
                'password': item.get('password', 'hidden'),
                'ip_address': item.get('ip_address', ''),
                'plan_name': item.get('profile') if item.get('profile') and item.get('profile') != 'Sin Plan' else 'default',
                'download_speed': '15M', # Default subida (Placeholder, plan real se define en router)
                'upload_speed': '15M',   # Default bajada
                'service_type': item.get('type', 'pppoe'), # pppoe o simple_queue
                'status': 'active' if item.get('status') == 'active' else 'suspended',
                'mikrotik_id': item.get('mikrotik_id', ''),
                'monthly_fee': fee, 
                'mac_address': item.get('mac', ''),
            }
            
            client_repo.create(client_data)
            new_client = client_repo.get_by_username(username)
            
            # --- LÓGICA DE REGULARIZACIÓN (Smart Import) ---
            if new_client and import_mode != 'standard':
                from src.application.services.billing_service import BillingService
                from src.infrastructure.database.models import Invoice, InvoiceItem
                
                billing_service = BillingService()
                now = datetime.now()
                
                amount_to_invoice = fee
                description = f"Mensualidad Inicial - {now.strftime('%B %Y')}"
                
                if import_mode == 'prorate':
                    # Calcular prorrata: (días restantes / total días) * fee
                    import calendar
                    days_in_month = calendar.monthrange(now.year, now.month)[1]
                    days_remaining = days_in_month - now.day + 1
                    prorate_factor = days_remaining / days_in_month
                    amount_to_invoice = round(fee * prorate_factor, 2)
                    description = f"Prorrateo Inicial ({days_remaining} días) - {now.strftime('%B %Y')}"
                
                # Crear Factura de Regularización
                new_invoice = Invoice(
                    client_id=new_client.id,
                    issue_date=now,
                    due_date=now + timedelta(days=3), # Vencimiento corto para regularización
                    total_amount=amount_to_invoice,
                    status='unpaid'
                )
                db.session.add(new_invoice)
                db.session.flush()
                
                item = InvoiceItem(
                    invoice_id=new_invoice.id,
                    description=description,
                    amount=amount_to_invoice
                )
                db.session.add(item)
                
                # Actualizar balance del cliente
                new_client.account_balance = amount_to_invoice
                db.session.commit()
                
                logger.info(f"✨ Regularización Smart aplicada a {username}: {description} (${amount_to_invoice})")

            imported_count += 1
            
            # Actualizar el set local para evitar duplicados dentro del mismo lote de importación
            existing_usernames.add(username.lower())
            
        except Exception as e:
            # IMPORTANTE: Rollback de la sesión para evitar "envenenamiento" de la transacción
            # Esto permite que el siguiente cliente del loop se procese en una transacción limpia
            db.session.rollback()
            logger.error(f"Fallo en importación de {item.get('username')}: {str(e)}")
            errors.append(f"Error importando {item.get('username')}: {str(e)}")
            
    # Auditoría de importación masiva
    if imported_count > 0:
        AuditService.log(
            operation='clients_imported_bulk',
            category='client',
            description=f"Importación masiva: {imported_count} clientes importados desde el router {router_id}.",
            new_state={'count': imported_count, 'router_id': router_id}
        )

    return jsonify({
        'success': True,
        'imported': imported_count,
        'errors': errors
    })


@clients_bp.route('/monitor', methods=['POST'])
def monitor_traffic():
    """Monitor de tráfico (Legacy/Fallback)"""
    client_ids = request.json
    if not client_ids: return jsonify({})
    
    from src.application.services.monitoring_manager import MonitoringManager
    manager = MonitoringManager.get_instance()
    db = get_db()
    router_repo = db.get_router_repository()
    client_repo = db.get_client_repository()
    
    try:
        all_clients = client_repo.get_all()
        target_clients = [c for c in all_clients if c.id in client_ids]
        grouped = {}
        for client in target_clients:
            if not client.router_id: continue
            if client.router_id not in grouped: grouped[client.router_id] = []
            grouped[client.router_id].append(client)
            
        results = {}
        for r_id, clients_list in grouped.items():
            router = router_repo.get_by_id(r_id)
            if not router: continue
            
            adapter = MikroTikAdapter()
            try:
                if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port, timeout=3):
                    router_results = manager.get_router_clients_traffic(r_id, [c.id for c in clients_list], adapter)
                    results.update(router_results)
                    adapter.disconnect()
            except Exception as e:
                logger.error(f"Error polling router {router.host_address}: {e}")
                
        return jsonify(results)
    except Exception as e:
         logger.error(f"Error traffic monitor: {e}")
         return jsonify({})

@clients_bp.route('/<int:client_id>/usage-report', methods=['GET'])
def get_usage_report(client_id):
    """
    Genera un reporte detallado de consumo y conectividad.
    """
    days = request.args.get('days', default=7, type=int)
    db = get_db()
    traffic_repo = db.get_traffic_repository()
    
    # Obtener historial ( snapshots de 10 min )
    history = traffic_repo.get_history(client_id, hours=days*24)
    
    if not history:
        return jsonify({
            'daily_usage': [],
            'availability': 0,
            'outages': []
        })

    # 1. Agrupar por día para el Histograma
    daily_stats = {}
    total_snapshots = len(history)
    online_snapshots = 0
    
    # Para calcular consumo diario necesitamos deltas de los contadores de bytes
    # download_bytes/upload_bytes son acumulados del router.
    
    # Agrupamos por fecha (YYYY-MM-DD)
    for h in history:
        day_key = h.timestamp.date().isoformat()
        if day_key not in daily_stats:
            daily_stats[day_key] = {'down': [], 'up': [], 'online': 0, 'total': 0}
        
        daily_stats[day_key]['down'].append(h.download_bytes)
        daily_stats[day_key]['up'].append(h.upload_bytes)
        daily_stats[day_key]['total'] += 1
        if h.is_online:
            daily_stats[day_key]['online'] += 1
            online_snapshots += 1

    report_daily = []
    for day, stats in sorted(daily_stats.items()):
        # Calcular delta (Consumo real del día)
        # down_delta = max(stats['down']) - min(stats['down'])
        # Pero si hubo reajuste (reboot), el min podría ser el post-reboot. 
        # Algoritmo simple: Suma de deltas positivos consecutivos
        
        def calculate_total_delta(series):
            if not series: return 0
            total = 0
            for i in range(1, len(series)):
                diff = series[i] - series[i-1]
                if diff > 0:
                    total += diff
            return total

        down_gb = calculate_total_delta(stats['down']) / (1024**3)
        up_gb = calculate_total_delta(stats['up']) / (1024**3)
        
        report_daily.append({
            'date': day,
            'download_gb': round(down_gb, 2),
            'upload_gb': round(up_gb, 2),
            'uptime_pct': round((stats['online'] / stats['total']) * 100, 1)
        })

    # 2. Detectar cortes (Outages)
    outages = []
    current_outage = None
    
    for h in history:
        if not h.is_online:
            if not current_outage:
                current_outage = {'start': h.timestamp.isoformat(), 'end': None}
        else:
            if current_outage:
                current_outage['end'] = h.timestamp.isoformat()
                # Calcular duración
                start_dt = datetime.fromisoformat(current_outage['start'])
                duration = h.timestamp - start_dt
                current_outage['duration_mins'] = int(duration.total_seconds() / 60)
                outages.append(current_outage)
                current_outage = None
    
    # 3. Calcular métricas globales de calidad
    avg_quality = 0
    avg_latency = 0
    latency_jitter = 0
    if online_snapshots > 0:
        active_hist = [h for h in history if h.is_online]
        total_q = sum([h.quality_score for h in active_hist])
        latencies = [h.latency_ms for h in active_hist]
        total_lat = sum(latencies)
        avg_quality = round(total_q / len(active_hist), 1)
        avg_latency = round(total_lat / len(active_hist), 0)
        
        # Calcular Jitter (Desviación estándar simple de latencia)
        if len(latencies) > 1:
            mean = total_lat / len(latencies)
            variance = sum((x - mean) ** 2 for x in latencies) / len(latencies)
            latency_jitter = round(variance ** 0.5, 1)

    # 4. INTELIGENCIA DE TRÁFICO (IA)
    # Perfil de usuario basado en consumo y ráfaga
    total_gb = sum([d['download_gb'] for d in report_daily])
    avg_daily_gb = total_gb / len(report_daily) if report_daily else 0
    
    user_profile = "Ligero"
    if avg_daily_gb > 10: user_profile = "Gamer / Heavy"
    elif avg_daily_gb > 5: user_profile = "Streaming / TV"
    elif avg_daily_gb > 2: user_profile = "Estándar"

    # Predicción (Simple Linear Trend o Promedio Ponderado)
    predicted_next_month = avg_daily_gb * 30
    
    # Detección de Hora Pico (Peak Hour)
    hour_stats = {} # {hour: total_bps}
    for h in history:
        hour = h.timestamp.hour
        if hour not in hour_stats: hour_stats[hour] = []
        hour_stats[hour].append(h.download_bps)
    
    peak_hour = 0
    max_peak_val = 0
    for h, vals in hour_stats.items():
        avg_val = sum(vals) / len(vals)
        if avg_val > max_peak_val:
            max_peak_val = avg_val
            peak_hour = h

    if current_outage:
        current_outage['end'] = 'En curso'
        outages.append(current_outage)

    return jsonify({
        'daily_usage': report_daily,
        'availability': round((online_snapshots / total_snapshots) * 100, 2) if total_snapshots > 0 else 0,
        'quality_score': avg_quality,
        'avg_latency': int(avg_latency),
        'latency_jitter': latency_jitter,
        'outages': sorted(outages, key=lambda x: x['start'], reverse=True)[:10], # Top 10 recientes
        'history_raw': [h.to_dict() for h in history], # Snapshots para el modal de estabilidad
        'intelligence': {
            'user_profile': user_profile,
            'predicted_monthly_gb': round(predicted_next_month, 1),
            'peak_hour': f"{peak_hour:02d}:00",
            'recommended_plan': "Upgrade Sugerido" if avg_daily_gb > 15 else "Plan Óptimo",
            'stability_status': "Excelente" if avg_quality > 95 else "Inestable" if avg_quality < 70 else "Normal"
        }
    })


@clients_bp.route('/bulk-update-plan', methods=['POST'])
def bulk_update_plan():
    """Actualiza el plan de múltiples clientes de forma masiva"""
    data = request.json
    client_ids = data.get('client_ids', [])
    plan_id = data.get('plan_id', type=int) if isinstance(data.get('plan_id'), str) else data.get('plan_id')
    
    if not client_ids or not plan_id:
        return jsonify({'error': 'IDs de clientes y ID de plan requeridos'}), 400
        
    db = get_db()
    client_repo = db.get_client_repository()
    plan = db.session.query(InternetPlan).get(plan_id)
    
    if not plan:
        return jsonify({'error': 'Plan no encontrado'}), 404
        
    # Helper para formatear velocidades (Copia de la lógica en create/update)
    def format_speed(kb):
        if not kb: return "0"
        if kb >= 1000: return f"{kb//1000}M"
        return f"{kb}k"

    update_data = {
        'plan_id': plan_id,
        'plan_name': plan.name,
        'monthly_fee': plan.monthly_price,
        'download_speed': format_speed(plan.download_speed),
        'upload_speed': format_speed(plan.upload_speed),
        'service_type': plan.service_type
    }
    
    updated_count = 0
    errors = []
    
    for c_id in client_ids:
        try:
            client = client_repo.get_by_id(c_id)
            if not client:
                errors.append(f"Cliente {c_id} no encontrado")
                continue
                
            old_username = client.username
            router_id = client.router_id
            
            # Actualizar en DB
            client_repo.update(c_id, update_data)
            updated_count += 1
            
            # Encolar Sincronización con MikroTik
            if router_id:
                updated_client = client_repo.get_by_id(c_id)
                from src.application.services.sync_service import SyncService
                sync_service = SyncService(db)
                sync_service.queue_operation(
                    client_id=c_id,
                    router_id=router_id,
                    operation_type='update',
                    operation_data={'old_username': old_username, 'data': updated_client.to_dict()}
                )
        except Exception as e:
            logger.error(f"Error in bulk plan update for client {c_id}: {e}")
            errors.append(f"Error procesando cliente {c_id}: {str(e)}")
            
    # Auditoría de actualización masiva
    if updated_count > 0:
        AuditService.log(
            operation='clients_bulk_plan_update',
            category='client',
            description=f"Actualización masiva de planes: {updated_count} clientes actualizados al plan ID {plan_id}.",
            new_state={'plan_id': plan_id, 'count': updated_count}
        )

    return jsonify({
        'message': f'Se actualizaron {updated_count} clientes de forma masiva',
        'errors': errors
    })


@clients_bp.route('/lookup-identity', methods=['GET'])
def lookup_identity():
    """Busca la identidad de un cliente (IP/MAC) directamente en el MikroTik"""
    router_id = request.args.get('router_id', type=int)
    ip = request.args.get('ip')
    mac = request.args.get('mac')
    username = request.args.get('username')
    
    if not router_id:
        return jsonify({'error': 'Router ID requerido'}), 400
        
    db = get_db()
    router = db.get_router_repository().get_by_id(router_id)
    if not router:
        return jsonify({'error': 'Router no encontrado'}), 404
        
    adapter = MikroTikAdapter()
    try:
        if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port, timeout=5):
            identity = adapter.get_client_identity(ip=ip, mac=mac, username=username)
            adapter.disconnect()
            return jsonify(identity)
        else:
            return jsonify({'error': 'No se pudo conectar al router'}), 503
    except Exception as e:
        logger.error(f"Error looking up identity: {e}")
        return jsonify({'error': str(e)}), 500


@clients_bp.route('/<int:client_id>/fix-queue', methods=['POST'])
def fix_client_queue(client_id):
    """
    Crea/Repara la Simple Queue de un cliente en MikroTik
    Útil cuando aparece como 'Detected (No Queue)'
    """
    db = get_db()
    client_repo = db.get_client_repository()
    router_repo = db.get_router_repository()
    
    client = client_repo.get_by_id(client_id)
    if not client:
        return jsonify({'error': 'Cliente no encontrado'}), 404
    
    if not client.router_id:
        return jsonify({'error': 'Cliente sin router asignado'}), 400
    
    router = router_repo.get_by_id(client.router_id)
    if not router:
        return jsonify({'error': 'Router no encontrado'}), 404
    
    if router.status != 'online':
        return jsonify({'error': 'Router offline, no se puede reparar'}), 503
    
    # Determinar velocidad
    max_limit = "15M/15M" # Default
    if client.download_speed and client.upload_speed:
        # Convertir formato visual (15M) a formato MikroTik (15M/15M)
        # Ojo: download_speed en DB suele ser "15M". upload "15M"
        # MikroTik max-limit = upload/download
        ul = client.upload_speed if 'M' in client.upload_speed or 'k' in client.upload_speed else f"{client.upload_speed}M"
        dl = client.download_speed if 'M' in client.download_speed or 'k' in client.download_speed else f"{client.download_speed}M"
        max_limit = f"{ul}/{dl}"

    target_ip = client.ip_address
    if not target_ip:
         return jsonify({'error': 'Cliente sin IP asignada'}), 400
         
    adapter = MikroTikAdapter()
    try:
        if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port, timeout=5):
            # Usar nombre legal o username
            name = client.legal_name or client.username
            
            # Crear Queue
            success = adapter.create_simple_queue(
                name=name,
                target=f"{target_ip}/32",
                max_limit=max_limit
            )
            adapter.disconnect()
            
            if success:
                AuditService.log(
                    operation='FIX_QUEUE',
                    category='client',
                    entity_type='client',
                    entity_id=client_id,
                    description=f"Reparación manual de Simple Queue para {client.legal_name} ({target_ip})"
                )
                logger.info(f"✅ Cola reparada para {client.legal_name} ({client.ip_address})")
                return jsonify({'message': 'Cola simple creada/actualizada correctamente', 'success': True})
            else:
                return jsonify({'error': 'Falló la creación de la cola en MikroTik'}), 500
        else:
            return jsonify({'error': 'No se pudo conectar al router'}), 503
    except Exception as e:
        logger.error(f"Error fixing queue for {client.legal_name}: {e}")
        return jsonify({'error': str(e)}), 500


@clients_bp.route('/<int:client_id>/traffic-history', methods=['GET'])
def get_client_traffic_history(client_id):
    """
    Obtiene el historial de tráfico de un cliente específico (mocked por ahora ya que el backend de telemetria no esta activo para clientes individuales en sqlite)
    """
    hours = request.args.get('hours', default=24, type=int)
    from src.application.services.monitoring_manager import MonitoringManager
    # As the telemetry method does not exist or raises an error, we provide an empty array for now 
    # to avoid the 500 error while the monitoring engine is fully implemented.
    try:
        if hasattr(MonitoringManager.get_instance(), 'get_client_telemetry_history'):
            history = MonitoringManager.get_instance().get_client_telemetry_history(client_id, hours=hours)
            return jsonify([h.to_dict() for h in history])
    except Exception as e:
        logger.error(f"Error fetching telemetry: {e}")
        pass
    
    return jsonify([])

def get_router_clients_traffic(router_id: int, client_ids: List[int], adapter: MikroTikAdapter) -> Dict[str, Any]:
    """
    Wrapper para mantener compatibilidad si otros módulos lo usan.
    Delegamos al MonitoringManager para evitar duplicación.
    """
    from src.application.services.monitoring_manager import MonitoringManager
    return MonitoringManager.get_instance().get_router_clients_traffic(router_id, client_ids, adapter)


@clients_bp.route('/<int:client_id>/promises', methods=['GET'])
def get_client_promises(client_id):
    """Obtiene el historial de promesas de un cliente"""
    db = get_db()
    session = db.session
    
    promises = session.query(PaymentPromise).filter(
        PaymentPromise.client_id == client_id
    ).order_by(PaymentPromise.created_at.desc()).all()
    
    return jsonify([p.to_dict() for p in promises])


@clients_bp.route('/bulk-suspend-pending', methods=['POST'])
def bulk_suspend_pending_by_router():
    """
    Suspende todos los clientes pendientes (con deuda) de un router específico.
    """
    try:
        data = request.get_json()
        router_id = data.get('router_id')
        
        if not router_id:
            return jsonify({'error': 'router_id es requerido'}), 400
        
        db = get_db()
        client_repo = db.get_client_repository()
        router_repo = db.get_router_repository()
        
        
        # Obtener todos los clientes del router con deuda pendiente
        # NO filtrar por status - queremos cortar TODOS los que tengan deuda
        all_clients = client_repo.get_by_router(router_id)
        clients_to_suspend = [
            c for c in all_clients 
            if c.account_balance > 0  # Solo verificar deuda, no status
        ]
        
        if not clients_to_suspend:
            return jsonify({
                'message': 'No hay clientes pendientes en este router',
                'suspended': 0
            }), 200
        
        logger.info(f"🔄 Iniciando corte masivo: {len(clients_to_suspend)} clientes del router {router_id}")
        
        # Get router and adapter
        router = router_repo.get_by_id(router_id)
        adapter = None
        mikrotik_connected = False
        
        if router and router.status == 'online':
            adapter = MikroTikAdapter()
            try:
                if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
                    mikrotik_connected = True
                    logger.info(f"✅ Conectado a MikroTik {router.host_address}")
                else:
                    logger.error(f"❌ No se pudo conectar a MikroTik {router.host_address}")
                    adapter = None
            except Exception as e:
                logger.error(f"❌ Error connecting to MikroTik: {e}")
                adapter = None
        else:
            logger.warning(f"⚠️ Router {router_id} no está online o no existe")
        
        suspended_count = 0
        mikrotik_sync_count = 0
        errors = []
        
        for client in clients_to_suspend:
            try:
                logger.info(f"⏳ Procesando cliente: {client.legal_name} (ID: {client.id}, IP: {client.ip_address}, Status actual: {client.status})")
                
                # 1. Suspend in database solo si NO está suspendido
                if client.status != 'suspended':
                    updated_client = client_repo.suspend(client.id)
                    logger.info(f"✅ BD actualizada para {client.legal_name} (active → suspended)")
                else:
                    logger.info(f"ℹ️ {client.legal_name} ya estaba suspendido en BD, solo sincronizamos MikroTik")
                
                # 2. SIEMPRE sincronizar con MikroTik (agregar a Address List si no está)
                if adapter and mikrotik_connected:
                    try:
                        # Refetch para tener datos actualizados
                        fresh_client = client_repo.get_by_id(client.id)
                        client_dict = fresh_client.to_dict() if fresh_client else client.to_dict()
                        
                        logger.info(f"📡 Sincronizando con MikroTik: {client.legal_name} - IP: {client_dict.get('ip_address')}")
                        
                        result = adapter.suspend_client_service(client_dict)
                        if result:
                            mikrotik_sync_count += 1
                            logger.info(f"✅ MikroTik sincronizado para {client.legal_name}")
                        else:
                            logger.error(f"❌ MikroTik sync falló para {client.legal_name}")
                            
                    except Exception as e:
                        logger.error(f"❌ Error syncing client {client.id} ({client.legal_name}) with MikroTik: {e}")
                        errors.append({
                            'client_id': client.id, 
                            'name': client.legal_name,
                            'error': f'MikroTik sync failed: {str(e)}'
                        })
                else:
                    logger.warning(f"⚠️ No hay conexión MikroTik para sincronizar {client.legal_name}")
                
                suspended_count += 1
                
                # 3. Audit log solo si se cambió el estado
                if client.status != 'suspended':
                    AuditService.log(
                        operation='bulk_suspend_pending',
                        category='client',
                        entity_type='client',
                        entity_id=client.id,
                        description=f"Suspensión masiva por router: {client.legal_name}",
                        previous_state={'status': 'active'},
                        new_state={'status': 'suspended'}
                    )
                
            except Exception as e:
                logger.error(f"❌ Error suspendiendo cliente {client.id} ({client.legal_name}): {e}")
                errors.append({
                    'client_id': client.id,
                    'name': client.legal_name, 
                    'error': str(e)
                })
        
        if adapter:
            adapter.disconnect()
            logger.info(f"🔌 Desconectado de MikroTik")
        
        result_message = f'{suspended_count} clientes suspendidos en BD'
        if mikrotik_connected:
            result_message += f', {mikrotik_sync_count} sincronizados con MikroTik'
        
        logger.info(f"✅ Corte masivo completado: {result_message}")
        
        return jsonify({
            'message': result_message,
            'suspended': suspended_count,
            'mikrotik_synced': mikrotik_sync_count if mikrotik_connected else None,
            'errors': errors if errors else None
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error en bulk suspend by router: {e}")
        return jsonify({'error': str(e)}), 500


@clients_bp.route('/bulk-suspend-all-pending', methods=['POST'])
def bulk_suspend_all_pending():
    """
    Suspende TODOS los clientes pendientes (con deuda) de TODOS los routers.
    """
    try:
        db = get_db()
        client_repo = db.get_client_repository()
        router_repo = db.get_router_repository()
        
        # Obtener todos los clientes
        all_clients = client_repo.get_all()
        clients_to_suspend = [
            c for c in all_clients 
            if c.account_balance > 0 and c.status != 'suspended'
        ]
        
        if not clients_to_suspend:
            return jsonify({
                'message': 'No hay clientes pendientes',
                'suspended': 0
            }), 200
        
        # Agrupar por router para eficiencia
        clients_by_router = {}
        for client in clients_to_suspend:
            if client.router_id:
                if client.router_id not in clients_by_router:
                    clients_by_router[client.router_id] = []
                clients_by_router[client.router_id].append(client)
        
        suspended_count = 0
        errors = []
        
        # Procesar por router
        for router_id, router_clients in clients_by_router.items():
            router = router_repo.get_by_id(router_id)
            adapter = None
            
            if router and router.status == 'online':
                adapter = MikroTikAdapter()
                try:
                    if not adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
                        adapter = None
                except Exception as e:
                    logger.error(f"Error connecting to router {router_id}: {e}")
                    adapter = None
            
            for client in router_clients:
                try:
                    # Suspend in database
                    client_repo.suspend(client.id)
                    
                    # Sync with MikroTik
                    if adapter:
                        try:
                            adapter.suspend_client_service(client.to_dict())
                        except Exception as e:
                            logger.error(f"Error syncing client {client.id} with MikroTik: {e}")
                    
                    suspended_count += 1
                    
                    # Audit log
                    AuditService.log(
                        operation='bulk_suspend_all_pending',
                        category='client',
                        entity_type='client',
                        entity_id=client.id,
                        description=f"Suspensión masiva global: {client.legal_name}",
                        previous_state={'status': 'active'},
                        new_state={'status': 'suspended'}
                    )
                    
                except Exception as e:
                    logger.error(f"Error suspendiendo cliente {client.id}: {e}")
                    errors.append({'client_id': client.id, 'error': str(e)})
            
            if adapter:
                adapter.disconnect()
        
        return jsonify({
            'message': f'{suspended_count} clientes suspendidos',
            'suspended': suspended_count,
            'errors': errors if errors else None
        }), 200
        
    except Exception as e:
        logger.error(f"Error en bulk suspend all pending: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# BULK OPERATIONS WITH MIKROTIK VALIDATION
# ============================================================================

@clients_bp.route('/bulk-suspend', methods=['POST'])
def bulk_suspend():
    """Suspende múltiples clientes validando estado en MikroTik"""
    try:
        data = request.get_json()
        client_ids = data.get('client_ids', [])
        
        if not client_ids:
            return jsonify({'error': 'No se proporcionaron IDs de clientes'}), 400
        
        db = get_db()
        client_repo = db.get_client_repository()
        router_repo = db.get_router_repository()
        audit = AuditService
        
        # Agrupar clientes por router
        clients_by_router = {}
        for client_id in client_ids:
            client = client_repo.get_by_id(client_id)
            if not client:
                continue
            
            router_id = client.router_id
            if router_id not in clients_by_router:
                clients_by_router[router_id] = []
            clients_by_router[router_id].append(client)
        
        already_blocked = []
        newly_blocked = []
        system_only = []
        errors = []
        
        # Procesar por router
        for router_id, clients in clients_by_router.items():
            router = router_repo.get_by_id(router_id)
            if not router:
                for c in clients:
                    errors.append({'client_id': c.id, 'error': 'Router no encontrado'})
                continue
            
            adapter = None
            try:
                adapter = MikroTikAdapter(router.to_dict())
                
                # Obtener lista actual de IPs bloqueadas en MikroTik
                blocked_ips = set()
                try:
                    address_list = adapter.get_address_list('IPS_BLOQUEADAS')
                    blocked_ips = {entry['address'] for entry in address_list}
                except Exception as e:
                    logger.warning(f"No se pudo obtener lista de bloqueados: {e}")
                
                for client in clients:
                    try:
                        client_ip = client.ip_address
                        
                        # Verificar si ya está bloqueado en MikroTik
                        if client_ip in blocked_ips:
                            # Ya está bloqueado, solo actualizar sistema
                            client.status = 'suspended'
                            client_repo.update(client)
                            already_blocked.append(client.id)
                            logger.info(f"Cliente {client.id} ya estaba bloqueado en MikroTik, solo se actualizó el sistema")
                        else:
                            # No está bloqueado, suspender en MikroTik
                            try:
                                adapter.suspend_client(client_ip)
                                client.status = 'suspended'
                                client_repo.update(client)
                                newly_blocked.append(client.id)
                                logger.info(f"Cliente {client.id} bloqueado en MikroTik y sistema")
                            except Exception as e:
                                # Si falla MikroTik, solo actualizar sistema
                                client.status = 'suspended'
                                client_repo.update(client)
                                system_only.append(client.id)
                                logger.warning(f"Cliente {client.id} suspendido solo en sistema (error MikroTik): {e}")
                        
                        # Auditar
                        audit.log_action(
                            action_type='client_suspended',
                            entity_type='client',
                            entity_id=client.id,
                            details=f'Suspensión masiva - Cliente: {client.legal_name}'
                        )
                        
                    except Exception as e:
                        logger.error(f"Error suspendiendo cliente {client.id}: {e}")
                        errors.append({'client_id': client.id, 'error': str(e)})
                
            finally:
                if adapter:
                    adapter.disconnect()
        
        # Mensaje detallado
        total_processed = len(already_blocked) + len(newly_blocked) + len(system_only)
        message_parts = []
        
        if newly_blocked:
            message_parts.append(f"{len(newly_blocked)} bloqueados en MikroTik")
        if already_blocked:
            message_parts.append(f"{len(already_blocked)} ya estaban bloqueados")
        if system_only:
            message_parts.append(f"{len(system_only)} solo en sistema")
        
        message = f"Suspensión masiva: {', '.join(message_parts)}" if message_parts else "No se procesaron clientes"
        
        return jsonify({
            'message': message,
            'total': total_processed,
            'newly_blocked': len(newly_blocked),
            'already_blocked': len(already_blocked),
            'system_only': len(system_only),
            'errors': errors if errors else None
        }), 200
        
    except Exception as e:
        logger.error(f"Error en bulk suspend: {e}")
        return jsonify({'error': str(e)}), 500


@clients_bp.route('/bulk-temporary-activation', methods=['POST'])
def bulk_temporary_activation():
    """Activa temporalmente múltiples clientes con promesa de pago de 5 días"""
    try:
        data = request.get_json()
        client_ids = data.get('client_ids', [])
        
        if not client_ids:
            return jsonify({'error': 'No se proporcionaron IDs de clientes'}), 400
        
        from src.application.services.batch_service import BatchService
        batch_service = BatchService()
        
        # Ejecutar acción masiva de restauración con promesa de 5 días por defecto
        results = batch_service.execute_batch_action(
            action='restore',
            client_ids=client_ids,
            extra_data={'promise_days': 5}
        )
        
        return jsonify({
            'success': True,
            'message': f"Activación temporal completada: {results['success_count']} éxitos, {results['fail_count']} fallos.",
            'results': results
        }), 200
        
    except Exception as e:
        logger.error(f"Error en bulk temporary activation: {e}")
        return jsonify({'error': str(e)}), 500


@clients_bp.route('/bulk-cash-payment', methods=['POST'])
def bulk_cash_payment():
    """Procesa pagos en efectivo masivos usando BatchService (Contabilidad individual + Resiliencia MikroTik)"""
    try:
        data = request.get_json()
        client_ids = data.get('client_ids', [])
        
        if not client_ids:
            return jsonify({'error': 'No se proporcionaron IDs de clientes'}), 400
        
        from src.application.services.batch_service import BatchService
        batch_service = BatchService()
        
        # Ejecutar acción masiva de pago
        # BatchService ya usa BillingService.register_payment internamente, lo que garantiza:
        # 1. Pago individual por cliente.
        # 2. Actualización de facturas FIFO.
        # 3. Auditoría contable individual.
        # 4. Reactivación automática resiliente (online o queued).
        results = batch_service.execute_batch_action(
            action='pay',
            client_ids=client_ids,
            extra_data={'payment_method': 'cash', 'notes': 'Pago masivo en efectivo registrado'}
        )
        
        message = f"Proceso masivo completado: {results['success_count']} éxitos, {results['fail_count']} fallos."
        
        return jsonify({
            'success': True,
            'message': message,
            'results': results
        }), 200
        
    except Exception as e:
        logger.error(f"Error en bulk cash payment: {e}")
        return jsonify({'error': str(e)}), 500
        
    except Exception as e:
        logger.error(f"Error en bulk cash payment: {e}")
        return jsonify({'error': str(e)}), 500

@clients_bp.route('/bulk-sync-ips', methods=['POST'])
def bulk_sync_ips():
    """Actualiza la IP de múltiples clientes de forma masiva"""
    try:
        data = request.get_json()
        updates = data.get('updates', []) # [{client_id, ip_address}, ...]
        
        if not updates:
            return jsonify({'error': 'No se proporcionaron actualizaciones'}), 400
            
        db = get_db()
        client_repo = db.get_client_repository()
        
        success_count = 0
        errors = []
        
        for item in updates:
            client_id = item.get('client_id')
            new_ip = item.get('ip_address')
            
            if not client_id or not new_ip:
                errors.append(f"Datos inválidos para item: {item}")
                continue
                
            try:
                # Actualizar en la base de datos
                # Solo actualizamos la IP, el repo de SQLAlchemy debería manejar el merge
                client_repo.update(client_id, {'ip_address': new_ip})
                success_count += 1
            except Exception as e:
                errors.append(f"Error sincronizando cliente {client_id}: {str(e)}")
        
        if success_count > 0:
            AuditService.log(
                operation='clients_bulk_ip_sync',
                category='client',
                description=f"Sincronización masiva: {success_count} IPs de clientes corregidas desde escaneo.",
                new_state={'count': success_count}
            )
            
        return jsonify({
            'success': True,
            'synchronized': success_count,
            'errors': errors
        }), 200
        
    except Exception as e:
        logger.error(f"Error en bulk IP sync: {e}")
        return jsonify({'error': str(e)}), 500


@clients_bp.route('/bulk-revert-recent-payments', methods=['POST'])
def bulk_revert_recent_payments():
    """
    Revierte los últimos pagos de múltiples clientes.
    Útil para deshacer pagos de cortesías que no fueron cumplidas.
    
    Request Body:
    {
        "client_ids": [1, 2, 3],
        "reason": "Reversión masiva por cortesía vencida" (opcional),
        "days_back": 7 (opcional, default 7)
    }
    
    Response:
    {
        "success": true,
        "message": "...",
        "reverted": 5,
        "skipped": 2,
        "details": {
            "reverted_ids": [...],
            "skipped_no_payment": [...],
            "errors": [...]
        }
    }
    """
    try:
        data = request.get_json()
        client_ids = data.get('client_ids', [])
        reason = data.get('reason', 'Reversión masiva desde Acción Masiva')
        days_back = data.get('days_back', 7)
        
        if not client_ids:
            return jsonify({'error': 'No se proporcionaron IDs de clientes'}), 400
        
        from src.infrastructure.database.models import Payment
        from src.application.services.billing_service import BillingService
        from datetime import timedelta
        
        db = get_db()
        session = db.session
        billing_service = BillingService()
        
        # Fecha límite para buscar pagos recientes
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        reverted_count = 0
        skipped_count = 0
        reverted_ids = []
        skipped_no_payment = []
        errors = []
        
        logger.info(f"🔄 Iniciando reversión masiva de pagos para {len(client_ids)} clientes")
        
        for client_id in client_ids:
            try:
                # Buscar el pago más reciente del cliente (últimos N días)
                recent_payment = session.query(Payment).filter(
                    Payment.client_id == client_id,
                    Payment.payment_date >= cutoff_date
                ).order_by(Payment.payment_date.desc()).first()
                
                if not recent_payment:
                    logger.info(f"⚠️ Cliente {client_id} no tiene pagos recientes (últimos {days_back} días)")
                    skipped_no_payment.append(client_id)
                    skipped_count += 1
                    continue
                
                # Revertir el pago usando BillingService
                logger.info(f"🔄 Revirtiendo pago {recent_payment.id} del cliente {client_id} (${recent_payment.amount})")
                billing_service.revert_payment(recent_payment.id, reason)
                
                reverted_ids.append(client_id)
                reverted_count += 1
                
            except Exception as e:
                logger.error(f"❌ Error revirtiendo pago del cliente {client_id}: {e}")
                errors.append({
                    'client_id': client_id,
                    'error': str(e)
                })
        
        # Auditoría global de la operación masiva
        if reverted_count > 0:
            AuditService.log(
                operation='bulk_revert_payments',
                category='accounting',
                description=f"Reversión masiva de pagos: {reverted_count} clientes procesados. Motivo: {reason}",
                new_state={
                    'reverted_count': reverted_count,
                    'client_ids': reverted_ids,
                    'reason': reason
                }
            )
        
        message = f"Reversión masiva completada: {reverted_count} pagos revertidos"
        if skipped_count > 0:
            message += f", {skipped_count} clientes sin pagos recientes"
        
        logger.info(f"✅ {message}")
        
        return jsonify({
            'success': True,
            'message': message,
            'reverted': reverted_count,
            'skipped': skipped_count,
            'details': {
                'reverted_ids': reverted_ids,
                'skipped_no_payment': skipped_no_payment,
                'errors': errors if errors else None
            }
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error crítico en bulk revert payments: {e}")
        return jsonify({'error': f'Error interno al revertir pagos: {str(e)}'}), 500

@clients_bp.route('/export', methods=['GET'])
@login_required
def export_clients():
    """Exporta los clientes a Excel basado en filtros actuales"""
    from flask import make_response
    from src.application.services.report_service import ReportService
    
    db = get_db()
    client_repo = db.get_client_repository()
    
    router_id = request.args.get('router_id', type=int)
    plan_id = request.args.get('plan_id', type=int)
    status = request.args.get('status')
    search = request.args.get('search')
    
    user = g.user
    is_restricted_role = user.role not in [UserRole.ADMIN.value, UserRole.ADMIN_FEM.value, UserRole.PARTNER.value]
    
    assigned_collector_id = None
    if is_restricted_role:
        if user.role == UserRole.COLLECTOR.value:
            assigned_collector_id = user.id
        elif user.assigned_router_id:
            router_id = user.assigned_router_id
        else:
            return jsonify({'error': 'No tienes permisos para exportar clientes'}), 403
            
    try:
        clients = client_repo.get_filtered(
            router_id=router_id, 
            status=status, 
            search=search, 
            plan_id=plan_id,
            assigned_collector_id=assigned_collector_id
        )
        
        clients_dict = [c.to_dict() for c in clients]
        
        router_name = "General"
        if router_id:
            router = db.get_router_repository().get_by_id(router_id)
            if router:
                router_name = router.alias
                
        excel_buffer = ReportService.generate_clients_excel(clients_dict, router_name=router_name)
        filename = f"clientes_{router_name.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        response = make_response(excel_buffer.getvalue())
        response.headers["Content-Disposition"] = f"attachment; filename={filename}"
        response.headers["Content-type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return response
    except Exception as e:
        logger.error(f"Error exporting clients: {e}")
        return jsonify({'error': 'Error al generar el archivo Excel'}), 500

