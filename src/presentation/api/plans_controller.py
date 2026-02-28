from flask import Blueprint, jsonify, request, render_template
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import InternetPlan, Client, Router
from src.infrastructure.mikrotik.adapter import MikroTikAdapter
from src.application.services.audit_service import AuditService
from src.application.services.auth import login_required, admin_required
from sqlalchemy.exc import IntegrityError
import logging

plans_bp = Blueprint('plans', __name__, 
                    template_folder='../web/templates',
                    static_folder='../web/static')

logger = logging.getLogger(__name__)

def sync_plan_to_routers(plan, db):
    """Propaga el plan a los routers MikroTik correspondientes"""
    routers = []
    if plan.router_id:
        router = db.session.query(Router).get(plan.router_id)
        if router: routers = [router]
    else:
        # Plan Global: Todos los routers online
        routers = db.session.query(Router).filter(Router.status == 'online').all()
    
    if not routers:
        return
        
    adapter = MikroTikAdapter()
    for router in routers:
        try:
            # Best effort sync
            if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port, timeout=3):
                if plan.service_type == 'pppoe':
                    profile_name = plan.mikrotik_profile or plan.name
                    # MikroTik format: TX/RX (Upload/Download)
                    rate_limit = f"{plan.upload_speed}k/{plan.download_speed}k"
                    adapter.create_ppp_profile(
                        name=profile_name, 
                        rate_limit=rate_limit,
                        local_address=plan.local_address,
                        remote_address=plan.remote_address
                    )
                elif plan.service_type == 'simple_queue':
                    # Podríamos implementar creación de Queue Types aquí si se desea
                    pass
                adapter.disconnect()
        except Exception as e:
            logger.error(f"Error syncing plan {plan.name} to {router.alias}: {e}")

@plans_bp.route('/plans-manager', methods=['GET'])
@admin_required
def plans_manager_view():
    """Vista principal del Gestor de Planes"""
    return render_template('modules/plans_manager.html')

@plans_bp.route('/api/plans', methods=['GET'])
@login_required
def get_plans():
    """Obtener todos los planes"""
    db = get_db()
    try:
        plans = db.session.query(InternetPlan).all()
        
        # Contar clientes por plan
        result = []
        for p in plans:
            count = db.session.query(Client).filter(Client.plan_id == p.id).count()
            data = p.to_dict()
            data['clients_count'] = count
            result.append(data)
            
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error fetching plans: {e}")
        return jsonify({'error': str(e)}), 500

@plans_bp.route('/api/plans', methods=['POST'])
@admin_required
def create_plan():
    """Crear nuevo plan (y opcionalmente Profile en MikroTik)"""
    data = request.json
    db = get_db()
    
    try:
        new_plan = InternetPlan(
            name=data.get('name'),
            download_speed=data.get('download_speed'),
            upload_speed=data.get('upload_speed'),
            monthly_price=data.get('monthly_price'),
            currency=data.get('currency', 'COP'),
            service_type=data.get('service_type', 'pppoe'),
            mikrotik_profile=data.get('mikrotik_profile'),
            router_id=data.get('router_id'),
            burst_limit=data.get('burst_limit'),
            priority=data.get('priority', 8),
            local_address=data.get('local_address'),
            remote_address=data.get('remote_address')
        )
        
        db.session.add(new_plan)
        db.session.commit()
        
        # Propagar a MikroTik
        sync_plan_to_routers(new_plan, db)
        
        # Auditoría
        AuditService.log(
            operation='plan_created',
            category='system',
            entity_type='plan',
            entity_id=new_plan.id,
            description=f"Nuevo plan de internet creado: {new_plan.name} (${new_plan.monthly_price})",
            new_state=new_plan.to_dict()
        )
        
        return jsonify({'message': 'Plan creado y propagado exitosamente', 'plan': new_plan.to_dict()}), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating plan: {e}")
        return jsonify({'error': str(e)}), 500

@plans_bp.route('/api/plans/<int:plan_id>', methods=['PUT'])
@admin_required
def update_plan(plan_id):
    """Actualizar plan"""
    data = request.json
    db = get_db()
    
    try:
        plan = db.session.query(InternetPlan).get(plan_id)
        if not plan:
            return jsonify({'error': 'Plan no encontrado'}), 404
            
        plan.name = data.get('name', plan.name)
        plan.download_speed = data.get('download_speed', plan.download_speed)
        plan.upload_speed = data.get('upload_speed', plan.upload_speed)
        plan.monthly_price = data.get('monthly_price', plan.monthly_price)
        plan.mikrotik_profile = data.get('mikrotik_profile', plan.mikrotik_profile)
        plan.router_id = data.get('router_id', plan.router_id)
        plan.local_address = data.get('local_address', plan.local_address)
        plan.remote_address = data.get('remote_address', plan.remote_address)
        
        db.session.commit()
        
        # Helper para formatear velocidades
        def format_speed(kb):
            if not kb: return "0"
            if kb >= 1000: return f"{kb//1000}M"
            return f"{kb}k"

        # Propagar cambios a todos los clientes que usan este plan
        clients = db.session.query(Client).filter(Client.plan_id == plan.id).all()
        from src.application.services.sync_service import SyncService
        sync_service = SyncService(db)
        
        for c in clients:
            c.plan_name = plan.name
            c.monthly_fee = plan.monthly_price
            c.download_speed = format_speed(plan.download_speed)
            c.upload_speed = format_speed(plan.upload_speed)
            c.service_type = plan.service_type
            
            # Encolar Sincronización
            if c.router_id:
                sync_service.queue_operation(
                    client_id=c.id,
                    router_id=c.router_id,
                    operation_type='update',
                    operation_data={'old_username': c.username, 'data': c.to_dict()}
                )
        
        db.session.commit() # Commit client changes
        
        # Propagar cambios a MikroTik (Perfiles)
        sync_plan_to_routers(plan, db)
        
        # Auditoría
        AuditService.log(
            operation='plan_updated',
            category='system',
            entity_type='plan',
            entity_id=plan_id,
            description=f"Plan de internet actualizado: {plan.name}",
            new_state=data
        )
        
        return jsonify({'message': 'Plan actualizado y propagado', 'plan': plan.to_dict()}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating plan {plan_id}: {e}")
        return jsonify({'error': str(e)}), 500

@plans_bp.route('/api/plans/<int:plan_id>', methods=['DELETE'])
@admin_required
def delete_plan(plan_id):
    """Eliminar plan (Solo si no tiene clientes)"""
    db = get_db()
    try:
        # Verificar clientes
        count = db.session.query(Client).filter(Client.plan_id == plan_id).count()
        if count > 0:
            return jsonify({'error': f'No se puede eliminar: tiene {count} clientes asignados'}), 400
            
        plan = db.session.query(InternetPlan).get(plan_id)
        if not plan:
            return jsonify({'error': 'Plan no encontrado'}), 404
            
        plan_name = plan.name
        db.session.delete(plan)
        db.session.commit()
        
        # Auditoría
        AuditService.log(
            operation='plan_deleted',
            category='system',
            entity_type='plan',
            entity_id=plan_id,
            description=f"Plan de internet eliminado: {plan_name}"
        )
        
        return jsonify({'message': 'Plan eliminado'}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting plan {plan_id}: {e}")
        return jsonify({'error': str(e)}), 500
