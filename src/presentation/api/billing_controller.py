from flask import Blueprint, jsonify, request
from src.application.services.billing_service import BillingService
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Invoice, Client
import logging
from sqlalchemy import desc

billing_bp = Blueprint('billing', __name__)
logger = logging.getLogger(__name__)

# Instancia del servicio
billing_service = BillingService()

@billing_bp.route('/api/billing/run-cycle', methods=['POST'])
def run_billing_cycle():
    """Ejecutar ciclo completo (Facturación + Cortes) con filtros"""
    try:
        data = request.json or {}
        router_id = data.get('router_id')
        client_ids = data.get('client_ids')
        year = data.get('year')
        month = data.get('month')
        
        # El servicio ya está instanciado como billing_service
        billing_service.process_daily_cycle(router_id=router_id, client_ids=client_ids, year=year, month=month)
        
        return jsonify({
            'success': True,
            'message': 'Ciclo de facturación iniciado'
        }), 200
        
    except Exception as e:
        logger.error(f"Error running billing cycle: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@billing_bp.route('/api/billing/generate', methods=['POST'])
def generate_invoices():
    """Generar facturas masivas para el mes actual"""
    try:
        data = request.json or {}
        year = data.get('year')
        month = data.get('month')
        router_id = data.get('router_id')
        client_ids = data.get('client_ids')
        
        result = billing_service.generate_monthly_invoices(year, month, router_id=router_id, client_ids=client_ids)
        
        return jsonify({
            'message': 'Proceso de facturación finalizado',
            'details': result
        }), 200
        
    except Exception as e:
        logger.error(f"Error generating invoices: {e}")
        return jsonify({'error': str(e)}), 500

@billing_bp.route('/api/billing/invoices', methods=['GET'])
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
        return jsonify({'error': str(e)}), 500

@billing_bp.route('/api/billing/invoices/<int:invoice_id>', methods=['GET'])
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
        return jsonify({'error': str(e)}), 500
@billing_bp.route('/api/billing/invoices/<int:invoice_id>/print', methods=['GET'])
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
