"""
Clients API Controller - DATOS REALES
Endpoints para gestión completa de clientes con importación MikroTik y filtrado por Segmentos
"""
from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import NetworkSegment
from src.infrastructure.mikrotik.adapter import MikroTikAdapter
from ipaddress import ip_network, ip_address
import logging

logger = logging.getLogger(__name__)

clients_bp = Blueprint('clients', __name__, url_prefix='/api/clients')


@clients_bp.route('', methods=['GET'])
def get_clients():
    """Obtiene todos los clientes"""
    db = get_db()
    client_repo = db.get_client_repository()
    
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
    try:
        client = client_repo.create(data)
        logger.info(f"Cliente creado: {client.legal_name}")
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
    
    # Actualizar en Base de Datos
    updated_client = client_repo.update(client_id, data)
    
    # SINCRONIZACIÓN CON MIKROTIK
    # Solo si el nombre (username) o el nombre legal cambiaron, o si se pide explícitamente
    if router_id:
        router = router_repo.get_by_id(router_id)
        if router and router.status == 'online':
            adapter = MikroTikAdapter()
            try:
                if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
                    # Pasamos el username antiguo para buscarlo en el router, y los datos nuevos para actualizar
                    sync_data = updated_client.to_dict()
                    adapter.update_client_service(old_username, sync_data)
                    adapter.disconnect()
            except Exception as e:
                logger.error(f"Error syncing update with MikroTik: {e}")

    logger.info(f"Cliente actualizado: {updated_client.legal_name}")
    return jsonify(updated_client.to_dict())


@clients_bp.route('/<int:client_id>', methods=['DELETE'])
def delete_client(client_id):
    """Elimina un cliente"""
    db = get_db()
    client_repo = db.get_client_repository()
    success = client_repo.delete(client_id)
    if not success:
        return jsonify({'error': 'Cliente no encontrado'}), 404
    logger.info(f"Cliente eliminado: ID {client_id}")
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

    logger.info(f"Cliente suspendido: {client.legal_name}")
    return jsonify(client.to_dict())


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

    logger.info(f"Cliente activado: {client.legal_name}")
    return jsonify(client.to_dict())


@clients_bp.route('/<int:client_id>/register-payment', methods=['POST'])
def register_payment(client_id):
    """Registra un pago para el cliente"""
    data = request.json
    db = get_db()
    client_repo = db.get_client_repository()
    payment_repo = db.get_payment_repository()
    
    client = client_repo.get_by_id(client_id)
    if not client:
        return jsonify({'error': 'Cliente no encontrado'}), 404
    
    payment_data = {
        'client_id': client_id,
        'amount': data.get('amount'),
        'payment_method': data.get('payment_method', 'cash'),
        'reference': data.get('reference', ''),
        'notes': data.get('notes', ''),
        'registered_by': data.get('registered_by', 'system')
    }
    
    payment = payment_repo.create(payment_data)
    client_repo.update_balance(client_id, payment.amount, operation='add')
    client_repo.update(client_id, {'last_payment_date': datetime.utcnow()})
    
    return jsonify(payment.to_dict()), 201


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
    
    logger.info(f"Nombre actualizado automáticamente por IP {ip_address}: '{old_username}' → '{new_username}'")
    
    return jsonify({
        'success': True,
        'client_id': client.id,
        'old_username': old_username,
        'new_username': new_username,
        'ip_address': ip_address
    })


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
            
    has_segments_filter = len(allowed_networks) > 0
    if has_segments_filter:
        logger.info(f"Filtrando importación de router {router_id} ({router.alias}) por {len(allowed_networks)} segmentos de red declarados: {[s.cidr for s in segments]}")
    else:
        logger.warning(f"No hay segmentos de red declarados para router {router_id} ({router.alias}). Se mostrarán TODOS los clientes encontrados.")


    def is_ip_allowed(ip_str):
        """Verifica si una IP está en los segmentos permitidos"""
        if not has_segments_filter: return True # Si no hay segmentos declarados, permitir todo
        
        # Limpiar IP (quitar máscara si viene tipo 192.168.1.5/32)
        clean_ip = ip_str.split('/')[0] if ip_str else ''
        if not clean_ip or clean_ip == '0.0.0.0': 
            return True # IPs dinámicas o vacías se permiten (se asignarán después)
            
        try:
            addr = ip_address(clean_ip)
            # Check si pertenece a al menos una red permitida
            return any(addr in net for net in allowed_networks)
        except ValueError:
            return False # No es una IP válida

    def is_management_equipment(name):
        """Verifica si un nombre corresponde a equipos de gestión/infraestructura"""
        if not name:
            return False
            
        name_upper = name.upper()
        
        # Patrones de equipos de gestión a excluir
        management_patterns = [
            'GESTION',
            'GESTION-AP',
            'AP-',
            'ROUTER-',
            'MIKROTIK',
            'SWITCH',
            'CORE',
            'BACKBONE',
            'INFRAESTRUCTURA',
            'ADMIN',
            'MANAGEMENT',
            'UBIQUITI',
            'TOWER',
            'TORRE',
            'PTP',
            'ENLACE'
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

        # --- A. SCAN PPPOE SECRETS ---
        try:
            ppp_secrets = adapter._api_connection.get_resource('/ppp/secret').get()
            for secret in ppp_secrets:
                name = secret.get('name', '')
                remote_addr = secret.get('remote-address', '')
                
                # FILTRO: Excluir equipos de gestión
                if is_management_equipment(name):
                    continue
                
                # FILTRO DE SEGMENTO
                if not is_ip_allowed(remote_addr):
                    continue 

                if not name: continue
                
                # DETECCIÓN INTELIGENTE: Buscar por IP primero
                existing_client_by_ip = existing_clients_by_ip.get(remote_addr) if remote_addr else None
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
                    'profile': secret.get('profile', 'default'),
                    'status': 'disabled' if secret.get('disabled') == 'true' else 'active',
                    'exists_in_db': is_duplicate,
                    'name_changed': name_changed,
                    'old_username': existing_client_by_ip.username if name_changed else None,
                    'client_id': existing_client_by_ip.id if existing_client_by_ip else None,
                    'mikrotik_id': secret.get('.id')
                })
        except Exception as e:
            logger.error(f"Error scanning PPPoE: {e}")

        # --- B. SCAN EXISTING SIMPLE QUEUES ---
        try:
            queues = adapter._api_connection.get_resource('/queue/simple').get()
            for q in queues:
                name = q.get('name', '')
                target = q.get('target', '') # Ej: 192.168.10.25/32
                
                # FILTRO: Excluir equipos de gestión
                if is_management_equipment(name):
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
                
                # FILTRO: Excluir equipos de gestión
                if is_management_equipment(lease.get('host-name', lease.get('comment', ''))):
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
                    continue

                if not ip or not is_ip_allowed(ip): continue
                if ip in seen_ips or ip in network_devices: continue
                
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
    
    for item in clients_to_import:
        try:
            username = item.get('username')
            # Check duplicado
            existing = client_repo.get_all()
            if any(c.username.lower() == username.lower() for c in existing):
                continue
                
            subscriber_code = f"CLI-{current_total + 1 + imported_count:04d}"
            legal_name = username.replace('_', ' ').replace('.', ' ').title()
            
            client_data = {
                'router_id': router_id,
                'subscriber_code': subscriber_code,
                'legal_name': legal_name,
                'username': username,
                'password': item.get('password', 'hidden'),
                'ip_address': item.get('ip_address', ''),
                'plan_name': item.get('profile', 'default'),
                'download_speed': '0', 
                'upload_speed': '0',
                'service_type': item.get('type', 'pppoe'), # pppoe o simple_queue
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


@clients_bp.route('/monitor', methods=['POST'])
def monitor_traffic():
    """Monitor de tráfico"""
    client_ids = request.json
    if not client_ids: return jsonify({})
    
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
                    # 1. Obtener PPPoE Active Sessions
                    active_sessions = adapter.get_active_pppoe_sessions()
                    active_map_lower = {k.lower(): k for k in active_sessions.keys()}
                    
                    # 2. Obtener ARP Table para detectar clientes Simple Queue online
                    arp_table = adapter.get_arp_table()
                    arp_ips = {arp.get('address') for arp in arp_table if arp.get('address')}
                    
                    
                    # 3. Obtener Simple Queues stats con tráfico en tiempo real
                    try:
                        queue_stats = adapter._api_connection.get_resource('/queue/simple').get()
                        queue_map = {}
                        queue_by_ip = {}
                        
                        for q in queue_stats:
                            name = q.get('name', '').lower()
                            target = q.get('target', '')
                            ip = target.split('/')[0] if '/' in target else target
                            
                            # Obtener tasa de tráfico actual (formato: "upload/download" en bps)
                            rate = q.get('rate', '0/0')
                            
                            # Parsear rate "upload/download"
                            try:
                                upload_str, download_str = rate.split('/')
                                upload_bps = int(upload_str)
                                download_bps = int(download_str)
                            except:
                                upload_bps = 0
                                download_bps = 0
                            
                            queue_info = {
                                'ip': ip,
                                'upload': upload_bps,
                                'download': download_bps,
                                'disabled': q.get('disabled', 'false') == 'true'
                            }
                            
                            queue_map[name] = queue_info
                            if ip:
                                queue_by_ip[ip] = queue_info
                                
                    except Exception as e:
                        logger.error(f"Error reading queue stats: {e}")
                        queue_map = {}
                        queue_by_ip = {}
                    
                    online_clients_real_names = []
                    db_to_router_name = {}
                    
                    for client in clients_list:
                        db_username_lower = client.username.lower()
                        client_ip = client.ip_address
                        
                        # Determinar si está online
                        is_online = False
                        uptime = None
                        ip = client_ip
                        upload = 0
                        download = 0
                        
                        # Caso 1: PPPoE Active
                        if db_username_lower in active_map_lower:
                            is_online = True
                            real_name = active_map_lower[db_username_lower]
                            session_info = active_sessions[real_name]
                            uptime = session_info.get('uptime')
                            ip = session_info.get('ip') or client_ip
                            online_clients_real_names.append(real_name)
                            db_to_router_name[client.id] = real_name
                        
                        # Caso 2: Simple Queue - buscar por nombre de usuario
                        elif db_username_lower in queue_map:
                            queue_info = queue_map[db_username_lower]
                            queue_ip = queue_info['ip']
                            
                            # Está online si la IP está en ARP o si la queue no está disabled
                            if (queue_ip and queue_ip in arp_ips) or not queue_info.get('disabled', False):
                                is_online = True
                                ip = queue_ip or client_ip
                                upload = queue_info['upload']
                                download = queue_info['download']
                        
                        # Caso 3: Simple Queue - buscar por IP del cliente
                        elif client_ip and client_ip in queue_by_ip:
                            queue_info = queue_by_ip[client_ip]
                            
                            # Si está en ARP, definitivamente está online
                            if client_ip in arp_ips or not queue_info.get('disabled', False):
                                is_online = True
                                upload = queue_info['upload']
                                download = queue_info['download']
                        
                        # Caso 4: IP en ARP pero sin queue (cliente conectado sin control)
                        elif client_ip and client_ip in arp_ips:
                            is_online = True
                        
                        results[str(client.id)] = {
                            'status': 'online' if is_online else 'offline',
                            'uptime': uptime,
                            'ip_address': ip or client_ip,
                            'upload': upload,
                            'download': download
                        }
                    
                    # Obtener tráfico para clientes PPPoE
                    if online_clients_real_names:
                        traffic_data = adapter.get_bulk_traffic(online_clients_real_names)
                        for client in clients_list:
                             router_name = db_to_router_name.get(client.id)
                             if router_name and router_name in traffic_data:
                                 results[str(client.id)]['upload'] = traffic_data[router_name]['upload']
                                 results[str(client.id)]['download'] = traffic_data[router_name]['download']
                    
                    adapter.disconnect()
            except Exception as e:
                logger.error(f"Error monitoring router {router.host_address}: {e}")
                
        return jsonify(results)
    except Exception as e:
         logger.error(f"Error traffic monitor: {e}")
         return jsonify({})
