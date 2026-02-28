from flask import Blueprint, jsonify, request
from src.application.services.billing_service import BillingService
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Invoice, Client
from src.application.services.auth import login_required, admin_required
import logging
from sqlalchemy import desc

billing_bp = Blueprint('billing', __name__)
logger = logging.getLogger(__name__)

# Instancia del servicio
billing_service = BillingService()

@billing_bp.route('/api/billing/run-cycle', methods=['POST'])
@admin_required
def run_billing_cycle():
    """Ejecutar ciclo completo (Facturación + Cortes) con filtros"""
    try:
        data = request.json or {}
        router_id = data.get('router_id')
        client_ids = data.get('client_ids')
        year = data.get('year')
        month = data.get('month')
        
        # Filtros Avanzados
        zone_names = data.get('zone_names')
        excluded_zones = data.get('excluded_zones')
        collector_ids = data.get('collector_ids')
        excluded_collectors = data.get('excluded_collectors')
        excluded_routers = data.get('excluded_routers')
        
        # El servicio ya está instanciado como billing_service
        billing_service.process_daily_cycle(
            router_id=router_id, 
            client_ids=client_ids, 
            year=year, 
            month=month,
            zone_names=zone_names,
            excluded_zones=excluded_zones,
            collector_ids=collector_ids,
            excluded_collectors=excluded_collectors,
            excluded_routers=excluded_routers
        )
        
        return jsonify({
            'success': True,
            'message': 'Ciclo de facturación iniciado'
        }), 200
        
    except Exception as e:
        logger.error(f"Error running billing cycle: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@billing_bp.route('/api/billing/generate', methods=['POST'])
@admin_required
def generate_invoices():
    """Generar facturas masivas para el mes actual"""
    try:
        data = request.json or {}
        year = data.get('year')
        month = data.get('month')
        router_id = data.get('router_id')
        client_ids = data.get('client_ids')
        
        # Filtros Avanzados
        zone_names = data.get('zone_names')
        excluded_zones = data.get('excluded_zones')
        collector_ids = data.get('collector_ids')
        excluded_collectors = data.get('excluded_collectors')
        excluded_routers = data.get('excluded_routers')
        
        result = billing_service.generate_monthly_invoices(
            year, month, 
            router_id=router_id, 
            client_ids=client_ids,
            zone_names=zone_names,
            excluded_zones=excluded_zones,
            collector_ids=collector_ids,
            excluded_collectors=excluded_collectors,
            excluded_routers=excluded_routers
        )
        
        return jsonify({
            'message': 'Proceso de facturación finalizado',
            'details': result
        }), 200
        
    except Exception as e:
        logger.error(f"Error generating invoices: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@billing_bp.route('/api/billing/invoices', methods=['GET'])
@login_required
def get_invoices():
    """Listar facturas con filtros"""
    db = get_db()
    
    try:
        client_id = request.args.get('client_id')
        status = request.args.get('status')
        search = request.args.get('search')
        limit = int(request.args.get('limit', 50))
        
        query = db.session.query(Invoice)
        
        if client_id:
            query = query.filter(Invoice.client_id == client_id)
        if status:
            query = query.filter(Invoice.status == status)
        
        if search:
            search_pattern = f"%{search}%"
            query = query.join(Client).filter(
                (Client.legal_name.ilike(search_pattern)) |
                (Client.subscriber_code.ilike(search_pattern))
            )
            
        # Ordenar por fecha de emisión descendente
        invoices = query.order_by(desc(Invoice.issue_date)).limit(limit).all()
        
        return jsonify([inv.to_dict() for inv in invoices]), 200
        
    except Exception as e:
        logger.error(f"Error fetching invoices: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@billing_bp.route('/api/billing/invoices/<int:invoice_id>', methods=['GET'])
@login_required
def get_invoice_detail(invoice_id):
    """Obtener detalle de una factura"""
    db = get_db()
    try:
        invoice = db.session.query(Invoice).get(invoice_id)
        if not invoice:
            return jsonify({'error': 'Factura no encontrada'}), 404
            
        return jsonify(invoice.to_dict()), 200
    except Exception as e:
        logger.error(f"Error fetching invoice {invoice_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
@billing_bp.route('/api/billing/invoices/<int:invoice_id>/print', methods=['GET'])
@login_required
def print_invoice(invoice_id):
    """Renderiza vista de impresión de factura"""
    from flask import render_template
    db = get_db()
    try:
        invoice = db.session.query(Invoice).get(invoice_id)
        if not invoice:
            return "Factura no encontrada", 404
            
        client = db.session.query(Client).get(invoice.client_id)
        
        return render_template('billing/invoice_print.html', invoice=invoice, client=client)
    except Exception as e:
        logger.error(f"Error printing invoice {invoice_id}: {e}")
        return str(e), 500

@billing_bp.route('/api/batch/execute', methods=['POST'])
@admin_required
def execute_batch_action():
    """Ejecutar accion masiva (suspend, restore, pay)"""
    from src.application.services.batch_service import BatchService
    try:
        data = request.json or {}
        action = data.get('action')
        client_ids = data.get('client_ids', [])
        extra_data = data.get('extra_data', {})
        
        if not action or not client_ids:
            return jsonify({'success': False, 'message': 'Missing action or client_ids'}), 400
            
        batch_service = BatchService()
        result = batch_service.execute_batch_action(action, client_ids, extra_data)
        
        return jsonify({
            'success': True,
            'message': f"Batch action {action} completed",
            'details': result
        }), 200
        
    except Exception as e:
        logger.error(f"Error executing batch action: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@billing_bp.route('/api/billing/notifications', methods=['GET'])
@admin_required
def get_billing_notifications():
    """Listar notificaciones de ciclo de facturación pendientes"""
    db = get_db()
    from src.infrastructure.database.models import SystemNotification
    try:
        notifications = db.session.query(SystemNotification).filter(
            SystemNotification.status == 'pending',
            SystemNotification.type == 'approval_required'
        ).all()
        return jsonify([n.to_dict() for n in notifications]), 200
    except Exception as e:
        logger.error(f"Error fetching notifications: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@billing_bp.route('/api/billing/notifications/<int:notif_id>/approve', methods=['POST'])
@admin_required
def approve_billing_cycle(notif_id):
    """Aprobar y ejecutar el ciclo de facturación"""
    db = get_db()
    from src.infrastructure.database.models import SystemNotification
    import json
    try:
        notif = db.session.query(SystemNotification).get(notif_id)
        if not notif or notif.status != 'pending':
            return jsonify({'success': False, 'message': 'Notificación no disponible'}), 404
            
        # Parsear datos del ciclo
        try:
            action_data = json.loads(notif.action_data)
        except:
            action_data = {}
            
        year = action_data.get('year')
        month = action_data.get('month')
        
        # Ejecutar facturación masiva
        success = billing_service.generate_monthly_invoices(year, month)
        
        if success:
            notif.status = 'accepted'
            db.session.commit()
            return jsonify({'success': True, 'message': 'Ciclo de facturación ejecutado con éxito'}), 200
        else:
            return jsonify({'success': False, 'message': 'Error al ejecutar la facturación'}), 500
            
    except Exception as e:
        logger.error(f"Error approving billing cycle: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@billing_bp.route('/api/billing/notifications/<int:notif_id>/reject', methods=['POST'])
@admin_required
def reject_billing_cycle(notif_id):
    """Rechazar ciclo y programar recordatorio"""
    db = get_db()
    from src.infrastructure.database.models import SystemNotification
    from datetime import datetime, timedelta
    try:
        notif = db.session.query(SystemNotification).get(notif_id)
        if not notif:
            return jsonify({'success': False, 'message': 'Notificación no encontrada'}), 404
            
        # El requerimiento dice: "se vuelve a notificar cada hora"
        # Mantenemos el status 'pending' pero movemos el 'remind_at'
        notif.remind_at = datetime.now() + timedelta(hours=1)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Recordatorio programado para dentro de 1 hora'
        }), 200
    except Exception as e:
        logger.error(f"Error rejecting billing cycle: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@billing_bp.route('/api/billing/settings', methods=['GET'])
@admin_required
def get_billing_settings():
    """Obtener configuraciones de facturación"""
    db = get_db()
    try:
        settings_repo = db.get_system_setting_repository()
        due_time = settings_repo.get_value('ERP_BILLING_DUE_TIME', '23:59')
        
        return jsonify({
            'success': True,
            'settings': {
                'billing_due_time': due_time
            }
        }), 200
    except Exception as e:
        logger.error(f"Error fetching billing settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@billing_bp.route('/api/billing/settings', methods=['POST'])
@admin_required
def update_billing_settings():
    """Actualizar configuraciones de facturación"""
    db = get_db()
    try:
        data = request.json or {}
        billing_due_time = data.get('billing_due_time')
        
        if billing_due_time:
            settings_repo = db.get_system_setting_repository()
            settings_repo.set_value(
                'ERP_BILLING_DUE_TIME', 
                billing_due_time,
                category='billing',
                description='Hora límite de vencimiento de facturas (HH:mm)'
            )
        
        return jsonify({
            'success': True,
            'message': 'Configuración de facturación actualizada'
        }), 200
    except Exception as e:
        logger.error(f"Error updating billing settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
