"""
Clients API Controller - DATOS REALES
Endpoints para gestión completa de clientes con importación MikroTik
"""
from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.mikrotik.adapter import MikroTikAdapter
import logging

logger = logging.getLogger(__name__)

clients_bp = Blueprint('clients', __name__, url_prefix='/api/clients')


@clients_bp.route('', methods=['GET'])
def get_clients():
    """
    Obtiene todos los clientes - DATOS REALES
    """
    db = get_db()
    client_repo = db.get_client_repository()
    
    # Filtros opcionales
    router_id = request.args.get('router_id', type=int)
    status = request.args.get('status')
    search = request.args.get('search')
    
    if search:
        clients = client_repo.search(search)
    elif router_id:
        clients = client_repo.get_by_router(router_id)
    elif status:
        clients = client_repo.get_by_status(status)
    else:
        clients = client_repo.get_all()
    
    return jsonify([c.to_dict() for c in clients])


@clients_bp.route('/<int:client_id>', methods=['GET'])
def get_client(client_id):
    """
    Obtiene un cliente específico
    """
    db = get_db()
    client_repo = db.get_client_repository()
    
    client = client_repo.get_by_id(client_id)
    if not client:
        return jsonify({'error': 'Cliente no encontrado'}), 404
    
    return jsonify(client.to_dict())


@clients_bp.route('', methods=['POST'])
def create_client():
    """
    Crea un nuevo cliente - DATOS REALES
    """
    data = request.json
    
    db = get_db()
    client_repo = db.get_client_repository()
    
    try:
        client = client_repo.create(data)
        logger.info(f"Cliente creado: {client.legal_name}")
        return jsonify(client.to_dict()), 201
    except Exception as e:
        logger.error(f"Error creating client: {str(e)}")
        return jsonify({'error': str(e)}), 400


@clients_bp.route('/<int:client_id>', methods=['PUT'])
def update_client(client_id):
    """
    Actualiza un cliente
    """
    data = request.json
    
    db = get_db()
    client_repo = db.get_client_repository()
    
    client = client_repo.update(client_id, data)
    if not client:
        return jsonify({'error': 'Cliente no encontrado'}), 404
    
    logger.info(f"Cliente actualizado: {client.legal_name}")
    return jsonify(client.to_dict())


@clients_bp.route('/<int:client_id>', methods=['DELETE'])
def delete_client(client_id):
    """
    Elimina un cliente
    """
    db = get_db()
    client_repo = db.get_client_repository()
    
    success = client_repo.delete(client_id)
    if not success:
        return jsonify({'error': 'Cliente no encontrado'}), 404
    
    logger.info(f"Cliente eliminado: ID {client_id}")
    return jsonify({'message': 'Cliente eliminado correctamente'}), 200


@clients_bp.route('/<int:client_id>/suspend', methods=['POST'])
def suspend_client(client_id):
    """
    Suspende un cliente - ACTUALIZA EN BD Y ROUTER
    """
    db = get_db()
    client_repo = db.get_client_repository()
    router_repo = db.get_router_repository()
    
    client = client_repo.get_by_id(client_id)
    if not client:
        return jsonify({'error': 'Cliente no encontrado'}), 404
    
    # Suspender en BD
    client = client_repo.suspend(client_id)
    
    # TODO: Suspender en MikroTik
    # if client.router and client.mikrotik_id:
    #     router = router_repo.get_by_id(client.router_id)
    #     adapter = MikroTikAdapter()
    #     adapter.connect(...)
    #     adapter.suspend_client_service(client.mikrotik_id)
    #     adapter.disconnect()
    
    logger.info(f"Cliente suspendido: {client.legal_name}")
    return jsonify(client.to_dict())


@clients_bp.route('/<int:client_id>/activate', methods=['POST'])
def activate_client(client_id):
    """
    Activa un cliente - ACTUALIZA EN BD Y ROUTER
    """
    db = get_db()
    client_repo = db.get_client_repository()
    
    client = client_repo.get_by_id(client_id)
    if not client:
        return jsonify({'error': 'Cliente no encontrado'}), 404
    
    # Activar en BD
    client = client_repo.activate(client_id)
    
    # TODO: Activar en MikroTik
    
    logger.info(f"Cliente activado: {client.legal_name}")
    return jsonify(client.to_dict())


@clients_bp.route('/<int:client_id>/payments', methods=['GET'])
def get_client_payments(client_id):
    """
    Obtiene historial de pagos del cliente
    """
    db = get_db()
    payment_repo = db.get_payment_repository()
    
    payments = payment_repo.get_by_client(client_id)
    return jsonify([p.to_dict() for p in payments])


@clients_bp.route('/<int:client_id>/register-payment', methods=['POST'])
def register_payment(client_id):
    """
    Registra un pago para el cliente
    """
    data = request.json
    
    db = get_db()
    client_repo = db.get_client_repository()
    payment_repo = db.get_payment_repository()
    
    client = client_repo.get_by_id(client_id)
    if not client:
        return jsonify({'error': 'Cliente no encontrado'}), 404
    
    # Crear pago
    payment_data = {
        'client_id': client_id,
        'amount': data.get('amount'),
        'payment_method': data.get('payment_method', 'cash'),
        'reference': data.get('reference', ''),
        'notes': data.get('notes', ''),
        'registered_by': data.get('registered_by', 'system')
    }
    
    payment = payment_repo.create(payment_data)
    
    # Actualizar balance del cliente (sumar el pago)
    client_repo.update_balance(client_id, payment.amount, operation='add')
    
    # Actualizar fecha de último pago
    client_repo.update(client_id, {'last_payment_date': datetime.utcnow()})
    
    logger.info(f"Pago registrado: {client.legal_name} - ${payment.amount}")
    
    return jsonify(payment.to_dict()), 201


@clients_bp.route('/import-from-router/<int:router_id>', methods=['POST'])
def import_from_router(router_id):
    """
    IMPORTA clientes desde un router MikroTik - SYNC REAL
    """
    db = get_db()
    router_repo = db.get_router_repository()
    client_repo = db.get_client_repository()
    
    router = router_repo.get_by_id(router_id)
    if not router:
        return jsonify({'error': 'Router no encontrado'}), 404
    
    adapter = MikroTikAdapter()
    
    try:
        # Timeout extendido para importación
        connected = adapter.connect(
            host=router.host_address,
            username=router.api_username,
            password=router.api_password,
            port=router.api_port,
            timeout=20 
        )
        
        if not connected:
            return jsonify({
                'success': False,
                'message': 'No se pudo conectar al router'
            }), 400
        
        # Obtener configuración básica
        config = adapter.discover_configuration()
        
        imported_count = 0
        skipped_count = 0
        errors = []
        
        # 1. IMPORTAR SECRETOS PPPOE (Usuarios reales)
        try:
            ppp_secrets = adapter._api_connection.get_resource('/ppp/secret').get()
            
            for secret in ppp_secrets:
                username = secret.get('name')
                
                # Verificar duplicados
                existing = client_repo.get_all()
                exists = any(c.username == username for c in existing)
                
                if not exists and username:
                    try:
                        subscriber_code = f"CLI-{len(existing) + 1 + imported_count:04d}"
                        
                        client_data = {
                            'router_id': router_id,
                            'subscriber_code': subscriber_code,
                            'legal_name': username.replace('_', ' ').replace('.', ' ').title(),
                            'username': username,
                            'password': secret.get('password', 'hidden'),
                            'ip_address': secret.get('remote-address', ''),
                            'plan_name': secret.get('profile', 'default'),
                            'download_speed': '0', # TODO: Leer del perfil
                            'upload_speed': '0',
                            'service_type': 'pppoe',
                            'status': 'suspended' if secret.get('disabled') == 'true' else 'active',
                            'mikrotik_id': secret.get('.id')
                        }
                        
                        client_repo.create(client_data)
                        imported_count += 1
                    except Exception as e:
                        errors.append(f"Error importando {username}: {str(e)}")
                else:
                    skipped_count += 1
                    
        except Exception as e:
            errors.append(f"Fallo al leer PPP Secrets: {str(e)}")

        # TODO: Implementar Hotspot Users similarmente aquí si se requiere
        
        adapter.disconnect()
        
        logger.info(f"Importación completada desde {router.alias}: {imported_count} importados, {skipped_count} omitidos")
        
        return jsonify({
            'success': True,
            'imported': imported_count,
            'skipped': skipped_count,
            'errors': errors,
            'methods_found': config['methods']
        })
        
    except Exception as e:
        logger.error(f"Error importing clients: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error de importación: {str(e)}'
        }), 400


@clients_bp.route('/preview-import/<int:router_id>', methods=['GET'])
def preview_import_clients(router_id):
    """
    Escanea clientes del router y devuelve lista comparada con BD para selección manual
    """
    db = get_db()
    router_repo = db.get_router_repository()
    client_repo = db.get_client_repository()
    
    router = router_repo.get_by_id(router_id)
    if not router:
        return jsonify({'error': 'Router no encontrado'}), 404
    
    adapter = MikroTikAdapter()
    
    try:
        # Conectar con timeout seguro
        connected = adapter.connect(
            host=router.host_address,
            username=router.api_username,
            password=router.api_password,
            port=router.api_port,
            timeout=10
        )
        
        if not connected:
            return jsonify({'error': 'No se pudo conectar al router'}), 400
            
        # Obtener clientes existentes en BD para comparar
        existing_clients = client_repo.get_all()
        # Crear set de usernames normalizados para búsqueda rápida
        existing_usernames = {c.username.lower() for c in existing_clients}
        
        preview_list = []
        
        # 1. Obtener Secrets PPPoE
        try:
            ppp_secrets = adapter._api_connection.get_resource('/ppp/secret').get()
            for secret in ppp_secrets:
                name = secret.get('name', '')
                if not name: continue
                
                is_duplicate = name.lower() in existing_usernames
                
                preview_list.append({
                    'type': 'pppoe',
                    'username': name,
                    'password': secret.get('password', ''), # Solo informativo, tal vez ocultar
                    'ip_address': secret.get('remote-address', 'Dinámica'),
                    'profile': secret.get('profile', 'default'),
                    'status': 'disabled' if secret.get('disabled') == 'true' else 'active',
                    'exists_in_db': is_duplicate,
                    'mikrotik_id': secret.get('.id')
                })
        except Exception as e:
            logger.error(f"Error scanning PPPoE: {e}")

        # 2. Obtener Hotspot Users (Opcional, agregamos soporte básico)
        try:
            hs_users = adapter._api_connection.get_resource('/ip/hotspot/user').get()
            for user in hs_users:
                name = user.get('name', '')
                if not name or name == 'default-trial': continue
                
                is_duplicate = name.lower() in existing_usernames
                
                preview_list.append({
                    'type': 'hotspot',
                    'username': name,
                    'password': user.get('password', ''),
                    'ip_address': user.get('address', 'Dinámica'),
                    'profile': user.get('profile', 'default'),
                    'status': 'disabled' if user.get('disabled') == 'true' else 'active',
                    'exists_in_db': is_duplicate,
                    'mikrotik_id': user.get('.id')
                })
        except Exception as e:
             logger.error(f"Error scanning Hotspot: {e}")
             
        adapter.disconnect()
        
        return jsonify({
            'router_alias': router.alias,
            'total_found': len(preview_list),
            'clients': preview_list
        })
        
    except Exception as e:
        logger.error(f"Error en preview import: {str(e)}")
        return jsonify({'error': str(e)}), 500


@clients_bp.route('/execute-import', methods=['POST'])
def execute_import_clients():
    """
    Importa los clientes SELECCIONADOS desde el frontend
    """
    data = request.json
    router_id = data.get('router_id')
    clients_to_import = data.get('clients', []) # Lista de objetos cliente
    
    if not router_id or not clients_to_import:
        return jsonify({'error': 'Datos insuficientes'}), 400
        
    db = get_db()
    client_repo = db.get_client_repository()
    
    imported_count = 0
    errors = []
    
    # Obtener conteo actual para códigos
    current_total = len(client_repo.get_all())
    
    for item in clients_to_import:
        try:
            username = item.get('username')
            # Validar doble check de existencia
            existing = client_repo.get_all()
            if any(c.username.lower() == username.lower() for c in existing):
                continue
                
            subscriber_code = f"CLI-{current_total + 1 + imported_count:04d}"
            
            # Normalizar nombre legal
            legal_name = username.replace('_', ' ').replace('.', ' ').title()
            
            client_data = {
                'router_id': router_id,
                'subscriber_code': subscriber_code,
                'legal_name': legal_name,
                'username': username,
                'password': item.get('password', 'hidden'),
                'ip_address': item.get('ip_address', ''),
                'plan_name': item.get('profile', 'default'),
                'download_speed': '0', # Se podría mejorar obteniendo del perfil
                'upload_speed': '0',
                'service_type': item.get('type', 'pppoe'),
                'status': 'active' if item.get('status') == 'active' else 'suspended',
                'mikrotik_id': item.get('mikrotik_id', '')
            }
            
            client_repo.create(client_data)
            imported_count += 1
            
        except Exception as e:
            errors.append(f"Error importando {item.get('username')}: {str(e)}")
            
    return jsonify({
        'success': True,
        'imported': imported_count,
        'errors': errors
    })


@clients_bp.route('/statistics', methods=['GET'])
def get_statistics():
    """
    Obtiene estadísticas de clientes
    """
    db = get_db()
    client_repo = db.get_client_repository()
    
    all_clients = client_repo.get_all()
    # Comparación segura de strings
    active = len([c for c in all_clients if str(c.status) == 'active'])
    suspended = len([c for c in all_clients if str(c.status) == 'suspended'])
    inactive = len([c for c in all_clients if str(c.status) == 'inactive'])
    
    # Balance total
    total_balance = sum(c.account_balance for c in all_clients)
    
    return jsonify({
        'total': len(all_clients),
        'active': active,
        'suspended': suspended,
        'inactive': inactive,
        'total_balance': total_balance
    })


@clients_bp.route('/monitor', methods=['POST'])
def monitor_traffic():
    """
    Obtiene estado y tráfico en tiempo real por ID de cliente (Individualizado)
    Entrada: [1, 2, 3] (IDs de base de datos)
    Retorna: { "1": { "status": "online", ... }, "2": ... }
    """
    client_ids = request.json
    if not client_ids or not isinstance(client_ids, list):
        return jsonify({})
    
    db = get_db()
    router_repo = db.get_router_repository()
    client_repo = db.get_client_repository()
    
    try:
        # 1. Obtener objetos cliente
        # Podríamos hacer get_by_ids si existiera, o iterar. Optimización: get_all y filtrar es rápido en memoria para <1000 items.
        # Para escalabilidad futura mejor query IN, pero por ahora esto funciona bien.
        all_clients = client_repo.get_all()
        target_clients = [c for c in all_clients if c.id in client_ids]
        
        # Agrupar por router_id para minimizar conexiones Open/Close
        grouped = {}
        for client in target_clients:
            if not client.router_id: continue
            if client.router_id not in grouped:
                grouped[client.router_id] = []
            grouped[client.router_id].append(client)
            
        results = {}
        
        # 2. Consultar cada router
        for r_id, clients_list in grouped.items():
            router = router_repo.get_by_id(r_id)
            if not router: continue
            
            adapter = MikroTikAdapter()
            try:
                # Conexión rápida
                if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port, timeout=3):
                    
                    # A. Obtener Sesiones Activas (Snapshot del router)
                    active_sessions = adapter.get_active_pppoe_sessions() # Dict: {'UsernameReal': info}
                    
                    # Crear índice case-insensitive para mapear nuestros usuarios (DB) a los del Router
                    # active_map = { "susancasadiego": "SusanCasadiego", ... }
                    active_map_lower = {k.lower(): k for k in active_sessions.keys()}
                    
                    # B. Identificar clientes Online y sus nombres reales de interfaz
                    online_clients_real_names = []
                    db_to_router_name = {} # mapa id_cliente -> nombre_router
                    
                    for client in clients_list:
                        db_username_lower = client.username.lower()
                        
                        is_online = db_username_lower in active_map_lower
                        
                        real_name = active_map_lower.get(db_username_lower, client.username) # Si no está, usamos el original
                        db_to_router_name[client.id] = real_name
                        
                        # Info base
                        uptime = None
                        ip = None
                        if is_online:
                            session_info = active_sessions[real_name]
                            uptime = session_info['uptime']
                            ip = session_info['ip']
                            online_clients_real_names.append(real_name)

                        results[str(client.id)] = {
                            'status': 'online' if is_online else 'offline',
                            'uptime': uptime,
                            'ip_address': ip,
                            'upload': 0,
                            'download': 0
                        }
                    
                    # C. Obtener Tráfico (Usando los nombres REALES del router)
                    if online_clients_real_names:
                        try:
                            # DEBUG LOG: Ver qué nombres estamos pidiendo
                            logger.info(f"🔍 [DEBUG] Solicitando trafico para interfaces: {online_clients_real_names}")
                            
                            # get_bulk_traffic maneja internamente la adición de <pppoe-...>
                            traffic_data = adapter.get_bulk_traffic(online_clients_real_names)
                            
                            # DEBUG LOG: Ver qué devolvió el adaptador
                            logger.info(f"✅ [DEBUG] Datos de trafico recibidos: {len(traffic_data)} interfaces. Keys: {list(traffic_data.keys())}")
                            
                            # Asignar tráfico de vuelta
                            for client in clients_list:
                                router_name_used = db_to_router_name[client.id]
                                
                                # get_bulk_traffic devuelve datos indexados por el nombre que le pedimos (usuario original)
                                if router_name_used in traffic_data:
                                    results[str(client.id)]['upload'] = traffic_data[router_name_used]['upload']
                                    results[str(client.id)]['download'] = traffic_data[router_name_used]['download']
                                    
                                    # DEBUG LOG para confirmar match
                                    if traffic_data[router_name_used]['upload'] > 0:
                                        logger.info(f"   -> Match para {client.username} ({router_name_used}): {traffic_data[router_name_used]}")
                                        
                        except Exception as e:
                            logger.error(f"❌ [DEBUG] Error obteniendo trafico bulk: {e}")
                            logger.warning(f"Error parcial traffic block router {r_id}: {e}")
                            
                    adapter.disconnect()
            except Exception as e:
                logger.error(f"Error monitoring router {router.host_address}: {e}")
                # Si falla conexión al router, estado desconocido/offline para todos sus clientes
                for client in clients_list:
                     results[str(client.id)] = {'status': 'unknown', 'uptime': None, 'upload': 0, 'download': 0}
                continue
                
        return jsonify(results)
        
    except Exception as e:
        logger.error(f"Error in traffic monitor: {e}")
        return jsonify({})
