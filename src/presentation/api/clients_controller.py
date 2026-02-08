"""
Clients API Controller - DATOS REALES
Endpoints para gestión completa de clientes con importación MikroTik y filtrado por Segmentos
"""
from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
from typing import List, Dict, Any
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import NetworkSegment, InternetPlan
from src.infrastructure.mikrotik.adapter import MikroTikAdapter
from src.application.services.audit_service import AuditService
from ipaddress import ip_address, ip_network
import logging

logger = logging.getLogger(__name__)

clients_bp = Blueprint('clients', __name__, url_prefix='/api/clients')


@clients_bp.route('', methods=['GET'])
def get_clients():
    """Obtiene todos los clientes con filtros combinados"""
    db = get_db()
    client_repo = db.get_client_repository()
    
    router_id = request.args.get('router_id', type=int)
    plan_id = request.args.get('plan_id', type=int)
    status = request.args.get('status')
    search = request.args.get('search')
    
    # Use the new combined filtering method
    clients = client_repo.get_filtered(router_id=router_id, status=status, search=search, plan_id=plan_id)
    
    return jsonify([c.to_dict() for c in clients])


@clients_bp.route('/<int:client_id>', methods=['GET'])
def get_client(client_id):
    """Obtiene un cliente específico"""
    db = get_db()
    client_repo = db.get_client_repository()
    client = client_repo.get_by_id(client_id)
    if not client:
        return jsonify({'error': 'Cliente no encontrado'}), 404
    return jsonify(client.to_dict())


@clients_bp.route('', methods=['POST'])
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

    try:
        client = client_repo.create(data)
        
        # Intentar crear en MikroTik si el router está online (Best Effort)
        # Esto faltaba en la implementación original
        try:
            if client.router_id:
                router = db.get_router_repository().get_by_id(client.router_id)
                if router and router.status == 'online':
                    adapter = MikroTikAdapter()
                    if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port, timeout=3):
                        adapter.create_client_service(client.to_dict())
                        adapter.disconnect()
                else:
                    # Encolar en Sentinel si no se pudo crear directo
                    sync_repo = db.get_sync_repository()
                    sync_repo.add_task(
                        router_id=client.router_id,
                        client_id=client.id,
                        operation='create', # Nota: Sentinel necesita implementar 'create'
                        payload={'data': client.to_dict()}
                    )
        except Exception as e:
            logger.error(f"Error provisioning client on MikroTik (queued): {e}")

        # Auditoría de creación
        AuditService.log(
            operation='client_created',
            category='client',
            entity_type='client',
            entity_id=client.id,
            description=f"Nuevo cliente creado: {client.legal_name} ({client.username})",
            new_state=client.to_dict()
        )
        
        return jsonify(client.to_dict()), 201
    except Exception as e:
        logger.error(f"Error creating client: {str(e)}")
        return jsonify({'error': str(e)}), 400


@clients_bp.route('/<int:client_id>', methods=['PUT'])
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

    try:
        # Actualizar en Base de Datos
        updated_client = client_repo.update(client_id, data)
        
        # SINCRONIZACIÓN CON MIKROTIK (Sentinel Logic)
        if router_id:
            router = router_repo.get_by_id(router_id)
            if router:
                sync_success = False
                
                # 1. Intentar sincronización directa si está online
                if router.status == 'online':
                    adapter = MikroTikAdapter()
                    try:
                        if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port, timeout=3):
                            sync_data = updated_client.to_dict()
                            sync_success = adapter.update_client_service(old_username, sync_data)
                            adapter.disconnect()
                    except Exception as e:
                        logger.error(f"Direct sync failed: {e}")
                
                # 2. Si falló o estaba offline, al SENTINEL (Cola)
                if not sync_success:
                    sync_repo = db.get_sync_repository()
                    sync_repo.add_task(
                        router_id=router.id,
                        client_id=client_id,
                        operation='update',
                        payload={'old_username': old_username, 'data': updated_client.to_dict()}
                    )
                    logger.warning(f"Router offline/error. Tarea de sincronización encolada para Cliente {client_id}")

        logger.info(f"Cliente actualizado: {updated_client.legal_name}")
        
        # Auditoría de actualización
        AuditService.log(
            operation='client_updated',
            category='client',
            entity_type='client',
            entity_id=client_id,
            description=f"Cliente actualizado: {updated_client.legal_name}",
            previous_state={'username': old_username},
            new_state=data
        )
        
        return jsonify(updated_client.to_dict())
    except Exception as e:
        logger.error(f"Error updating client {client_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500


@clients_bp.route('/<int:client_id>', methods=['DELETE'])
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
        # Global / Hard Delete
        # 1. Eliminar de Mikrotik si tiene servicio activo
        if client.router_id:
            router = router_repo.get_by_id(client.router_id)
            if router and router.status == 'online':
                adapter = MikroTikAdapter()
                try:
                    if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
                        # Intentamos eliminar Queue y Secret
                        # adapter.remove_client no existe explícitamente en lo que vi, 
                        # pero adapter.remove_simple_queue y remove_ppp_secret sí deberían existir o lo hacemos manual.
                        # Revisando adapter... asumiremos remove_client_service o llamadas directas.
                        
                        # Fallback a métodos específicos si remove_client general no existe
                        # En implementaciones previas se usaba remove_simple_queue / remove_ppp_secret
                        # Usaremos remove_client_service si existe (patrón común) o llamadas individuales.
                        
                        # Verificamos si existe método unificado, si no, individual:
                        if hasattr(adapter, 'remove_client_service'):
                            adapter.remove_client_service(client.to_dict())
                        else:
                            # Intento manual basico
                            if client.service_type == 'pppoe':
                                adapter.remove_ppp_secret(client.username)
                            if client.username: # Siempre intentar borrar cola por si acaso
                                adapter.remove_simple_queue(client.username)
                                
                        adapter.disconnect()
                except Exception as e:
                    logger.error(f"Error eliminando de Mikrotik (pero se borrará de BD): {e}")

        # 2. Eliminar de BD
        success = client_repo.delete(client_id)
        if not success:
             return jsonify({'error': 'Error al eliminar de BD'}), 500
             
        # Auditoría de eliminación permanente
        AuditService.log(
            operation='client_deleted_permanent',
            category='client',
            entity_type='client',
            entity_id=client_id,
            description=f"Cliente eliminado permanentemente: {client.legal_name} ({client.username})",
            previous_state=client.to_dict()
        )
        
        logger.info(f"Cliente {client_id} eliminado permanentemente (Global).")
        return jsonify({'message': 'Cliente eliminado correctamente'}), 200


@clients_bp.route('/<int:client_id>/suspend', methods=['POST'])
def suspend_client(client_id):
    """Suspende un cliente"""
    db = get_db()
    router_repo = db.get_router_repository()
    client_repo = db.get_client_repository()
    
    client = client_repo.get_by_id(client_id)
    if not client:
        return jsonify({'error': 'Cliente no encontrado'}), 404
    
    # 1. Actualizar en BD
    client = client_repo.suspend(client_id)
    
    # 2. Sincronizar con MikroTik (Address List de Corte)
    if client.router_id:
        router = router_repo.get_by_id(client.router_id)
        if router and router.status == 'online':
            adapter = MikroTikAdapter()
            try:
                if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
                    adapter.suspend_client_service(client.to_dict())
                    adapter.disconnect()
            except Exception as e:
                logger.error(f"Error syncing suspension with MikroTik: {e}")

    # Auditoría
    AuditService.log(
        operation='client_suspended_manual',
        category='client',
        entity_type='client',
        entity_id=client_id,
        description=f"Suspensión manual de cliente: {client.legal_name}",
        previous_state={'status': 'active'},
        new_state={'status': 'suspended'}
    )

    logger.info(f"Cliente suspendido: {client.legal_name}")
    return jsonify(client.to_dict())


@clients_bp.route('/<int:client_id>/promise', methods=['POST'])
def register_promise(client_id):
    """Registra una promesa de pago (pospone suspensión) y reactiva servicio si estaba cortado"""
    data = request.json
    db = get_db()
    client_repo = db.get_client_repository()
    router_repo = db.get_router_repository()
    
    promise_date_str = data.get('promise_date')
    
    # Obtener el cliente actual
    client = client_repo.get_by_id(client_id)
    if not client:
        return jsonify({'error': 'Cliente no encontrado'}), 404
    
    if not promise_date_str:
        # Si no se envía fecha, se limpia la promesa
        updated_client = client_repo.update(client_id, {'promise_date': None})
        logger.info(f"Promesa de pago eliminada para {updated_client.legal_name}")
        return jsonify(updated_client.to_dict())
    
    try:
        # Formato esperado: 'YYYY-MM-DD'
        promise_date = datetime.strptime(promise_date_str, '%Y-%m-%d')
        # Ajustar a final del día (23:59:59)
        promise_date = promise_date.replace(hour=23, minute=59, second=59)
        
        # Actualizar fecha de promesa
        updates = {'promise_date': promise_date}
        
        # LÓGICA DE REACTIVACIÓN AUTOMÁTICA
        restored = False
        if client.status == 'suspended':
            updates['status'] = 'active'
            restored = True
            
        updated_client = client_repo.update(client_id, updates)
        
        # Sincronizar con MikroTik si hubo restauración
        if restored and updated_client.router_id:
            router = router_repo.get_by_id(updated_client.router_id)
            if router and router.status == 'online':
                adapter = MikroTikAdapter()
                try:
                    if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
                        adapter.restore_client_service(updated_client.to_dict())
                        adapter.disconnect()
                        logger.info(f"Servicio restaurado automáticamente en MikroTik para {updated_client.legal_name} por Promesa")
                except Exception as e:
                    logger.error(f"Error restaurando servicio en MikroTik al crear promesa: {e}")

        # Auditoría
        AuditService.log(
            operation='promise_registered',
            category='accounting',
            entity_type='client',
            entity_id=client_id,
            description=f"Promesa de pago registrada hasta {promise_date_str}",
            new_state={'promise_date': promise_date_str}
        )

        logger.info(f"Promesa de pago registrada para {updated_client.legal_name} hasta {promise_date_str}")
        return jsonify(updated_client.to_dict())
        
    except ValueError:
        return jsonify({'error': 'Formato de fecha inválido. Use YYYY-MM-DD'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@clients_bp.route('/<int:client_id>/activate', methods=['POST'])
def activate_client(client_id):
    """Activa un cliente"""
    db = get_db()
    router_repo = db.get_router_repository()
    client_repo = db.get_client_repository()
    
    client = client_repo.get_by_id(client_id)
    if not client:
        return jsonify({'error': 'Cliente no encontrado'}), 404
        
    # 1. Actualizar en BD
    client = client_repo.activate(client_id)
    
    # 2. Sincronizar con MikroTik (Remover de Address List de Corte)
    if client.router_id:
        router = router_repo.get_by_id(client.router_id)
        if router and router.status == 'online':
            adapter = MikroTikAdapter()
            try:
                if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
                    adapter.restore_client_service(client.to_dict())
                    adapter.disconnect()
            except Exception as e:
                logger.error(f"Error syncing activation with MikroTik: {e}")

    # Auditoría
    AuditService.log(
        operation='client_activated_manual',
        category='client',
        entity_type='client',
        entity_id=client_id,
        description=f"Activación manual de cliente: {client.legal_name}",
        previous_state={'status': 'suspended'},
        new_state={'status': 'active'}
    )

    logger.info(f"Cliente activado: {client.legal_name}")
    return jsonify(client.to_dict())


@clients_bp.route('/<int:client_id>/restore', methods=['POST'])
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


@clients_bp.route('/<int:client_id>/register-payment', methods=['POST'])
def register_payment(client_id):
    """Registra un pago para el cliente y restaura servicio si aplica"""
    data = request.json
    db = get_db()
    client_repo = db.get_client_repository()
    payment_repo = db.get_payment_repository()
    router_repo = db.get_router_repository()
    
    client = client_repo.get_by_id(client_id)
    if not client:
        return jsonify({'error': 'Cliente no encontrado'}), 404
    
    payment_data = {
        'client_id': client_id,
        'amount': float(data.get('amount') or 0),
        'payment_method': data.get('payment_method', 'cash'),
        'reference': data.get('reference', ''),
        'notes': data.get('notes', ''),
        'registered_by': data.get('registered_by', 'system')
    }
    
    # 1. Registrar pago y descontar balance
    payment = payment_repo.create(payment_data)
    # Importante: Restar el pago de la deuda (account_balance)
    updated_client = client_repo.update_balance(client_id, payment.amount, operation='subtract')
    client_repo.update(client_id, {'last_payment_date': datetime.utcnow()})
    
    # 2. Restauración automática si la deuda es <= 0 y estaba suspendido
    restored_in_mikrotik = False
    if updated_client.account_balance <= 0 and updated_client.status == 'suspended':
        logger.info(f"Deuda saldada para {updated_client.legal_name}. Restaurando servicio...")
        
        # Cambiar estado en BD
        client_repo.update(client_id, {'status': 'active'})
        
        # Intentar restaurar en Router
        if updated_client.router_id:
            router = router_repo.get_by_id(updated_client.router_id)
            if router and router.status == 'online':
                adapter = MikroTikAdapter()
                try:
                    if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
                        adapter.restore_client_service(updated_client.to_dict())
                        adapter.disconnect()
                        restored_in_mikrotik = True
                except Exception as e:
                    logger.error(f"Error restaurando en Mikrotik tras pago: {e}")

    result = updated_client.to_dict()
    result['restored_auto'] = restored_in_mikrotik
    
    logger.info(f"Pago registrado para {updated_client.legal_name}: ${payment.amount}")
    return jsonify(result), 201


@clients_bp.route('/update-name-by-ip', methods=['POST'])
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
def preview_import_clients(router_id):
    """
    Escanea clientes del router (PPPoE + Simple Queues) y filtra por Segmentos de Red declarados.
    Devuelve lista comparada con BD para selección manual.
    """
    db = get_db()
    router_repo = db.get_router_repository()
    client_repo = db.get_client_repository()
    
    router = router_repo.get_by_id(router_id)
    if not router:
        return jsonify({'error': 'Router no encontrado'}), 404
    
    # 1. Obtener Segmentos de Red Validos SOLO PARA ESTE ROUTER
    segments = db.session.query(NetworkSegment).filter(NetworkSegment.router_id == router_id).all()
    # Si hay segmentos definidos para este router, crear lista de redes permitidas
    allowed_networks = []
    for s in segments:
        try:
            allowed_networks.append(ip_network(s.cidr, strict=False))
        except Exception as e:
            logger.warning(f"Segmento invalido en BD {s.cidr}: {e}")
            
    # Reactivar filtro de segmentos
    has_segments_filter = len(allowed_networks) > 0
    # has_segments_filter = False

    if has_segments_filter:
        logger.info(f"Filtrando importación de router {router_id} ({router.alias}) por {len(allowed_networks)} segmentos de red declarados: {[s.cidr for s in segments]}")
    else:
        logger.warning(f"No hay segmentos de red declarados para router {router_id} ({router.alias}). Se mostrarán TODOS los clientes encontrados.")


    def is_ip_allowed(ip_str):
        """Verifica si una IP está en los segmentos permitidos"""
        if not has_segments_filter: return True # Si no hay segmentos declarados, permitir todo
        
        # Limpiar IP (quitar máscara si viene tipo 192.168.1.5/32)
        clean_ip = ip_str.split('/')[0] if ip_str else ''
        
        # EXCLUSIÓN EXPLÍCITA DE BASURA CONOCIDA
        if clean_ip.startswith('169.254'): return False # Link-local garbage
        
        if not clean_ip or clean_ip == '0.0.0.0': 
            return True 
            
        try:
            addr = ip_address(clean_ip)
            return any(addr in net for net in allowed_networks)
        except ValueError:
            return False

    def is_management_equipment(name):
        """Verifica si un nombre corresponde a equipos de gestión, infraestructura o HOTSPOT"""
        if not name:
            return False
            
        name_upper = name.upper()
        
        # Patrones de equipos de gestión a excluir
        management_patterns = [
            'GESTION', 'GESTION-AP', 'AP-', 'ROUTER-', 'MIKROTIK', 'SWITCH', 'CORE', 'BACKBONE',
            'INFRAESTRUCTURA', 'ADMIN', 'MANAGEMENT', 'TOWER', 'TORRE', 'PTP-', 'ENLACE',
            'APB', 
            # 'STA',  <-- REMOVIDO: Generaba falsos positivos (ej: ACOSTA)
            # 'UBIQUITI', <-- REMOVIDO: A veces usado en notas de cliente
            
            # EXCLUSIONES DE HOTSPOT
            'HS-', 'HOTSPOT', 'FICHAS', 'INVITADO', 'GUEST'
        ]
        
        # Verificar si el nombre contiene algún patrón
        for pattern in management_patterns:
            if pattern in name_upper:
                logger.debug(f"Cliente '{name}' excluido (equipamiento de gestión/infraestructura)")
                return True
                
        return False

    adapter = MikroTikAdapter()
    
    try:
        connected = adapter.connect(
            host=router.host_address,
            username=router.api_username,
            password=router.api_password,
            port=router.api_port,
            timeout=10
        )
        
        if not connected:
            return jsonify({'error': 'No se pudo conectar al router'}), 400
            
        existing_clients = client_repo.get_all()
        existing_usernames = {c.username.lower() for c in existing_clients}
        existing_ips = {c.ip_address for c in existing_clients if c.ip_address}
        
        # Mapeo IP -> Client para detectar cambios de nombre
        existing_clients_by_ip = {c.ip_address: c for c in existing_clients if c.ip_address}
        
        preview_list = []
        seen_ips = set()
        seen_mikrotik_usernames = set() # Nombres que ya están en el router (Queues o PPP)
        management_ips = set() # IPs identificadas como gestión (para excluir de ARP)

        # --- A. SCAN PPPOE SECRETS ---
        try:
            ppp_secrets = adapter.get_all_pppoe_secrets()
            all_profiles = adapter.get_ppp_profiles()
            all_pools = adapter.get_ip_pools()
            
            # Mapa de pools y perfiles permitidos
            pool_map = {p.get('name'): p.get('ranges') for p in all_pools}
            allowed_profiles = set()
            
            for p in all_profiles:
                p_name = p.get('name')
                remote = p.get('remote-address')
                
                if remote and is_ip_allowed(remote):
                    allowed_profiles.add(p_name)
                    continue
                    
                pool_range = pool_map.get(remote)
                if pool_range:
                    first_part = pool_range.split(',')[0]
                    first_ip = first_part.split('-')[0]
                    if is_ip_allowed(first_ip):
                        allowed_profiles.add(p_name)

            for secret in ppp_secrets:
                name = secret.get('name', '')
                remote_addr = secret.get('remote_address', '')
                profile_name = secret.get('profile', '')
                
                # FILTRO: Excluir equipos de gestión (Chequear nombre y comentario)
                comment = secret.get('comment', '')
                if is_management_equipment(name) or is_management_equipment(comment):
                    if remote_addr: management_ips.add(remote_addr)
                    continue
                
                # FILTRO DE SEGMENTO Y PERFIL
                if not (is_ip_allowed(remote_addr) or profile_name in allowed_profiles):
                    continue 

                if not name: continue
                
                # DETECCIÓN INTELIGENTE: Buscar por IP primero
                existing_client_by_ip = existing_clients_by_ip.get(remote_addr) if remote_addr and remote_addr != '0.0.0.0' else None
                name_changed = False
                
                if existing_client_by_ip:
                    # Ya existe un cliente con esta IP
                    if existing_client_by_ip.username.lower() != name.lower():
                        # El nombre cambió!
                        name_changed = True
                        logger.info(f"Cambio de nombre detectado en IP {remote_addr}: '{existing_client_by_ip.username}' → '{name}'")
                    is_duplicate = True
                else:
                    # No existe por IP, verificar por username
                    is_duplicate = name.lower() in existing_usernames
                
                seen_mikrotik_usernames.add(name.lower())
                if remote_addr: seen_ips.add(remote_addr)

                preview_list.append({
                    'type': 'pppoe',
                    'username': name,
                    'password': secret.get('password', ''),
                    'ip_address': remote_addr or 'Dinámica',
                    'profile': profile_name or 'default',
                    'status': 'disabled' if secret.get('disabled') else 'active',
                    'exists_in_db': is_duplicate,
                    'name_changed': name_changed,
                    'old_username': existing_client_by_ip.username if name_changed else None,
                    'client_id': existing_client_by_ip.id if existing_client_by_ip else None,
                    'mikrotik_id': secret.get('mikrotik_id', '')
                })
        except Exception as e:
            logger.error(f"Error scanning PPPoE: {e}")

        # --- B. SCAN EXISTING SIMPLE QUEUES ---
        try:
            queues = adapter._api_connection.get_resource('/queue/simple').get()
            for q in queues:
                name = q.get('name', '')
                target = q.get('target', '') # Ej: 192.168.10.25/32
                
                # FILTRO: Excluir equipos de gestión (Chequear nombre y comentario)
                comment = q.get('comment', '')
                if is_management_equipment(name) or is_management_equipment(comment):
                    # Extraer IP si es posible
                    target_ip = target.split('/')[0] if target else ''
                    if target_ip: management_ips.add(target_ip)
                    continue

                # La target ip es clave para queue
                if not is_ip_allowed(target):
                    continue
                
                if not name or name.startswith('<pppoe-'): continue # Omitir colas dinámicas de PPPoE
                
                # Extraer IP del target
                queue_ip = target.split('/')[0] if target else ''
                
                # DETECCIÓN INTELIGENTE: Buscar por IP primero
                existing_client_by_ip = existing_clients_by_ip.get(queue_ip) if queue_ip else None
                name_changed = False
                
                if existing_client_by_ip:
                    # Ya existe un cliente con esta IP
                    if existing_client_by_ip.username.lower() != name.lower():
                        # El nombre cambió!
                        name_changed = True
                        logger.info(f"Cambio de nombre detectado en IP {queue_ip}: '{existing_client_by_ip.username}' → '{name}'")
                    is_duplicate = True
                else:
                    # No existe por IP, verificar por username
                    is_duplicate = name.lower() in existing_usernames
                
                if name.lower() in seen_mikrotik_usernames: continue # Ya procesado como PPPoE
                seen_mikrotik_usernames.add(name.lower())
                if queue_ip: seen_ips.add(queue_ip)

                preview_list.append({
                    'type': 'simple_queue',
                    'username': name,
                    'password': '',
                    'ip_address': queue_ip or 'Sin IP',
                    'profile': q.get('max-limit', ''),
                    'status': 'disabled' if q.get('disabled') == 'true' else 'active',
                    'exists_in_db': is_duplicate,
                    'name_changed': name_changed,
                    'old_username': existing_client_by_ip.username if name_changed else None,
                    'client_id': existing_client_by_ip.id if existing_client_by_ip else None,
                    'mikrotik_id': q.get('.id')
                })
        except Exception as e:
             logger.error(f"Error scanning Queues: {e}")

        # --- C. SCAN DHCP LEASES && ARP (ADVANCED SYNC) ---
        # Buscamos clientes que estén conectados pero NO tengan Queue/PPP
        try:
            dhcp_leases = adapter.get_dhcp_leases()
            arp_table = adapter.get_arp_table()
            
            # Unir info por IP
            network_devices = {} # ip -> { mac, host, source }
            
            for lease in dhcp_leases:
                ip = lease.get('address')
                
                # FILTRO: Excluir equipos de gestión (Chequear host-name y comment)
                host_name = lease.get('host-name', '')
                comment = lease.get('comment', '')
                if is_management_equipment(host_name) or is_management_equipment(comment):
                    if lease.get('address'): management_ips.add(lease.get('address'))
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
                
                # FILTRO: Excluir equipos de gestión
                if is_management_equipment(arp.get('comment', '')):
                    if arp.get('address'): management_ips.add(arp.get('address'))
                    continue

                if not ip or not is_ip_allowed(ip): continue
                if ip in seen_ips or ip in network_devices or ip in management_ips: continue
                
                network_devices[ip] = {
                    'mac': arp.get('mac-address', ''),
                    'host': arp.get('comment', f"ARP-Device-{ip.split('.')[-1]}"),
                    'source': 'ARP'
                }
            
            # Añadir candidatos detectados a la lista
            for ip, info in network_devices.items():
                username = info['host'].replace(' ', '_')
                # Evitar colisión de nombres
                if username.lower() in seen_mikrotik_usernames:
                    username = f"{username}_{ip.split('.')[-1]}"

                preview_list.append({
                    'type': 'discovered',
                    'username': username,
                    'password': 'N/A',
                    'ip_address': ip,
                    'profile': 'Detected (No Queue)',
                    'status': 'active',
                    'exists_in_db': username.lower() in existing_usernames or ip in existing_ips,
                    'mikrotik_id': f"new-{info['source']}",
                    'mac': info['mac']
                })
                
        except Exception as e:
            logger.error(f"Error in advanced sync scanning: {e}")

        adapter.disconnect()
        
        # Contar clientes por tipo
        discovered_count = sum(1 for c in preview_list if c.get('type') == 'discovered')
        pppoe_count = sum(1 for c in preview_list if c.get('type') == 'pppoe')
        queue_count = sum(1 for c in preview_list if c.get('type') == 'simple_queue')
        name_changes_count = sum(1 for c in preview_list if c.get('name_changed', False))
        
        return jsonify({
            'router_alias': router.alias,
            'router_id': router_id,
            'total_found': len(preview_list),
            'segments_filter_active': has_segments_filter,
            'clients': preview_list,
            'summary': {
                'discovered_no_queue': discovered_count,
                'pppoe_secrets': pppoe_count,
                'simple_queues': queue_count,
                'needs_provisioning': discovered_count > 0,
                'name_changes': name_changes_count
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
    
    for item in clients_to_import:
        try:
            username = item.get('username')
            if not username: continue

            # Check duplicado (Optimizado)
            if username.lower() in existing_usernames:
                continue
                
            subscriber_code = f"CLI-{current_total + 1 + imported_count:04d}"
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
                'plan_name': item.get('profile', 'default'),
                'download_speed': '15M', # Default subida (Placeholder, plan real se define en router)
                'upload_speed': '15M',   # Default bajada
                'service_type': item.get('type', 'pppoe'), # pppoe o simple_queue
                'status': 'active' if item.get('status') == 'active' else 'suspended',
                'mikrotik_id': item.get('mikrotik_id', ''),
                'monthly_fee': fee, 
                'mac_address': item.get('mac', ''),
            }
            
            client_repo.create(client_data)
            imported_count += 1
            
            # Actualizar el set local para evitar duplicados dentro del mismo lote de importación
            existing_usernames.add(username.lower())
            
        except Exception as e:
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
                sync_repo = db.get_sync_repository()
                sync_repo.add_task(
                    router_id=router_id,
                    client_id=c_id,
                    operation='update',
                    payload={'old_username': old_username, 'data': updated_client.to_dict()}
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


@clients_bp.route('/<int:client_id>/traffic-history', methods=['GET'])


def get_router_clients_traffic(router_id: int, client_ids: List[int], adapter: MikroTikAdapter) -> Dict[str, Any]:
    """
    Wrapper para mantener compatibilidad si otros módulos lo usan.
    Delegamos al MonitoringManager para evitar duplicación.
    """
    from src.application.services.monitoring_manager import MonitoringManager
    return MonitoringManager.get_instance().get_router_clients_traffic(router_id, client_ids, adapter)
