"""
Sync API Controller - Gestión de operaciones pendientes y sincronización
"""
from flask import Blueprint, jsonify, request
from src.infrastructure.database.db_manager import get_db
from src.application.services.sync_service import SyncService
from src.application.services.mikrotik_operations import trigger_sync_if_online
from src.application.services.auth import admin_required, permission_required
from sqlalchemy import func
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

sync_bp = Blueprint('sync', __name__, url_prefix='/api/sync')


@sync_bp.route('/pending', methods=['GET'])
@permission_required('routers:monitoring', 'view')
def get_pending_operations():
    """Obtiene todas las operaciones pendientes"""
    try:
        db = get_db()
        sync_service = SyncService(db)
        
        router_id = request.args.get('router_id', type=int)
        operations = sync_service.get_pending_operations(router_id)
        
        return jsonify({
            'success': True,
            'operations': [op.to_dict() for op in operations],
            'total': len(operations)
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo operaciones pendientes: {e}")
        return jsonify({'error': str(e)}), 500


@sync_bp.route('/pending/<int:operation_id>', methods=['DELETE'])
@permission_required('routers:monitoring', 'delete')
def cancel_pending_operation(operation_id):
    """Cancela una operación pendiente"""
    try:
        db = get_db()
        session = db.session
        
        from src.infrastructure.database.models import PendingOperation
        operation = session.query(PendingOperation).get(operation_id)
        
        if not operation:
            return jsonify({'error': 'Operación no encontrada'}), 404
        
        session.delete(operation)
        session.commit()
        session.close()
        
        logger.info(f"✅ Operación pendiente {operation_id} cancelada")
        
        return jsonify({
            'success': True,
            'message': 'Operación cancelada'
        })
        
    except Exception as e:
        logger.error(f"Error cancelando operación: {e}")
        return jsonify({'error': str(e)}), 500


@sync_bp.route('/stats', methods=['GET'])
@permission_required('routers:monitoring', 'view')
def get_sync_stats():
    """Obtiene estadísticas de sincronización"""
    try:
        db = get_db()
        session = db.session
        
        from src.infrastructure.database.models import PendingOperation
        
        # Estadísticas generales
        total_pending = session.query(PendingOperation).filter(
            PendingOperation.status == 'pending'
        ).count()
        
        total_completed = session.query(PendingOperation).filter(
            PendingOperation.status == 'completed'
        ).count()
        
        total_failed = session.query(PendingOperation).filter(
            PendingOperation.status == 'failed'
        ).count()
        
        # Por router
        by_router = session.query(
            PendingOperation.router_id,
            PendingOperation.status,
            func.count(PendingOperation.id).label('count')
        ).group_by(
            PendingOperation.router_id,
            PendingOperation.status
        ).all()
        
        router_stats = {}
        for router_id, status, count in by_router:
            if router_id not in router_stats:
                router_stats[router_id] = {'pending': 0, 'completed': 0, 'failed': 0}
            router_stats[router_id][status] = count
        
        # Últimas 24 horas
        yesterday = datetime.now() - timedelta(days=1)
        recent_completed = session.query(PendingOperation).filter(
            PendingOperation.status == 'completed',
            PendingOperation.last_attempt >= yesterday
        ).count()
        
        recent_failed = session.query(PendingOperation).filter(
            PendingOperation.status == 'failed',
            PendingOperation.last_attempt >= yesterday
        ).count()
        
        session.close()
        
        return jsonify({
            'success': True,
            'stats': {
                'total_pending': total_pending,
                'total_completed': total_completed,
                'total_failed': total_failed,
                'by_router': {str(k): v for k, v in router_stats.items()},
                'last_24h': {
                    'completed': recent_completed,
                    'failed': recent_failed
                }
            }
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas: {e}")
        return jsonify({'error': str(e)}), 500


@sync_bp.route('/force/<int:router_id>', methods=['POST'])
@permission_required('routers:monitoring', 'edit')
def force_sync(router_id):
    """Fuerza la sincronización de operaciones pendientes de un router"""
    try:
        db = get_db()
        router_repo = db.get_router_repository()
        
        router = router_repo.get_by_id(router_id)
        if not router:
            return jsonify({'error': 'Router no encontrado'}), 404
        
        if router.status != 'online':
            return jsonify({
                'success': False,
                'message': f'Router {router.alias} está offline',
                'router_status': router.status
            }), 400
        
        # Forzar sincronización
        result = trigger_sync_if_online(db, router)
        
        if result:
            return jsonify({
                'success': True,
                'message': f"Sincronización completada para {router.alias}",
                'result': result
            })
        else:
            return jsonify({
                'success': False,
                'message': 'No se pudo sincronizar'
            })
        
    except Exception as e:
        logger.error(f"Error forzando sincronización: {e}")
        return jsonify({'error': str(e)}), 500


@sync_bp.route('/force-all', methods=['POST'])
@permission_required('routers:monitoring', 'edit')
def force_sync_all():
    """Fuerza la sincronización de TODOS los routers online"""
    try:
        db = get_db()
        router_repo = db.get_router_repository()
        
        # Obtener todos los routers online
        routers = router_repo.get_all()
        online_routers = [r for r in routers if r.status == 'online']
        
        if not online_routers:
            return jsonify({
                'success': False,
                'message': 'No hay routers online para sincronizar'
            })
        
        results = []
        total_completed = 0
        total_failed = 0
        
        for router in online_routers:
            result = trigger_sync_if_online(db, router)
            if result:
                results.append({
                    'router_id': router.id,
                    'router_name': router.alias,
                    'completed': result.get('completed', 0),
                    'failed': result.get('failed', 0)
                })
                total_completed += result.get('completed', 0)
                total_failed += result.get('failed', 0)
        
        return jsonify({
            'success': True,
            'message': f'Sincronizados {len(online_routers)} routers',
            'total_completed': total_completed,
            'total_failed': total_failed,
            'details': results
        })
        
    except Exception as e:
        logger.error(f"Error en sincronización global: {e}")
        return jsonify({'error': str(e)}), 500


@sync_bp.route('/history', methods=['GET'])
@permission_required('routers:monitoring', 'view')
def get_sync_history():
    """Obtiene el historial de sincronizaciones (últimas 100)"""
    try:
        db = get_db()
        session = db.session
        
        from src.infrastructure.database.models import PendingOperation
        
        limit = request.args.get('limit', 100, type=int)
        router_id = request.args.get('router_id', type=int)
        
        query = session.query(PendingOperation).filter(
            PendingOperation.status.in_(['completed', 'failed'])
        )
        
        if router_id:
            query = query.filter(PendingOperation.router_id == router_id)
        
        history = query.order_by(
            PendingOperation.last_attempt.desc()
        ).limit(limit).all()
        
        session.close()
        
        return jsonify({
            'success': True,
            'history': [op.to_dict() for op in history],
            'count': len(history)
        })
        
    except Exception as e:
        logger.error(f"Error obteniendo historial: {e}")
        return jsonify({'error': str(e)}), 500
