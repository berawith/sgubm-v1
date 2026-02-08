"""
Payments API Controller - DATOS REALES
Endpoints para gestión y contabilidad de pagos
"""
from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
from src.infrastructure.database.db_manager import get_db
import logging

logger = logging.getLogger(__name__)

payments_bp = Blueprint('payments', __name__, url_prefix='/api/payments')


@payments_bp.route('', methods=['GET'])
def get_payments():
    """
    Obtiene listado de pagos con filtros - DATOS REALES
    """
    db = get_db()
    payment_repo = db.get_payment_repository()
    
    # Filtros opcionales
    client_id = request.args.get('client_id', type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    limit = request.args.get('limit', default=100, type=int)
    
    if client_id:
        payments = payment_repo.get_by_client(client_id)
    elif start_date and end_date:
        start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        payments = payment_repo.get_by_date_range(start, end)
    else:
        payments = payment_repo.get_all(limit=limit)
    
    return jsonify([p.to_dict() for p in payments])


@payments_bp.route('/<int:payment_id>', methods=['GET'])
def get_payment(payment_id):
    """
    Obtiene un pago específico
    """
    db = get_db()
    payment_repo = db.get_payment_repository()
    
    payment = payment_repo.get_by_id(payment_id)
    if not payment:
        return jsonify({'error': 'Pago no encontrado'}), 404
    
    return jsonify(payment.to_dict())


@payments_bp.route('', methods=['POST'])
def create_payment():
    """
    Registra un nuevo pago
    """
    data = request.json
    
    db = get_db()
    payment_repo = db.get_payment_repository()
    client_repo = db.get_client_repository()
    
    # Verificar que el cliente existe
    client_id = data.get('client_id')
    client = client_repo.get_by_id(client_id)
    if not client:
        return jsonify({'error': 'Cliente no encontrado'}), 404
    
    try:
        payment = payment_repo.create(data)
        
        # Actualizar balance del cliente
        client_repo.update_balance(client_id, payment.amount, operation='add')
        
        # Actualizar fecha de último pago
        client_repo.update(client_id, {
            'last_payment_date': payment.payment_date
        })
        
        logger.info(f"Pago registrado: ID {payment.id} - Cliente {client.legal_name} - ${payment.amount}")
        
        return jsonify(payment.to_dict()), 201
    except Exception as e:
        logger.error(f"Error creating payment: {str(e)}")
        return jsonify({'error': str(e)}), 400


@payments_bp.route('/<int:payment_id>', methods=['PUT'])
def update_payment(payment_id):
    """
    Actualiza un pago existente
    """
    data = request.json
    
    db = get_db()
    payment_repo = db.get_payment_repository()
    
    payment = payment_repo.update(payment_id, data)
    if not payment:
        return jsonify({'error': 'Pago no encontrado'}), 404
    
    logger.info(f"Pago actualizado: ID {payment_id}")
    return jsonify(payment.to_dict())


@payments_bp.route('/<int:payment_id>', methods=['DELETE'])
def delete_payment(payment_id):
    """
    Elimina un pago
    """
    db = get_db()
    payment_repo = db.get_payment_repository()
    client_repo = db.get_client_repository()
    
    payment = payment_repo.get_by_id(payment_id)
    if not payment:
        return jsonify({'error': 'Pago no encontrado'}), 404
    
    # Actualizar balance del cliente (restar el pago que se elimina)
    client_repo.update_balance(payment.client_id, payment.amount, operation='subtract')
    
    # Eliminar pago
    success = payment_repo.delete(payment_id)
    
    logger.info(f"Pago eliminado: ID {payment_id}")
    return jsonify({'message': 'Pago eliminado correctamente'}), 200


@payments_bp.route('/today', methods=['GET'])
def get_today_payments():
    """
    Obtiene pagos del día actual
    """
    db = get_db()
    payment_repo = db.get_payment_repository()
    
    payments = payment_repo.get_today_payments()
    total = sum(p.amount for p in payments)
    
    return jsonify({
        'payments': [p.to_dict() for p in payments],
        'count': len(payments),
        'total': total
    })


@payments_bp.route('/statistics', methods=['GET'])
def get_statistics():
    """
    Obtiene estadísticas y contabilidad de pagos
    """
    db = get_db()
    payment_repo = db.get_payment_repository()
    
    # Definir rangos de tiempo
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=now.weekday())
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Calcular totales
    today_total = payment_repo.get_total_by_date_range(today_start, now)
    week_total = payment_repo.get_total_by_date_range(week_start, now)
    month_total = payment_repo.get_total_by_date_range(month_start, now)
    year_total = payment_repo.get_total_by_date_range(year_start, now)
    
    # Pagos recientes
    recent_payments = payment_repo.get_all(limit=10)
    
    # Métodos de pago más usados
    all_payments = payment_repo.get_by_date_range(month_start, now)
    payment_methods = {}
    for payment in all_payments:
        method = payment.payment_method or 'unknown'
        if method not in payment_methods:
            payment_methods[method] = {'count': 0, 'total': 0}
        payment_methods[method]['count'] += 1
        payment_methods[method]['total'] += payment.amount
    
    return jsonify({
        'totals': {
            'today': today_total,
            'week': week_total,
            'month': month_total,
            'year': year_total
        },
        'counts': {
            'today': len(payment_repo.get_by_date_range(today_start, now)),
            'week': len(payment_repo.get_by_date_range(week_start, now)),
            'month': len(all_payments),
            'year': len(payment_repo.get_by_date_range(year_start, now))
        },
        'payment_methods': payment_methods,
        'recent_payments': [p.to_dict() for p in recent_payments[:5]]
    })


@payments_bp.route('/report', methods=['POST'])
def generate_report():
    """
    Genera reporte de pagos para un rango de fechas
    """
    data = request.json
    
    db = get_db()
    payment_repo = db.get_payment_repository()
    
    start_date = datetime.fromisoformat(data['start_date'].replace('Z', '+00:00'))
    end_date = datetime.fromisoformat(data['end_date'].replace('Z', '+00:00'))
    
    payments = payment_repo.get_by_date_range(start_date, end_date)
    
    total = sum(p.amount for p in payments)
    
    # Agrupar por día
    daily_totals = {}
    for payment in payments:
        day = payment.payment_date.strftime('%Y-%m-%d')
        if day not in daily_totals:
            daily_totals[day] = {'count': 0, 'total': 0, 'payments': []}
        daily_totals[day]['count'] += 1
        daily_totals[day]['total'] += payment.amount
        daily_totals[day]['payments'].append(payment.to_dict())
    
    # Agrupar por método
    by_method = {}
    for payment in payments:
        method = payment.payment_method or 'unknown'
        if method not in by_method:
            by_method[method] = {'count': 0, 'total': 0}
        by_method[method]['count'] += 1
        by_method[method]['total'] += payment.amount
    
    return jsonify({
        'period': {
            'start': start_date.isoformat(),
            'end': end_date.isoformat()
        },
        'summary': {
            'total_payments': len(payments),
            'total_amount': total,
            'average_payment': total / len(payments) if payments else 0
        },
        'daily_breakdown': daily_totals,
        'by_payment_method': by_method,
        'all_payments': [p.to_dict() for p in payments]
    })


@payments_bp.route('/balance-summary', methods=['GET'])
def balance_summary():
    """
    Resumen de balances de todos los clientes
    """
    db = get_db()
    client_repo = db.get_client_repository()
    
    clients = client_repo.get_all()
    
    total_balance = sum(c.account_balance for c in clients)
    clients_with_positive = len([c for c in clients if c.account_balance > 0])
    clients_with_negative = len([c for c in clients if c.account_balance < 0])
    clients_with_zero = len([c for c in clients if c.account_balance == 0])
    
    return jsonify({
        'total_clients': len(clients),
        'total_balance': total_balance,
        'clients_with_credit': clients_with_positive,
        'clients_with_debt': clients_with_negative,
        'clients_balanced': clients_with_zero,
        'average_balance': total_balance / len(clients) if clients else 0
    })
