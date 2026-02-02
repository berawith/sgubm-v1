"""
Routers API Controller - DATOS REALES
Endpoints CRUD para gestión de routers con sincronización MikroTik
"""
from flask import Blueprint, jsonify, request
from datetime import datetime
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.mikrotik.adapter import MikroTikAdapter
import logging

logger = logging.getLogger(__name__)

routers_bp = Blueprint('routers', __name__, url_prefix='/api/routers')


@routers_bp.route('', methods=['GET'])
def get_routers():
    """
    Obtiene listado de todos los routers - DATOS REALES
    """
    db = get_db()
    router_repo = db.get_router_repository()
    
    routers = router_repo.get_all()
    return jsonify([r.to_dict() for r in routers])


@routers_bp.route('/<int:router_id>', methods=['GET'])
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
def create_router():
    """
    Crea un nuevo router - DATOS REALES
    """
    data = request.json
    
    db = get_db()
    router_repo = db.get_router_repository()
    
    try:
        router = router_repo.create(data)
        logger.info(f"Router creado: {router.alias}")
        return jsonify(router.to_dict()), 201
    except Exception as e:
        logger.error(f"Error creating router: {str(e)}")
        return jsonify({'error': str(e)}), 400


@routers_bp.route('/<int:router_id>', methods=['PUT'])
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
    
    logger.info(f"Router actualizado: {router.alias}")
    return jsonify(router.to_dict())


@routers_bp.route('/<int:router_id>', methods=['DELETE'])
def delete_router(router_id):
    """
    Elimina un router - DATOS REALES
    """
    db = get_db()
    router_repo = db.get_router_repository()
    
    success = router_repo.delete(router_id)
    if not success:
        return jsonify({'error': 'Router no encontrado'}), 404
    
    logger.info(f"Router eliminado: ID {router_id}")
    return jsonify({'message': 'Router eliminado correctamente'}), 200


@routers_bp.route('/<int:router_id>/test-connection', methods=['POST'])
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
            }), 400
            
    except Exception as e:
        logger.error(f"Error testing connection: {str(e)}")
        router_repo.update(router_id, {'status': 'offline'})
        return jsonify({
            'success': False,
            'message': f'Error de conexión: {str(e)}'
        }), 400


@routers_bp.route('/<int:router_id>/sync', methods=['POST'])
def sync_router(router_id):
    """
    Sincroniza la configuración y métricas del router - SINCRONIZACIÓN REAL
    """
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
            }), 400

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
        
        # Contar clientes en BD
        clients_in_db = len(client_repo.get_by_router(router_id))
        
        adapter.disconnect()
        
        logger.info(f"Router sincronizado: {router.alias}")
        
        return jsonify({
            'success': True,
            'message': 'Sincronización completada',
            'details': {
                'methods_detected': config['methods'],
                'clients_in_db': clients_in_db,
                'system_info': config['system_info']
            }
        })
        
    except Exception as e:
        logger.error(f"Error syncing router: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error de sincronización: {str(e)}'
        }), 400


@routers_bp.route('/sync-all', methods=['POST'])
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
def monitor_routers():
    """
    Obtiene métricas en tiempo real de todos los routers (Live Monitor)
    Usa hilos para consultar en paralelo y ser rápido.
    """
    db = get_db()
    router_repo = db.get_router_repository()
    routers = router_repo.get_all()
    
    import concurrent.futures
    
    def fetch_router_metrics(router):
        try:
            adapter = MikroTikAdapter()
            connected = adapter.connect(
                host=router.host_address,
                username=router.api_username,
                password=router.api_password,
                port=router.api_port,
                timeout=3 # Timeout corto (3s)
            )
            
            if not connected:
                return {
                    'id': router.id,
                    'status': 'offline',
                    'uptime': 'N/A',
                    'cpu_usage': 0,
                    'memory_usage': 0,
                    'clients_connected': 0
                }
                
            try:
                # Obtener recursos rápidos
                res_list = adapter._api_connection.get_resource('/system/resource').get()
                cpu = 0
                mem = 0
                uptime = 'N/A'
                
                if res_list:
                    res = res_list[0]
                    cpu = int(res.get('cpu-load', 0))
                    total = int(res.get('total-memory', 1))
                    free = int(res.get('free-memory', 0))
                    mem = int(((total - free)/total)*100)
                    uptime = res.get('uptime', 'N/A')
                
                # Obtener clientes (solo pppoe)
                active = 0
                try:
                    ppp = adapter._api_connection.get_resource('/ppp/active').get()
                    active += len(ppp) if ppp else 0
                    # Hotspot opcional si no es muy lento
                    hs = adapter._api_connection.get_resource('/ip/hotspot/active').get()
                    active += len(hs) if hs else 0
                except:
                    pass
                    
                adapter.disconnect()
                
                # Devolver datos reales
                return {
                    'id': router.id,
                    'status': 'online',
                    'uptime': uptime,
                    'cpu_usage': cpu,
                    'memory_usage': mem,
                    'clients_connected': active
                }
                
            except Exception as e:
                adapter.disconnect()
                return {'id': router.id, 'status': 'offline', 'error': str(e)}
                
        except Exception as e:
            return {'id': router.id, 'status': 'offline', 'error': str(e)}

    # Ejecutar en paralelo (max 10 routers a la vez)
    results = []
    if routers:
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(fetch_router_metrics, r) for r in routers]
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())
    
    return jsonify(results)
