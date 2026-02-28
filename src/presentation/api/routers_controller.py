"""
Routers API Controller - DATOS REALES
Endpoints CRUD para gestión de routers con sincronización MikroTik
"""
from flask import Blueprint, jsonify, request
from datetime import datetime
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import NetworkSegment, Router, Invoice, InvoiceItem, InternetPlan
from src.infrastructure.mikrotik.adapter import MikroTikAdapter
from src.application.services.audit_service import AuditService
from ipaddress import ip_network, ip_address, IPv4Network, IPv6Network
from src.application.services.report_service import ReportService
from src.application.services.auth import login_required, admin_required, UserRole, permission_required
import logging
import re

logger = logging.getLogger(__name__)

routers_bp = Blueprint('routers', __name__, url_prefix='/api/routers')

def _get_next_subscriber_code(client_repo, prefix='CLI-'):
    """Genera el siguiente código de suscriptor basado en el máximo actual en BD"""
    try:
        existing_clients = client_repo.get_all()
        max_num = 0
        for c in existing_clients:
            if c.subscriber_code and c.subscriber_code.startswith(prefix):
                match = re.search(f"{prefix}(\\d+)", c.subscriber_code)
                if match:
                    try:
                        num = int(match.group(1))
                        if num > max_num:
                            max_num = num
                    except:
                        pass
        return f"{prefix}{max_num + 1:04d}"
    except Exception as e:
        logger.error(f"Error generating subscriber code: {e}")
        # fallback seguro
        return f"{prefix}{len(client_repo.get_all()) + 1:04d}"


@routers_bp.route('', methods=['GET'])
@login_required
def get_routers():
    """
    Obtiene listado de todos los routers desde BD (carga instantánea)
    """
    from flask import g
    db = get_db()
    router_repo = db.get_router_repository()
    client_repo = db.get_client_repository()
    
    user = g.user
    
    is_restricted_role = user.role not in [UserRole.ADMIN.value, UserRole.ADMIN_FEM.value, UserRole.PARTNER.value]
    
    if is_restricted_role:
        # Check both legacy assigned_router_id and new assignments relationship
        allowed_router_ids = set()
        
        # If the user has explicitly defined router assignments (Multi-router feature), use ONLY those.
        # Otherwise, fallback to the legacy assigned_router_id if it exists.
        has_assignments = hasattr(user, 'assignments') and len(user.assignments) > 0
        
        if has_assignments:
            for assignment in user.assignments:
                if assignment.router_id:
                    allowed_router_ids.add(assignment.router_id)
        elif user.assigned_router_id:
            allowed_router_ids.add(user.assigned_router_id)
                    
        if allowed_router_ids:
            all_routers = router_repo.get_all()
            routers = [r for r in all_routers if r.id in allowed_router_ids]
        else:
            routers = [] # Restricted user with no assignments sees no routers
    else:
        routers = router_repo.get_all()
        
    result = []
    
    for router in routers:
        router_dict = router.to_dict()
        
        clients_for_router = client_repo.get_by_router(router.id)
        router_dict['clients_connected'] = len(clients_for_router)
        
        # Calcular estados para mini-tarjetas
        online_count = 0
        offline_count = 0
        active_count = 0
        
        for c in clients_for_router:
            # SÓLO contamos métricas de conectividad para clientes con estado "active" (Administrativamente habilitados)
            status = str(c.status).lower() if c.status else 'active'
            if status == 'active':
                active_count += 1
                if c.is_online:
                    online_count += 1
                else:
                    offline_count += 1
                
        router_dict['clients_online'] = online_count
        router_dict['clients_offline'] = offline_count
        router_dict['clients_active'] = active_count
        
        # Calcular ingreso potencial (solo clientes activos)
        potential = sum((c.monthly_fee or 0) for c in clients_for_router if str(c.status).lower() == 'active')
        router_dict['potential_revenue'] = float(potential)
        
        result.append(router_dict)
    
    return jsonify(result)


@routers_bp.route('/<int:router_id>', methods=['GET'])
@login_required
def get_router(router_id):
    """
    Obtiene un router específico por ID - DATOS REALES
    """
    db = get_db()
    router_repo = db.get_router_repository()
    
    router = router_repo.get_by_id(router_id)
    if not router:
        return jsonify({'error': 'Router no encontrado'}), 404
    
    return jsonify(router.to_dict())


@routers_bp.route('', methods=['POST'])
@permission_required('routers:list', 'create')
def create_router():
    """
    Crea un nuevo router - DATOS REALES
    """
    data = request.json
    
    db = get_db()
    router_repo = db.get_router_repository()
    
    try:
        router = router_repo.create(data)
        
        # Auditoría
        AuditService.log(
            operation='router_created',
            category='router',
            entity_type='router',
            entity_id=router.id,
            description=f"Nuevo router creado: {router.alias} ({router.host_address})",
            new_state=router.to_dict()
        )
        
        logger.info(f"Router creado: {router.alias}")
        return jsonify(router.to_dict()), 201
    except Exception as e:
        logger.error(f"Error creating router: {str(e)}")
        return jsonify({'error': str(e)}), 400


@routers_bp.route('/<int:router_id>', methods=['PUT'])
@permission_required('routers:list', 'edit')
def update_router(router_id):
    """
    Actualiza un router existente - DATOS REALES
    """
    data = request.json
    
    db = get_db()
    router_repo = db.get_router_repository()
    
    router = router_repo.update(router_id, data)
    if not router:
        return jsonify({'error': 'Router no encontrado'}), 404
    
    # Auditoría
    AuditService.log(
        operation='router_updated',
        category='router',
        entity_type='router',
        entity_id=router_id,
        description=f"Router actualizado: {router.alias}",
        new_state=data
    )
    
    logger.info(f"Router actualizado: {router.alias}")
    return jsonify(router.to_dict())


@routers_bp.route('/<int:router_id>', methods=['DELETE'])
@permission_required('routers:list', 'delete')
def delete_router(router_id):
    """
    Elimina un router - DATOS REALES
    """
    db = get_db()
    router_repo = db.get_router_repository()
    
    # Obtener info para log antes de borrar
    router = router_repo.get_by_id(router_id)
    
    success = router_repo.delete(router_id)
    if not success:
        return jsonify({'error': 'Router no encontrado'}), 404
    
    # Auditoría
    AuditService.log(
        operation='router_deleted',
        category='router',
        entity_type='router',
        entity_id=router_id,
        description=f"Router eliminado: {router.alias if router else router_id}"
    )
    
    logger.info(f"Router eliminado: ID {router_id}")
    return jsonify({'message': 'Router eliminado correctamente'}), 200


@routers_bp.route('/<int:router_id>/test-connection', methods=['POST'])
@permission_required('routers:monitoring', 'view')
def test_connection(router_id):
    """
    Prueba la conexión con un router - CONEXIÓN REAL MIKROTIK
    """
    db = get_db()
    router_repo = db.get_router_repository()
    
    router = router_repo.get_by_id(router_id)
    if not router:
        return jsonify({'error': 'Router no encontrado'}), 404
    
    adapter = MikroTikAdapter()
    
    try:
        connected = adapter.connect(
            host=router.host_address,
            username=router.api_username,
            password=router.api_password,
            port=router.api_port
        )
        
        if connected:
            # Obtener información del sistema
            config = adapter.discover_configuration()
            adapter.disconnect()
            
            # Actualizar estado
            router_repo.update(router_id, {'status': 'online'})
            
            return jsonify({
                'success': True,
                'message': 'Conexión exitosa',
                'details': {
                    'version': config['system_info'].get('version', 'N/A'),
                    'board': config['system_info'].get('board_name', 'N/A'),
                    'uptime': config['system_info'].get('uptime', 'N/A'),
                    'methods': config['methods']
                }
            })
        else:
            router_repo.update(router_id, {'status': 'offline'})
            return jsonify({
                'success': False,
                'message': 'No se pudo conectar al router'
            }), 200
            
    except Exception as e:
        logger.error(f"Error testing connection: {str(e)}")
        router_repo.update(router_id, {'status': 'offline'})
        return jsonify({
            'success': False,
            'message': f'Error de conexión: {str(e)}'
        }), 200


@routers_bp.route('/<int:router_id>/billing', methods=['PUT'])
@permission_required('routers:list', 'edit')
def update_billing_config(router_id):
    """Actualiza la configuración de facturación del router"""
    try:
        data = request.json
        billing_day = data.get('billing_day')
        grace_period = data.get('grace_period')
        cut_day = data.get('cut_day')
        
        db = get_db()
        router_repo = db.get_router_repository()
        
        # Validar existencia
        router = router_repo.get_by_id(router_id)
        if not router:
            return jsonify({'error': 'Router no encontrado'}), 404
            
        # Update using repository generic update (or specific if strictly typed)
        # Assuming repository.update takes a dict
        update_data = {}
        if billing_day is not None: update_data['billing_day'] = billing_day
        if grace_period is not None: update_data['grace_period'] = grace_period
        if cut_day is not None: update_data['cut_day'] = cut_day
        
        router_repo.update(router_id, update_data)
        
        # Auditoría
        AuditService.log(
            operation='router_billing_config_updated',
            category='router',
            entity_type='router',
            entity_id=router_id,
            description=f"Configuración de facturación de {router.alias} actualizada",
            new_state=update_data
        )
        
        return jsonify({'success': True, 'message': 'Configuración actualizada'})
        
    except Exception as e:
        logger.error(f"Error updating billing config: {e}")
        return jsonify({'error': str(e)}), 500


@routers_bp.route('/<int:router_id>/sync', methods=['POST'])
@permission_required('routers:monitoring', 'edit')
def sync_router(router_id):
    """
    Sincroniza la configuración y métricas del router - SINCRONIZACIÓN REAL
    Soporta confirmación en dos pasos:
    - confirm=False (default): Solo descubre y retorna cantidades
    - confirm=True: Ejecuta el aprovisionamiento real
    """
    # Obtener parámetro de confirmación del body
    data = request.json if request.json else {}
    confirm = data.get('confirm', False)
    selected_keys = set(data.get('selected_candidates', []))
    
    db = get_db()
    router_repo = db.get_router_repository()
    client_repo = db.get_client_repository()
    
    router = router_repo.get_by_id(router_id)
    if not router:
        return jsonify({'error': 'Router no encontrado'}), 404
    
    adapter = MikroTikAdapter()
    
    try:
        connected = adapter.connect(
            host=router.host_address,
            username=router.api_username,
            password=router.api_password,
            port=router.api_port
        )
        
        if not connected:
            return jsonify({
                'success': False,
                'message': 'No se pudo conectar al router. Verifica la IP y que tengas acceso a la red.'
            }), 200

        # Descubrir configuración
        config = adapter.discover_configuration()
        
        # Actualizar métricas del router
        sys_info = config.get('system_info', {})
        metrics = {
            'status': 'online',
            'uptime': sys_info.get('uptime', 'N/A'),
            'cpu_usage': sys_info.get('cpu_load', 0),
            'memory_usage': sys_info.get('memory_usage', 0),
            # Usar conexiones activas reales detectadas, o fallback a 0
            'clients_connected': sys_info.get('active_connections', 0), 
        }
        
        router_repo.update_metrics(router_id, metrics)
        
        # ----------------------------------------------------------------------
        # NUEVO: AUTO-PROVISIONING (Descubrimiento y creación automática)
        # Con soporte para confirmación en dos pasos y selección
        # ----------------------------------------------------------------------
        provisioned_count = 0
        candidates_count = 0
        
        # 1. Obtener Segmentos de Red vinculados a este Router y Clientes Existentes
        segments = db.session.query(NetworkSegment).filter(NetworkSegment.router_id == router_id).all()
        allowed_networks = []
        for s in segments:
            try:
                allowed_networks.append(ip_network(s.cidr, strict=False))
            except Exception as e:
                logger.warning(f"Segmento invalido en BD {s.cidr} para router {router_id}: {e}")
        
        has_segments_filter = len(allowed_networks) > 0
        logger.info(f"Sync sync_router: Start auto-provisioning. router={router_id}, segments_found={len(allowed_networks)}, segments={[str(n) for n in allowed_networks]}")

        # POLÍTICA ESTRICTA: Si no hay segmentos declarados, NO se importa NADA
        if not has_segments_filter:
            logger.warning(f"⚠️ Router {router_id} ({router.alias}): No tiene segmentos de red declarados. Importación/Sincronización BLOQUEADA.")
            # Retornamos respuesta vacía indicando el problema
            adapter.disconnect()
            return jsonify({
                'success': True,
                'requires_confirmation': True,
                'current_queues': 0,
                'candidates_to_add': 0,
                'candidates': [],
                'message': f'⚠️ El router {router.alias} no tiene segmentos de red internos declarados. Debes configurar al menos un segmento en la pestaña de Segmentos del router antes de importar clientes.',
                'details': {
                    'methods_detected': config['methods'],
                    'clients_in_db': len(client_repo.get_by_router(router_id)),
                    'provisioned': 0,
                    'system_info': config['system_info']
                }
            })

        # Get exclusion keywords from router config
        exclusion_raw = router.exclusion_keywords or ""
        dynamic_keywords = [k.strip().upper() for k in exclusion_raw.split(',') if k.strip()]
        
        def is_ip_allowed(ip_str):
            """Valida ESTRICTAMENTE que la IP pertenezca a un segmento declarado."""
            clean_ip = ip_str.split('/')[0] if ip_str else ''
            if not clean_ip or clean_ip == '0.0.0.0': return False
            try:
                addr = ip_network(clean_ip, strict=False) if '/' in clean_ip else ip_address(clean_ip)
                if isinstance(addr, (IPv4Network, IPv6Network)):
                    return any(addr.overlaps(net) for net in allowed_networks)
                return any(addr in net for net in allowed_networks)
            except ValueError:
                return False

        def is_excluded_by_keywords(name, comment=''):
            """Verifica si un nombre o comentario debe ser excluido por palabras clave."""
            if not name and not comment:
                return False
                
            text_to_check = f"{name or ''} {comment or ''}".upper()
            
            # 1. Patrones dinámicos configurados por el usuario
            for pattern in dynamic_keywords:
                if pattern in text_to_check:
                    return True

            # 2. Patrones base de seguridad (hardcoded fallback)
            base_patterns = [
                'GESTION', 'GESTION-AP', 'AP-', 'ROUTER-', 'MIKROTIK', 'SWITCH',
                'CORE', 'BACKBONE', 'ADMIN', 'MANAGEMENT'
            ]
            for pattern in base_patterns:
                if pattern in text_to_check:
                    return True
            return False

        # Obtener clientes existentes GLOBALES para verificar IP duplicada real
        all_clients = client_repo.get_all()
        # Mapa global de IPs: IP -> (ClientName, RouterID)
        global_ip_map = {c.ip_address: {'name': c.legal_name, 'router': c.router_id} for c in all_clients if c.ip_address}
        
        # Mapa local (este router) para nombres de usuario y demas
        existing_clients_in_router = [c for c in all_clients if c.router_id == router_id]
        existing_usernames = {c.username.lower() for c in existing_clients_in_router}
        existing_ips = {c.ip_address for c in existing_clients_in_router if c.ip_address}

            # 2. Escanear estado actual del Router
        try:
            # Obtener recursos CRUDOS
            ppp_active = adapter.get_active_pppoe_sessions()
            ppp_secrets = adapter.get_all_pppoe_secrets()
            all_pools = adapter.get_ip_pools()
            existing_queues = adapter._api_connection.get_resource('/queue/simple').get()
            dhcp_leases = adapter.get_dhcp_leases()
            arp_table = adapter.get_arp_table()
            
            # Construir Sets de validación
            
            # A. IPs que YA tienen Simple Queue (Ya están limitados/gestionados)
            ips_with_queues = set()
            for q in existing_queues:
                target = q.get('target', '')
                # Target puede ser "192.168.1.10/32" o "192.168.1.10"
                clean_target = target.split('/')[0]
                if clean_target:
                    ips_with_queues.add(clean_target)

            # B. IPs activas en ARP (Para validar vs DHCP)
            ips_in_arp = set()
            for arp in arp_table:
                if arp.get('address'):
                    ips_in_arp.add(arp.get('address'))
            
            logger.info(f"Sync Logic: Queues found={len(ips_with_queues)}, ARP entries={len(ips_in_arp)}, DHCP Leases={len(dhcp_leases)}")
            
            candidates = {} # Identificador único -> Info del candidato

            # ------------------------------------------------------------
            # ESTRATEGIA DE SINCRONIZACIÓN REFINADA (Solicitud Usuario)
            # 1. Recorrer DHCP Leases
            # 2. Validar coincidencia con ARP
            # 3. Validar que NO tenga Simple Queue (Si tiene, ya está gestionado)
            # 4. Validar que NO esté en BD local (existing_usernames / existing_ips)
            # ------------------------------------------------------------

            for lease in dhcp_leases:
                ip = lease.get('address')
                mac = lease.get('mac-address', '')
                host_name = lease.get('host-name', '')
                comment = lease.get('comment', '')
                
                # --- Filtros de Exclusión ---

                # 1. IP Válida y Permitida (VALIDACIÓN ESTRICTA DE SEGMENTO POR ROUTER)
                if not ip or not is_ip_allowed(ip): 
                    continue
                
                # 2. Exclusión por palabras clave (nombre/comentario)
                if is_excluded_by_keywords(host_name, comment):
                    continue

                # 3. Validar con ARP (Debe estar activo/presente en la red física)
                if ip not in ips_in_arp:
                    # Si tiene lease pero no está en ARP, probablemente no está conectado
                    continue

                # 4. Validar Simple Queues (Si ya tiene queue, NO es candidato a "Nuevo")
                if ip in ips_with_queues:
                    continue

                # 5. Local DB Check (Si ya está en BD de este router)
                if ip in existing_ips:
                    continue
                
                # --- PREVENCIÓN DE COLISIONES GLOBAL (AISLAMIENTO DE ROUTERS) ---
                ip_status = 'ok'
                dup_info = ''
                if ip in global_ip_map:
                    dup_client = global_ip_map[ip]
                    if dup_client['router'] != router_id:
                        # BLOQUEO: Esta IP pertenece a OTRO router en la BD
                        logger.warning(f"Sync: IP {ip} already managed in router {dup_client['router']} by {dup_client['name']}. Skipping to avoid mixing.")
                        continue # Saltamos para asegurar aislamiento total
                    else:
                        # Es del mismo router pero no cayó en existing_ips? (posible inconsistencia o IP recién liberada)
                        ip_status = 'conflict'
                        dup_info = f"Ya asignada en este router a: {dup_client['name']}"

                # Nombre propuesto
                host = host_name or comment or f"User-{ip.split('.')[-1]}"
                
                # Check Username Local
                if host.lower() in existing_usernames:
                    continue

                candidates[f"dhcp_{ip}"] = {
                    'key': f"dhcp_{ip}",
                    'host': host,
                    'ip': ip,
                    'mac': mac,
                    'source': 'DHCP+ARP Verified',
                    'type': 'simple_queue', 
                    'profile': '15M', 
                    'ip_status': ip_status,
                    'dup_info': dup_info
                }

            # 6. Sincronizar PPPoE Secrets con las mismas reglas de aislamiento
            for s in ppp_secrets:
                name = s.get('name', '')
                ip = s.get('remote_address', '')
                profile = s.get('profile', '')
                comment = s.get('comment', '')
                
                # Reglas de exclusión base
                # PPPoE: Validar IP contra segmentos si tiene remote-address asignado
                if ip and not is_ip_allowed(ip): continue
                if name.lower() in existing_usernames: continue
                # Exclusión por palabras clave en nombre Y comentario del secret
                if is_excluded_by_keywords(name, comment): continue
                
                # Validación de colisión global para PPPoE
                if ip and ip in global_ip_map:
                    dup_client = global_ip_map[ip]
                    if dup_client['router'] != router_id:
                        logger.warning(f"Sync PPPoE: IP {ip} already managed in router {dup_client['router']}. Skipping.")
                        continue

                # Si es un secret, es un candidato válido aunque ya tenga queue (dynamic) o no.
                # Lo tratamos como "Importar configuración existente"
                candidates[name] = {
                    'key': name,
                    'host': name,
                    'ip': ip,
                    'mac': '',
                    'source': 'PPPoE Secret',
                    'type': 'pppoe',
                    'profile': profile,
                    'password': s.get('password', ''),
                    'ip_status': 'ok',
                    'dup_info': ''
                }


            candidates_count = len(candidates)
            logger.info(f"Sync sync_router: Valid provisioning candidates={candidates_count}")

            # 4. PROVISIONAR (Solo si confirm=True)
            if confirm:
                # Si confirm=True, filtramos por selected_keys si se enviaron
                # Si selected_keys está vacío pero confirm=True, asumimos TODOS? 
                # Mejor seguridad: Si selected_keys existe, usarlo. Si no (legacy), todos.
                # El frontend enviará selected_candidates siempre. 
                
                final_candidates = []
                if 'selected_candidates' in data:
                    # Validar explicitamente contra selected_keys
                    for k, cand in candidates.items():
                        if k in selected_keys:
                            final_candidates.append(cand)
                else:
                    # Legacy behavior: All
                     final_candidates = list(candidates.values())

                for info in final_candidates:
                    original_host = info['host']
                    username = original_host 
                    ip = info.get('ip', '')
                    c_type = info.get('type', 'simple_queue')
                    
                    # Evitar colisión de nombres (generación de unicos)
                    base_username = username
                    counter = 1
                    while username.lower() in existing_usernames: # Check local DB only for naming collision
                         suffix = ip.split('.')[-1] if ip else counter
                         username = f"{base_username} ({suffix})"
                         if counter > 1 and ip:
                             username = f"{base_username} ({suffix}-{counter})"
                         counter += 1
                    
                    # A. Crear Registro en BD
                    subscriber_code = _get_next_subscriber_code(client_repo)
                    legal_name = username 
                    
                    # Determine Plan Information
                    plan_name = ReportService.format_bandwidth(info.get('profile', '15M/15M'))
                    monthly_fee = 70000.0 if router_id == 2 else 90000.0
                    download_val = '15M'
                    upload_val = '15M'
                    
                    # Logic: Try default_plan_id first, then map profile to plan name, else default
                    selected_plan_id = data.get('default_plan_id')
                    try:
                        plan_obj = None
                        if selected_plan_id:
                            plan_obj = InternetPlan.query.get(selected_plan_id)
                        
                        if not plan_obj:
                             mikrotik_profile = info.get('profile', '')
                             if mikrotik_profile:
                                plan_obj = InternetPlan.query.filter_by(name=mikrotik_profile).first()

                        if plan_obj:
                            plan_name = plan_obj.name
                            monthly_fee = plan_obj.monthly_price
                            # Convert kbps to M string format for display/storage if needed, or keeping raw if schema changed
                            # Schema seems to store strings like '15M' based on previous code
                            download_val = f"{int(plan_obj.download_speed/1000)}M"
                            upload_val = f"{int(plan_obj.upload_speed/1000)}M"
                    except Exception as e:
                        logger.error(f"Error mapping plan for {username}: {e}")
                    
                    client_data = {
                        'router_id': router_id,
                        'subscriber_code': subscriber_code,
                        'legal_name': legal_name,
                        'username': username, # Username unico generado
                        'password': info.get('password', 'N/A'),
                        'ip_address': ip,
                        'plan_name': plan_name,
                        'monthly_fee': monthly_fee,
                        'download_speed': download_val,
                        'upload_speed': upload_val,
                        'service_type': c_type,
                        'status': 'active',
                        'mikrotik_id': ''
                    }
                    
                    try:
                        db_client = client_repo.create(client_data)
                        
                        # B. Crear en MikroTik si es Simple Queue (DHCP/ARP)
                        # Si es PPPoE Secret ya existe en el Router, solo vinculamos mikrotik_id si queremos
                        if c_type == 'simple_queue':
                            queue_payload = {
                                'queue_name': username,
                                'target_address': f"{ip}/32",
                                'max_limit': '15M/15M',
                                'comment': ""
                            }
                            result = adapter._create_queue_client(queue_payload)
                            if result.get('success'):
                                 client_repo.update(db_client.id, {'mikrotik_id': result.get('mikrotik_id')})
                                 provisioned_count += 1
                                 logger.info(f"Auto-provisioned Simple Queue {username} at {ip}")
                        else:
                            # PPPoE Secret - Ya existe, no creamos nada en MikroTik, solo log
                            provisioned_count += 1
                            logger.info(f"Imported existing PPPoE Secret {username} to DB")

                        # --- SMART IMPORT LOGIC: Financial Onboarding ---
                        import_strategy = data.get('import_strategy', 'none')
                        if import_strategy in ['debt', 'grace']:
                            try:
                                from src.application.services.billing_service import BillingService
                                bs = BillingService()
                                initial_debt = float(data.get('initial_debt', 0))
                                
                                # Process financial enrollment
                                bs.onboard_client_financially(
                                    db_client, 
                                    import_strategy, 
                                    initial_debt=initial_debt,
                                    registered_by=getattr(g, 'user', None).username if hasattr(g, 'user') and g.user else 'System'
                                )

                                # If debt strategy, apply immediate Mikrotik suspension
                                if import_strategy == 'debt' and initial_debt > 0:
                                    logger.info(f"Applying immediate suspension for debt-onboarded client: {username}")
                                    from src.application.services.mikrotik_operations import safe_suspend_client
                                    suspend_res = safe_suspend_client(db_client.id)
                                    if not suspend_res.get('success'):
                                        logger.warning(f"Initial suspension failed for {username}: {suspend_res.get('message')}")
                                
                            except Exception as fin_ex:
                                logger.error(f"Error in financial onboarding for {username}: {fin_ex}")

                        # Añadir a vistos para evitar duplicados en la misma ejecución
                        existing_usernames.add(username.lower())
                        
                    except Exception as ex:
                        # IMPORTANTE: Rollback para evitar bloqueo de sesión
                        db.session.rollback()
                        logger.error(f"Error provisioning client {username} at {ip}: {ex}")

        except Exception as e:
            logger.error(f"Error in auto-provisioning logic: {e}")

        # ----------------------------------------------------------------------
        
        # Contar clientes en BD (actualizado)
        clients_in_db = len(client_repo.get_by_router(router_id))
        
        # Contar Simple Queues actuales
        try:
            current_queues_count = len(existing_queues) if 'existing_queues' in locals() else 0
        except:
            current_queues_count = 0
        
        adapter.disconnect()
        
        # Auditoría de sincronización masiva
        if confirm and provisioned_count > 0:
             AuditService.log(
                operation='router_sync',
                category='system',
                entity_type='router',
                entity_id=router_id,
                description=f"Sincronización de router {router.alias}. Candidatos: {candidates_count}, Provisionados: {provisioned_count}"
            )
        
        return jsonify({
            'success': True,
            'requires_confirmation': not confirm,
            'current_queues': current_queues_count,
            'candidates_to_add': candidates_count,
            'candidates': list(candidates.values()) if not confirm else [],
            'message': f'Sincronización completada. {provisioned_count} clientes importados.' if confirm else f'Descubiertos {candidates_count} nuevos candidatos.',
            'details': {
                'methods_detected': config['methods'],
                'clients_in_db': clients_in_db,
                'provisioned': provisioned_count,
                'system_info': config['system_info']
            }
        })
        
    except Exception as e:
        logger.error(f"Error syncing router: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error de sincronización: {str(e)}'
        }), 200
@routers_bp.route('/<int:router_id>/setup-cutoff', methods=['POST'])
@admin_required
def setup_cutoff(router_id):
    """
    Configura las reglas de firewall para cortes (Address List IPS_BLOQUEADAS)
    """
    db = get_db()
    router_repo = db.get_router_repository()
    
    router = router_repo.get_by_id(router_id)
    if not router:
        return jsonify({'error': 'Router no encontrado'}), 404
        
    adapter = MikroTikAdapter()
    try:
        if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
            success = adapter.ensure_cutoff_firewall_rules()
            adapter.disconnect()
            
            if success:
                return jsonify({
                    'success': True,
                    'message': f'Reglas de firewall configuradas correctamente en {router.alias}'
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'No se pudieron configurar algunas reglas. Verifica los permisos del usuario API.'
                }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'No se pudo conectar al router'
            }), 200
    except Exception as e:
        logger.error(f"Error in setup-cutoff: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@routers_bp.route('/sync-all', methods=['POST'])
@admin_required
def sync_all_routers():
    """
    Sincroniza TODOS los routers - SINCRONIZACIÓN MÚLTIPLE
    """
    db = get_db()
    router_repo = db.get_router_repository()
    
    routers = router_repo.get_all()
    results = []
    
    for router in routers:
        adapter = MikroTikAdapter()
        try:
            connected = adapter.connect(
                host=router.host_address,
                username=router.api_username,
                password=router.api_password,
                port=router.api_port
            )
            
            if connected:
                config = adapter.discover_configuration()
                metrics = {
                    'status': 'online',
                    'uptime': config['system_info'].get('uptime', 'N/A'),
                }
                router_repo.update_metrics(router.id, metrics)
                
                results.append({
                    'router': router.alias,
                    'success': True
                })
            else:
                router_repo.update(router.id, {'status': 'offline'})
                results.append({
                    'router': router.alias,
                    'success': False,
                    'error': 'No se pudo conectar'
                })
                
            adapter.disconnect()
            
        except Exception as e:
            logger.error(f"Error syncing {router.alias}: {str(e)}")
            router_repo.update(router.id, {'status': 'offline'})
            results.append({
                'router': router.alias,
                'success': False,
                'error': str(e)
            })
    
    successful = len([r for r in results if r['success']])
    
    return jsonify({
        'total': len(routers),
        'successful': successful,
        'failed': len(routers) - successful,
        'results': results
    })


@routers_bp.route('/monitor', methods=['GET'])
@login_required
def monitor_routers():
    """
    Obtiene métricas en tiempo real de todos los routers (Live Monitor)
    Usa hilos para consultar en paralelo y ser rápido.
    """
    try:
        db = get_db()
        router_repo = db.get_router_repository()
        routers = router_repo.get_all()
        
        # 1. Extraer datos necesarios y CONTAR CLIENTES POR ROUTER
        client_repo = db.get_client_repository()
        all_clients = client_repo.get_all()
        
        # Mapa de conteo rápido: router_id -> count
        client_counts = {}
        for c in all_clients:
            rid = c.router_id
            client_counts[rid] = client_counts.get(rid, 0) + 1

        routers_data = []
        for r in routers:
            routers_data.append({
                'id': r.id,
                'host_address': r.host_address,
                'api_username': r.api_username,
                'api_password': r.api_password,
                'api_port': r.api_port
            })

        import concurrent.futures
        
        def fetch_router_metrics(router_data):
            """Worker que consulta métricas de un router usando datos planos (no objetos DB)"""
            router_id = router_data['id']
            result = {
                'id': router_id,
                'status': 'offline',
                'uptime': 'N/A',
                'cpu_usage': 0,
                'memory_usage': 0,
                'last_error': None
            }
            
            try:
                adapter = MikroTikAdapter()
                connected = adapter.connect(
                    host=router_data['host_address'],
                    username=router_data['api_username'],
                    password=router_data['api_password'],
                    port=router_data['api_port'],
                    timeout=5
                )

                if not connected:
                    result['last_error'] = 'No se pudo establecer conexión (Timeout o Credenciales incorrectas)'
                else:
                    try:
                        res_list = adapter._api_connection.get_resource('/system/resource').get()
                        if res_list:
                            res = res_list[0]
                            # Handle MikroTik weird types if necessary (usually strings or ints)
                            result['cpu_usage'] = int(str(res.get('cpu-load', 0)))
                            
                            total = int(str(res.get('total-memory', 1)))
                            free = int(str(res.get('free-memory', 0)))
                            if total > 0:
                                result['memory_usage'] = int(((total - free)/total)*100)
                            
                            result['uptime'] = str(res.get('uptime', 'N/A'))
                        
                        result['status'] = 'online'
                        result['last_error'] = None
                        adapter.disconnect()
                    except Exception as e:
                        logger.error(f"Error reading resources for router {router_id}: {e}")
                        result['last_error'] = f"Error al leer recursos: {str(e)}"
                        if adapter._is_connected:
                            adapter.disconnect()
                
                return result
                    
            except Exception as e:
                logger.error(f"Critical error in worker for router {router_id}: {e}")
                result['last_error'] = str(e)
                return result

        # 2. Ejecutar en paralelo (max 10 routers a la vez)
        results = []
        if routers_data:
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(fetch_router_metrics, rd) for rd in routers_data]
                for future in concurrent.futures.as_completed(futures):
                    try:
                        res = future.result()
                        
                        # Inyectar el conteo de clientes real de la BD
                        res['clients_connected'] = client_counts.get(res['id'], 0)
                        
                        # Actualizar Base de Datos (en el hilo principal, thread-safe)
                        update_data = {
                            'status': res['status'],
                            'cpu_usage': res.get('cpu_usage', 0),
                            'memory_usage': res.get('memory_usage', 0),
                            'uptime': res.get('uptime', 'N/A'),
                            'last_error': res.get('last_error')
                        }
                        
                        if res['status'] == 'online':
                            update_data['last_online_at'] = datetime.now()
                        
                        # Actualizar en DB
                        router_repo.update(res['id'], update_data)
                        
                        # Recuperar info actualizada para devolver
                        updated_router = router_repo.get_by_id(res['id'])
                        if updated_router:
                            res['last_online_at'] = updated_router.last_online_at.isoformat() if updated_router.last_online_at else None
                        
                        results.append(res)
                    except Exception as e:
                        logger.error(f"Thread execution result processing failed: {e}")
        
        return jsonify(results)

    except Exception as e:
        logger.error(f"Global error in monitor_routers: {e}")
        # Return error as JSON to avoid 500 crash in frontend
        return jsonify({'error': str(e)}), 200


# ==============================================================================
# CLIENT IMPORT ENDPOINTS
# ==============================================================================

@routers_bp.route('/<int:router_id>/discover-clients', methods=['GET'])
@admin_required
def discover_clients(router_id):
    """
    Descubre clientes configurados en el router (Simple Queues + PPPoE Secrets)
    sin importarlos a la base de datos. Retorna preview de lo que se encontró.
    SOLO retorna clientes cuyas IPs estén dentro de los segmentos de red declarados.
    """
    db = get_db()
    router_repo = db.get_router_repository()
    
    router = router_repo.get_by_id(router_id)
    if not router:
        return jsonify({'error': 'Router no encontrado'}), 404
    
    # Obtener segmentos de red declarados para este router
    segments = db.session.query(NetworkSegment).filter(NetworkSegment.router_id == router_id).all()
    allowed_networks = []
    for s in segments:
        try:
            allowed_networks.append(ip_network(s.cidr, strict=False))
        except Exception as e:
            logger.warning(f"Segmento inválido {s.cidr} para router {router_id}: {e}")
    
    if not allowed_networks:
        return jsonify({
            'success': False,
            'message': 'No hay segmentos de red declarados para este router. Por favor, configura los segmentos de red primero.'
        }), 400
    
    logger.info(f"Filtering clients by {len(allowed_networks)} declared network segments for router {router_id}")
    
    def is_ip_allowed(ip_str):
        """Verifica si una IP está dentro de los segmentos declarados"""
        if not ip_str:
            return False
        # Limpiar IP (remover /32 si existe)
        clean_ip = ip_str.split('/')[0] if ip_str else ''
        if not clean_ip or clean_ip == '0.0.0.0':
            return False
        try:
            addr = ip_address(clean_ip)
            return any(addr in net for net in allowed_networks)
        except ValueError:
            return False
    
    adapter = MikroTikAdapter()
    
    try:
        connected = adapter.connect(
            host=router.host_address,
            username=router.api_username,
            password=router.api_password,
            port=router.api_port
        )
        
        if not connected:
            return jsonify({
                'success': False,
                'message': 'No se pudo conectar al router'
            }), 400
        
        # Obtener Simple Queues y aplicar filtros (IP declarada + No es gestión)
        all_simple_queues = adapter.get_all_simple_queues()
        filtered_simple_queues = []
        
        # LOS BANCOS (ID 4) gestiona solamente por pppoe según requerimiento
        if router_id != 4 and router.host_address != '12.12.12.122':
            for q in all_simple_queues:
                comment = q.get('comment', '').upper()
                if "GESTION" in comment:
                    continue
                if is_ip_allowed(q.get('ip_address', '')):
                    filtered_simple_queues.append(q)
        else:
            logger.info(f"Skipping Simple Queues for Router {router_id} (LOS BANCOS) - PPPoE Only Mode")
        
        # Obtener PPPoE Secrets y aplicar filtros (IP declarada + No es gestión)
        all_pppoe_secrets = adapter.get_all_pppoe_secrets()
        all_profiles = adapter.get_ppp_profiles()
        all_pools = adapter.get_ip_pools()
        
        # Mapa de pools y perfiles permitidos
        pool_map = {p.get('name'): p.get('ranges') for p in all_pools}
        allowed_profiles = set()
        
        for p in all_profiles:
            p_name = p.get('name')
            remote = p.get('remote-address') # Puede ser IP o Nombre de Pool
            
            # Caso 1: IP directa en el perfil
            if remote and is_ip_allowed(remote):
                allowed_profiles.add(p_name)
                continue
                
            # Caso 2: El nombre del perfil contiene una velocidad o palabra clave que buscamos (opcional, pero ayuda)
            # Caso 3: Es un Pool, verificar rangos
            pool_range = pool_map.get(remote)
            if pool_range:
                # MikroTik: "77.16.10.2-77.16.10.254" o ráfagas separadas por coma
                # Simplificación: Checar la primera IP de la primera ráfaga
                first_part = pool_range.split(',')[0]
                first_ip = first_part.split('-')[0]
                if is_ip_allowed(first_ip):
                    allowed_profiles.add(p_name)

        filtered_pppoe_secrets = []
        for s in all_pppoe_secrets:
            comment = s.get('comment', '').upper()
            if "GESTION" in comment:
                continue
            
            # Lógica de validación:
            # A. Tiene una IP estática permitida
            # B. No tiene IP estática PERO su perfil está en el segmento permitido
            remote_ip = s.get('remote_address', '')
            profile_name = s.get('profile', '')
            
            if is_ip_allowed(remote_ip) or profile_name in allowed_profiles:
                filtered_pppoe_secrets.append(s)
        
        adapter.disconnect()
        
        logger.info(
            f"Discovered from router {router_id}: "
            f"{len(all_simple_queues)} Simple Queues ({len(filtered_simple_queues)} filtered), "
            f"{len(all_pppoe_secrets)} PPPoE Secrets ({len(filtered_pppoe_secrets)} filtered)"
        )
        
        return jsonify({
            'success': True,
            'router_id': router_id,
            'router_name': router.alias,
            'simple_queues': filtered_simple_queues,
            'pppoe_secrets': filtered_pppoe_secrets,
            'total_clients': len(filtered_simple_queues) + len(filtered_pppoe_secrets),
            'counts': {
                'simple_queues': len(filtered_simple_queues),
                'pppoe': len(filtered_pppoe_secrets)
            },
            'filtering_info': {
                'total_found': len(all_simple_queues) + len(all_pppoe_secrets),
                'total_filtered': len(filtered_simple_queues) + len(filtered_pppoe_secrets),
                'excluded': (len(all_simple_queues) + len(all_pppoe_secrets)) - (len(filtered_simple_queues) + len(filtered_pppoe_secrets)),
                'network_segments': [s.cidr for s in segments]
            }
        })
        
    except Exception as e:
        logger.error(f"Error discovering clients: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error al descubrir clientes: {str(e)}'
        }), 200



@routers_bp.route('/<int:router_id>/import-clients', methods=['POST'])
@admin_required
def import_clients(router_id):
    """
    Importa clientes desde MikroTik a la base de datos.
    Body esperado:
    {
        "simple_queues": [...],  // Lista de Simple Queues a importar
        "pppoe_secrets": [...],  // Lista de PPPoE Secrets a importar
        "duplicate_strategy": "skip|update", // Opcional, default: skip
        "code_format": "auto|username"  // Opcional, default: auto
    }
    """
    db = get_db()
    router_repo = db.get_router_repository()
    client_repo = db.get_client_repository()
    
    router = router_repo.get_by_id(router_id)
    if not router:
        return jsonify({'error': 'Router no encontrado'}), 404
    
    data = request.json or {}
    simple_queues = data.get('simple_queues', [])
    pppoe_secrets = data.get('pppoe_secrets', [])
    duplicate_strategy = data.get('duplicate_strategy', 'skip')  # skip o update
    code_format = data.get('code_format', 'auto')  # auto o username
    
    imported = []
    skipped = []
    errors = []
    
    # Obtener clientes existentes SOLO de este router para detectar duplicados locales
    existing_clients = client_repo.get_filtered(router_id=router_id)
    existing_usernames = {c.username.lower(): c for c in existing_clients}
    existing_ips = {c.ip_address: c for c in existing_clients if c.ip_address}
    
    # Función auxiliar para generar subscriber_code
    def generate_subscriber_code():
        if code_format == 'username':
            return None  # Se usará el username
        else:  # auto
            return _get_next_subscriber_code(client_repo)
    
    # Importar Simple Queues
    for queue in simple_queues:
        try:
            name = queue.get('name', '')
            ip_address = queue.get('ip_address', '')
            
            if not name:
                errors.append({'type': 'simple_queue', 'data': queue, 'error': 'Sin nombre'})
                continue
            
            # Verificar duplicados
            is_duplicate = False
            if name.lower() in existing_usernames:
                is_duplicate = True
                if duplicate_strategy == 'skip':
                    skipped.append({'type': 'simple_queue', 'name': name, 'reason': 'Username ya existe'})
                    continue
            
            if ip_address and ip_address in existing_ips:
                is_duplicate = True
                if duplicate_strategy == 'skip':
                    skipped.append({'type': 'simple_queue', 'name': name, 'reason': 'IP ya existe'})
                    continue
            
            # Crear o actualizar cliente
            subscriber_code = generate_subscriber_code() or name
            
            client_data = {
                'router_id': router_id,
                'subscriber_code': subscriber_code,
                'legal_name': name,
                'username': name,
                'password': '**',
                'ip_address': ip_address,
                'monthly_fee': 70000.0 if router_id == 2 else 90000.0,
                'plan_name': f"{queue.get('download_speed', '')} / {queue.get('upload_speed', '')}",
                'download_speed': queue.get('download_speed', ''),
                'upload_speed': queue.get('upload_speed', ''),
                'service_type': 'simple_queue',
                'status': 'suspended' if queue.get('disabled') else 'active',
                'mikrotik_id': queue.get('mikrotik_id', ''),
            }
            
            if is_duplicate and duplicate_strategy == 'update':
                # Actualizar existente
                existing = existing_usernames.get(name.lower())
                if existing:
                    client_repo.update(existing.id, client_data)
                    imported.append({'type': 'simple_queue', 'name': name, 'action': 'updated'})
            else:
                # Crear nuevo
                client_repo.create(client_data)
                imported.append({'type': 'simple_queue', 'name': name, 'action': 'created'})
                
        except Exception as e:
            logger.error(f"Error importing Simple Queue {queue.get('name')}: {e}")
            errors.append({'type': 'simple_queue', 'data': queue, 'error': str(e)})
    
    # Importar PPPoE Secrets
    for secret in pppoe_secrets:
        try:
            name = secret.get('name', '')
            remote_address = secret.get('remote_address', '')
            
            if not name:
                errors.append({'type': 'pppoe', 'data': secret, 'error': 'Sin nombre'})
                continue
            
            # Verificar duplicados
            is_duplicate = False
            if name.lower() in existing_usernames:
                is_duplicate = True
                if duplicate_strategy == 'skip':
                    skipped.append({'type': 'pppoe', 'name': name, 'reason': 'Username ya existe'})
                    continue
            
            # Crear o actualizar cliente
            subscriber_code = generate_subscriber_code() or name
            
            client_data = {
                'router_id': router_id,
                'subscriber_code': subscriber_code,
                'legal_name': name,
                'username': name,
                'password': secret.get('password', ''),
                'ip_address': remote_address,
                'monthly_fee': 70000.0 if router_id == 2 else 90000.0,
                'plan_name': secret.get('profile', '') or f"{secret.get('download_speed', '')} / {secret.get('upload_speed', '')}",
                'download_speed': secret.get('download_speed', ''),
                'upload_speed': secret.get('upload_speed', ''),
                'service_type': 'pppoe',
                'status': 'suspended' if secret.get('disabled') else 'active',
                'mikrotik_id': secret.get('mikrotik_id', ''),
            }
            
            if is_duplicate and duplicate_strategy == 'update':
                # Actualizar existente
                existing = existing_usernames.get(name.lower())
                if existing:
                    client_repo.update(existing.id, client_data)
                    imported.append({'type': 'pppoe', 'name': name, 'action': 'updated'})
            else:
                # Crear nuevo
                client_repo.create(client_data)
                imported.append({'type': 'pppoe', 'name': name, 'action': 'created'})
                
        except Exception as e:
            logger.error(f"Error importing PPPoE Secret {secret.get('name')}: {e}")
            errors.append({'type': 'pppoe', 'data': secret, 'error': str(e)})
    
    logger.info(f"Import completed for router {router_id}: {len(imported)} imported, {len(skipped)} skipped, {len(errors)} errors")
    
    return jsonify({
        'success': True,
        'imported': len(imported),
        'skipped': len(skipped),
        'errors': len(errors),
        'details': {
            'imported': imported,
            'skipped': skipped,
            'errors': errors
        },
        'message': f'Importación completada: {len(imported)} clientes importados, {len(skipped)} ignorados, {len(errors)} errores'
    })

# ==============================================================================
# NEW ENDPOINTS FOR ENHANCED DASHBOARD
# ==============================================================================

@routers_bp.route('/<int:router_id>/reboot', methods=['POST'])
@admin_required
def reboot_router(router_id):
    """Reinicia el router - DATOS REALES"""
    db = get_db()
    router_repo = db.get_router_repository()
    
    router = router_repo.get_by_id(router_id)
    if not router:
        return jsonify({'error': 'Router no encontrado'}), 404
        
    adapter = MikroTikAdapter()
    try:
        if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
            success = adapter.reboot_system()
            adapter.disconnect()
            
            if success:
                logger.warning(f"Router {router.alias} is rebooting...")
                
                # Auditoría de reinicio
                AuditService.log(
                    operation='router_reboot',
                    category='router',
                    entity_type='router',
                    entity_id=router_id,
                    description=f"Reinicio comandado para router {router.alias}"
                )
                
                return jsonify({'success': True, 'message': 'Comando de reinicio enviado. El router se reiniciará en breve.'})
            else:
                return jsonify({'success': False, 'message': 'No se pudo enviar el comando de reinicio'}), 200
        else:
            return jsonify({'success': False, 'message': 'No se pudo conectar al router'}), 200
            
    except Exception as e:
        logger.error(f"Error rebooting router: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@routers_bp.route('/<int:router_id>/interfaces', methods=['GET'])
@admin_required
def get_router_interfaces(router_id):
    """Obtiene lista de interfaces del router"""
    db = get_db()
    router_repo = db.get_router_repository()
    
    router = router_repo.get_by_id(router_id)
    if not router:
        return jsonify({'error': 'Router no encontrado'}), 404
        
    adapter = MikroTikAdapter()
    try:
        if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
            interfaces = adapter.get_interfaces()
            adapter.disconnect()
            
            # Integrar preferencias guardadas
            import json
            prefs = {}
            if router.monitored_interfaces:
                try:
                    prefs = json.loads(router.monitored_interfaces)
                except:
                    pass
            
            for iface in interfaces:
                iface_prefs = prefs.get(iface['name'], {})
                iface['monitored'] = iface_prefs.get('modal', False)
                iface['on_dashboard'] = iface_prefs.get('dashboard', False)
                
            return jsonify(interfaces)
        else:
            return jsonify([]), 200
    except Exception as e:
        logger.error(f"Error getting interfaces: {e}")
        return jsonify([]), 200

@routers_bp.route('/<int:router_id>/logs', methods=['GET'])
@admin_required
def get_router_logs(router_id):
    """Obtiene logs recientes del router"""
    db = get_db()
    router_repo = db.get_router_repository()
    
    router = router_repo.get_by_id(router_id)
    if not router:
        return jsonify({'error': 'Router no encontrado'}), 404
        
    limit = request.args.get('limit', 50, type=int)
    adapter = MikroTikAdapter()
    try:
        if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
            logs = adapter.get_logs(limit=limit)
            adapter.disconnect()
            return jsonify(logs)
        else:
            return jsonify([]), 200
    except Exception as e:
        logger.error(f"Error getting logs API: {e}")
        return jsonify([]), 200

@routers_bp.route('/<int:router_id>/interface/<path:interface_name>/traffic', methods=['GET'])
@login_required
def get_interface_traffic(router_id, interface_name):
    """Obtiene tráfico de una interfaz específica"""
    db = get_db()
    router_repo = db.get_router_repository()
    
    router = router_repo.get_by_id(router_id)
    if not router:
        return jsonify({'error': 'Router no encontrado'}), 404
        
    adapter = MikroTikAdapter()
    try:
        # Timeout corto para tráfico tiempo real
        if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port, timeout=5):
            traffic = adapter.get_interface_traffic(interface_name)
            adapter.disconnect()
            return jsonify(traffic)
        else:
            return jsonify({'rx': 0, 'tx': 0, 'error': 'Connection failed'}), 200 # Return 0s to not break graph
    except Exception as e:
        logger.error(f"Error getting traffic: {e}")
        return jsonify({'rx': 0, 'tx': 0, 'error': str(e)}), 200

@routers_bp.route('/<int:router_id>/monitoring-preferences', methods=['POST'])
@admin_required
def save_monitoring_preferences(router_id):
    """Guarda las preferencias de monitoreo de interfaces del router"""
    db = get_db()
    router_repo = db.get_router_repository()
    
    router = router_repo.get_by_id(router_id)
    if not router:
        return jsonify({'error': 'Router no encontrado'}), 404
        
    data = request.get_json()
    preferences = data.get('preferences', {})
    
    import json
    try:
        # Validar que sea un dict serializable
        prefs_json = json.dumps(preferences)
        router_repo.update(router_id, {'monitored_interfaces': prefs_json})
        
        # Auditoría
        AuditService.log(
            operation='router_monitoring_updated',
            category='router',
            entity_type='router',
            entity_id=router_id,
            description=f"Preferencias de monitoreo de interfaces actualizadas para {router.alias}",
            new_state=preferences
        )
        
        return jsonify({'success': True, 'message': 'Preferencias guardadas correctamente'})
    except Exception as e:
        logger.error(f"Error saving monitoring preferences: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
@routers_bp.route('/<int:router_id>/clients/export', methods=['GET'])
@login_required
def export_router_clients(router_id):
    """Exporta el listado de clientes de un router a PDF o Excel"""
    format_type = request.args.get('format', 'pdf').lower()
    
    db = get_db()
    router = db.get_router_repository().get_by_id(router_id)
    if not router:
        return jsonify({'error': 'Router no encontrado'}), 404
        
    clients = db.get_client_repository().get_by_router(router_id)
    
    # Convertir a dicts con campos requeridos por el reporte
    client_list = []
    for c in clients:
        client_list.append({
            'subscriber_code': c.subscriber_code,
            'legal_name': c.legal_name,
            'dni': c.identity_document,
            'ip_address': c.ip_address,
            'phone': c.phone,
            'plan_name': c.plan_name,
            'status': c.status
        })
    
    # Ordenar alfabéticamente
    client_list.sort(key=lambda x: x['legal_name'].lower())
    
    from src.application.services.report_service import ReportService
    from flask import send_file
    
    report_service = ReportService()
    
    if format_type == 'excel':
        output = report_service.generate_clients_excel(client_list, router.alias)
        filename = f"Clientes_{router.alias}_{datetime.now().strftime('%Y%m%d')}.xlsx"
        mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    else:
        output = report_service.generate_clients_pdf(client_list, router.alias)
        filename = f"Clientes_{router.alias}_{datetime.now().strftime('%Y%m%d')}.pdf"
        mimetype = 'application/pdf'
        
    return send_file(
        output,
        mimetype=mimetype,
        as_attachment=True,
        download_name=filename
    )

@routers_bp.route('/dashboard/monitored-traffic', methods=['GET'])
@login_required
def get_dashboard_monitored_traffic():
    """Obtiene el tráfico acumulado de todas las interfaces marcadas para el dashboard"""
    db = get_db()
    router_repo = db.get_router_repository()
    routers = router_repo.get_all()
    
    import json
    total_rx = 0
    total_tx = 0
    details = []
    
    adapter = MikroTikAdapter()
    
    for router in routers:
        if not router.monitored_interfaces:
            continue
            
        try:
            prefs = json.loads(router.monitored_interfaces)
            # Buscar interfaces marcadas para dashboard
            dashboard_ifaces = [name for name, p in prefs.items() if p.get('dashboard', False)]
            
            if dashboard_ifaces:
                if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port, timeout=3):
                    for iface_name in dashboard_ifaces:
                        traffic = adapter.get_interface_traffic(iface_name)
                        total_rx += traffic.get('rx', 0)
                        total_tx += traffic.get('tx', 0)
                        details.append({
                            'router': router.alias,
                            'interface': iface_name,
                            'rx': traffic.get('rx', 0),
                            'tx': traffic.get('tx', 0)
                        })
                    adapter.disconnect()
        except Exception as e:
            logger.error(f"Error fetching dashboard traffic for router {router.alias}: {e}")
            
    return jsonify({
        'total_rx': total_rx,
        'total_tx': total_tx,
        'details': details,
        'timestamp': datetime.utcnow().isoformat()
    })
