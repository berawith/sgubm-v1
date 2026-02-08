"""
Payments API Controller - DATOS REALES
Endpoints para gestión y contabilidad de pagos
"""
from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
from typing import List, Dict, Any
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import ClientStatus, PaymentStatus, Client
from src.application.services.audit_service import AuditService
import logging

logger = logging.getLogger(__name__)

payments_bp = Blueprint('payments', __name__, url_prefix='/api/payments')


@payments_bp.route('/<int:payment_id>/print', methods=['GET'])
def print_payment_receipt(payment_id):
    """
    Renderiza la vista de impresión de un recibo de pago
    """
    from flask import render_template
    db = get_db()
    payment_repo = db.get_payment_repository()
    client_repo = db.get_client_repository()
    
    payment = payment_repo.get_by_id(payment_id)
    if not payment:
        return "Pago no encontrado", 404
        
    client = client_repo.get_by_id(payment.client_id)
    
    return render_template('billing/receipt_print.html', payment=payment, client=client)


@payments_bp.route('', methods=['GET'])
def get_payments():
    """
    Obtiene listado de pagos con filtros - DATOS REALES
    """
    db = get_db()
    payment_repo = db.get_payment_repository()
    
    # Filtros obcionales
    client_id = request.args.get('client_id', type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    method = request.args.get('method')
    search = request.args.get('search')
    limit = request.args.get('limit', default=100, type=int)
    
    # Convertir fechas si existen
    start_dt = None
    end_dt = None
    
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        except ValueError:
            pass
            
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except ValueError:
            pass

    payments = payment_repo.get_filtered(
        client_id=client_id,
        start_date=start_dt,
        end_date=end_dt,
        method=method,
        search=search,
        limit=limit
    )
    
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
    Registra un nuevo pago - USA LOGICA CENTRALIZADA
    """
    data = request.json
    client_id = data.get('client_id')
    amount = float(data.get('amount', 0))
    
    if not client_id or amount <= 0:
        return jsonify({'error': 'ID de cliente o monto inválido'}), 400
        
    try:
        from src.application.services.billing_service import BillingService
        service = BillingService()
        
        # El servicio maneja: 
        # - Registro en tabla payments
        # - Actualización de balance
        # - Actualización de facturas (FIFO)
        # - Reactivación automática si corresponde
        # - Validación de no duplicidad (Problema 3)
        new_payment = service.register_payment(client_id, amount, data)
        
        # Obtener balance actualizado para la respuesta
        db = get_db()
        client = db.session.query(Client).get(client_id)
        
        return jsonify({
            'success': True, 
            'payment_id': new_payment.id,
            'new_balance': client.account_balance,
            'message': 'Pago registrado exitosamente'
        }), 201
        
    except ValueError as ve:
        # Errores de validación (como el de pago duplicado)
        return jsonify({'error': str(ve)}), 400
    except Exception as e:
        logger.error(f"Error creating payment: {str(e)}")
        return jsonify({'error': 'Error interno al procesar el pago'}), 500


@payments_bp.route('/<int:payment_id>', methods=['PUT'])
def update_payment(payment_id):
    """
    Actualiza un pago existente
    """
    data = request.json
    
    db = get_db()
    payment_repo = db.get_payment_repository()
    
    # 1. Filtrar y Sanitizar datos
    allowed_fields = ['amount', 'payment_method', 'reference', 'notes', 'payment_date', 'currency']
    update_data = {k: v for k, v in data.items() if k in allowed_fields}
    
    # 2. Convertir fechas
    if 'payment_date' in update_data and update_data['payment_date']:
        try:
            # Intentar formato completo ISO
            update_data['payment_date'] = datetime.fromisoformat(update_data['payment_date'].replace('Z', '+00:00'))
        except ValueError:
            try:
                # Intentar solo fecha YYYY-MM-DD
                update_data['payment_date'] = datetime.strptime(update_data['payment_date'], '%Y-%m-%d')
            except ValueError:
                return jsonify({'error': 'Formato de fecha inválido. Use ISO 8601 o YYYY-MM-DD'}), 400

    try:
        payment = payment_repo.update(payment_id, update_data)
        if not payment:
            return jsonify({'error': 'Pago no encontrado'}), 404
        
        # Auditoría de actualización
        AuditService.log(
            operation='payment_updated',
            category='accounting',
            entity_type='payment',
            entity_id=payment_id,
            description=f"Pago actualizado. Nuevos datos: {update_data}"
        )
        
        logger.info(f"Pago actualizado: ID {payment_id}")
        return jsonify(payment.to_dict())
        
    except Exception as e:
        logger.error(f"Error updating payment {payment_id}: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Error interno al actualizar el pago'}), 500


@payments_bp.route('/<int:payment_id>', methods=['DELETE'])
def delete_payment(payment_id):
    """
    Anula/Elimina un pago y lo mueve a la papelera (archiva)
    """
    db = get_db()
    payment_repo = db.get_payment_repository()
    deleted_repo = db.get_deleted_payment_repository()
    client_repo = db.get_client_repository()
    
    payment = payment_repo.get_by_id(payment_id)
    if not payment:
        return jsonify({'error': 'Pago no encontrado'}), 404
    
    reason = request.args.get('reason', 'Eliminación manual')
    
    try:
        # 1. Archivar en papelera
        deleted_repo.create_from_payment(payment, deleted_by='admin', reason=reason)
        
        # 2. Restaurar balance del cliente (sumar el pago eliminado)
        client_repo.update_balance(payment.client_id, payment.amount, operation='add')
        
        # 3. Eliminar pago original
        payment_repo.delete(payment_id)
        
        # 4. Auditoría
        AuditService.log(
            operation='payment_deleted_archived',
            category='accounting',
            entity_type='payment',
            entity_id=payment_id,
            description=f"Pago de ${payment.amount} ANULADO y movido a papelera. Cliente ID {payment.client_id}. Motivo: {reason}"
        )
        
        logger.info(f"Pago archivado y eliminado: ID {payment_id}")
        return jsonify({'message': 'Pago anulado y movido a papelera correctamente'}), 200
    except Exception as e:
        logger.error(f"Error deleting/archiving payment: {e}")
        return jsonify({'error': 'Error al procesar la anulación'}), 500


@payments_bp.route('/deleted', methods=['GET'])
def get_deleted_payments():
    """Obtiene lista de pagos eliminados"""
    db = get_db()
    deleted_repo = db.get_deleted_payment_repository()
    deleted = deleted_repo.get_all()
    return jsonify([d.to_dict() for d in deleted])


@payments_bp.route('/deleted/<int:deleted_id>/restore', methods=['POST'])
def restore_payment(deleted_id):
    """Restaura un pago desde la papelera"""
    db = get_db()
    deleted_repo = db.get_deleted_payment_repository()
    
    deleted = deleted_repo.get_by_id(deleted_id)
    if not deleted:
        return jsonify({'error': 'Registro en papelera no encontrado'}), 404
        
    try:
        from src.application.services.billing_service import BillingService
        service = BillingService()
        
        # El restore es básicamente re-registrar el pago
        data = {
            'payment_method': deleted.payment_method,
            'reference': deleted.reference,
            'notes': f"RESTAURADO (Original ID {deleted.original_id}): " + (deleted.notes or ""),
            'authorized': True # Forzar autorización ya que es una restauración
        }
        
        new_payment = service.register_payment(deleted.client_id, deleted.amount, data)
        
        # Eliminar de la papelera
        deleted_repo.delete(deleted_id)
        
        AuditService.log(
            operation='payment_restored',
            category='accounting',
            entity_type='payment',
            entity_id=new_payment.id,
            description=f"Pago restaurado desde papelera. Cliente ID {deleted.client_id}, Monto ${deleted.amount}"
        )
        
        return jsonify({
            'success': True,
            'message': 'Pago restaurado exitosamente',
            'new_payment_id': new_payment.id
        })
    except Exception as e:
        logger.error(f"Error restoring payment: {e}")
        return jsonify({'error': str(e)}), 500


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
    Soporta filtros opcionales para reportes personalizados
    """
    try:
        db = get_db()
        payment_repo = db.get_payment_repository()
        
        # Filtros opcionales
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        method_filter = request.args.get('method')
        
        # Definir rangos de tiempo base
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=now.weekday())
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Determinar rango activo para "Reporte Principal"
        report_start = month_start
        report_end = now
        
        if start_date_str:
            try:
                report_start = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
            except: pass
            
        if end_date_str:
            try:
                report_end = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                # Ajustar al final del día si no tiene hora
                if report_end.hour == 0 and report_end.minute == 0:
                     report_end = report_end.replace(hour=23, minute=59, second=59)
            except: pass

        # Calcular totales Fijos (Siempre útiles)
        today_total = payment_repo.get_total_by_date_range(today_start, now)
        week_total = payment_repo.get_total_by_date_range(week_start, now)
        month_total = payment_repo.get_total_by_date_range(month_start, now)
        year_total = payment_repo.get_total_by_date_range(year_start, now)
        all_time_total = payment_repo.get_total_by_date_range(datetime(2000, 1, 1), now)
        
        # Calcular total del periodo seleccionado (para la tarjeta "Este Mes" o "Periodo")
        selected_period_total = payment_repo.get_filtered(
            start_date=report_start, 
            end_date=report_end, 
            method=method_filter,
            limit=5000 # Aumentamos el límite para que el desglose por métodos sea real
        )
        # Sum manually because get_filtered returns objects
        selected_total_val = sum(p.amount for p in selected_period_total)

        # Métodos de pago (Basado en el rango seleccionado y filtros)
        # Si hay metodo filtro, todo será de ese método, pero si es 'Todos', desgloza.
        payment_methods = {}
        
        # Usamos los pagos ya filtrados del periodo seleccionado
        for payment in selected_period_total:
            method = payment.payment_method or 'unknown'
            if method_filter and method != method_filter:
                continue
                
            if method not in payment_methods:
                payment_methods[method] = {'count': 0, 'total': 0.0}
            payment_methods[method]['count'] += 1
            payment_methods[method]['total'] += float(payment.amount or 0)
        
        # Métricas de Deuda (Balances de Clientes)
        client_repo = db.get_client_repository()
        clients = client_repo.get_all()
        total_debt = sum((c.account_balance or 0) for c in clients if (c.account_balance or 0) > 0)
        clients_with_debt = sum(1 for c in clients if (c.account_balance or 0) > 0)
        
        # Calcular facturación esperada mensual (Basado en mensualidades de clientes activos)
        # Manejo robusto de status (puede ser string o enum)
        active_str = ClientStatus.ACTIVE.value if hasattr(ClientStatus.ACTIVE, 'value') else "active"
        monthly_billed_target = sum(
            (c.monthly_fee or 0) for c in clients 
            if c.status == active_str or (hasattr(c.status, 'value') and c.status.value == active_str)
        )
        
        # Generar tendencia de los últimos 12 meses
        annual_trend = []
        for i in range(11, -1, -1):
            # Ajustar para obtener exactamente el mes i atrás de forma robusta
            temp_date = now.replace(day=1)
            for _ in range(i):
                last_day_prev_month = temp_date - timedelta(days=1)
                temp_date = last_day_prev_month.replace(day=1)
            
            month_start_i = temp_date.replace(hour=0, minute=0, second=0, microsecond=0)
            if i == 0:
                month_end_i = now
            else:
                # Siguiente mes - 1 segundo
                next_month = (month_start_i + timedelta(days=32)).replace(day=1)
                month_end_i = next_month - timedelta(seconds=1)
                
            collected = payment_repo.get_total_by_date_range(month_start_i, month_end_i)
            
            annual_trend.append({
                'label': month_start_i.strftime('%b'),
                'month_name': month_start_i.strftime('%B'),
                'year': month_start_i.year,
                'month': month_start_i.month,
                'collected': float(collected or 0),
                'billed': float(monthly_billed_target) # Target simplificado por ahora
            })
            
        # Variables adicionales para counts
        month_payments = payment_repo.get_by_date_range(month_start, now)
        paid_client_ids = set(p.client_id for p in month_payments)
        
        # Obtener pagos recientes
        recent_payments = payment_repo.get_all(limit=5)
        
        return jsonify({
            'totals': {
                'today': float(today_total or 0),
                'week': float(week_total or 0),
                'month': float(month_total or 0),
                'year': float(year_total or 0),
                'all_time': float(all_time_total or 0),
                'filtered': float(selected_total_val or 0),
                'total_pending_debt': float(total_debt or 0)
            },
            'counts': {
                'today': len(payment_repo.get_by_date_range(today_start, now)),
                'week': len(payment_repo.get_by_date_range(week_start, now)),
                'month': len(month_payments),
                'year': len(payment_repo.get_by_date_range(year_start, now)),
                'debt_clients': clients_with_debt,
                'paid_clients': len(paid_client_ids)
            },
            'payment_methods': payment_methods,
            'annual_trend': annual_trend,
            'recent_payments': [p.to_dict() for p in recent_payments]
        })
    except Exception as e:
        logger.exception("CRITICAL ERROR in get_statistics")
        return jsonify({
            'error': str(e),
            'type': type(e).__name__
        }), 500


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


@payments_bp.route('/export', methods=['GET'])
def export_payments():
    """
    Exporta el listado de pagos a CSV con filtros
    """
    import csv
    import io
    from flask import make_response
    
    db = get_db()
    payment_repo = db.get_payment_repository()
    
    # Filtros
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    method = request.args.get('method')
    
    from datetime import timedelta
    start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00')) if start_date else None
    end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00')) if end_date else None
    
    if end_dt:
        end_dt = end_dt.replace(hour=23, minute=59, second=59)
    
    payments = payment_repo.get_filtered(
        start_date=start_dt,
        end_date=end_dt,
        method=method,
        limit=10000
    )
    
    # Crear CSV en memoria
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Encabezados - Cambiado 'ID' por 'Ref' para evitar problema SYLK de Excel
    writer.writerow(['Ref', 'Cliente', 'Código', 'Fecha', 'Monto', 'Moneda', 'Método', 'Referencia', 'Nota'])
    
    for p in payments:
        client_name = p.client.legal_name if p.client else 'N/A'
        subs_code = p.client.subscriber_code if p.client else 'N/A'
        writer.writerow([
            p.id,
            client_name,
            subs_code,
            p.payment_date.strftime('%Y-%m-%d %H:%M'),
            p.amount,
            p.currency,
            p.payment_method,
            p.reference,
            p.notes
        ])
    
    filename = f"reporte_pagos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    # Usar utf-8-sig para que Excel reconozca los acentos y caracteres especiales inmediatamente
    response = make_response(output.getvalue().encode('utf-8-sig'))
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    response.headers["Content-type"] = "text/csv; charset=utf-8"
    
    return response


@payments_bp.route('/export-debtors', methods=['GET'])
def export_debtors():
    """
    Exporta el listado de clientes con deuda a CSV
    """
    import csv
    import io
    from flask import make_response
    
    db = get_db()
    client_repo = db.get_client_repository()
    
    # Obtener todos los clientes con balance > 0 (deuda)
    clients = client_repo.get_all()
    debtors = [c for c in clients if (c.account_balance or 0) > 0]
    
    # Crear CSV en memoria
    output = io.StringIO()
    writer = csv.writer(output, lineterminator='\n')
    
    # Encabezados - Cambiado 'ID' por 'Ref' para evitar el error SYLK de Excel
    writer.writerow(['Ref', 'Código', 'Nombre Legal', 'Teléfono', 'Plan', 'Deuda Tot. (COP)'])
    
    for c in debtors:
        writer.writerow([
            c.id,
            c.subscriber_code or '---',
            c.legal_name or 'N/A',
            c.phone or '---',
            c.plan_name or 'Básico',
            f"{c.account_balance:,.2f}"
        ])
    
    filename = f"reporte_morosos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    # Usar utf-8-sig para compatibilidad total con Excel
    response = make_response(output.getvalue().encode('utf-8-sig'))
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    response.headers["Content-type"] = "text/csv; charset=utf-8"
    
    return response


@payments_bp.route('/export-pdf', methods=['GET'])
def export_payments_pdf():
    """
    Exporta el listado de pagos o morosos a PDF premium
    """
    from src.application.services.report_service import ReportService
    from flask import make_response
    
    db = get_db()
    
    # Filtros
    report_type = request.args.get('report_type', 'payments')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    method = request.args.get('method')
    
    start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00')) if start_date else None
    end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00')) if end_date else None
    
    if end_dt:
        end_dt = end_dt.replace(hour=23, minute=59, second=59)
    
    if report_type == 'debtors':
        client_repo = db.get_client_repository()
        clients = client_repo.get_all()
        debtors = [c for c in clients if (c.account_balance or 0) > 0]
        pdf_buffer = ReportService.generate_debtors_pdf(debtors)
        filename = f"reporte_morosos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    else:
        payment_repo = db.get_payment_repository()
        payments = payment_repo.get_filtered(
            start_date=start_dt,
            end_date=end_dt,
            method=method,
            limit=2000
        )
        pdf_buffer = ReportService.generate_payments_pdf(
            payments, 
            start_date=start_dt.strftime('%d/%m/%Y') if start_dt else None,
            end_date=end_dt.strftime('%d/%m/%Y') if end_dt else None
        )
        filename = f"reporte_pagos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    
    response = make_response(pdf_buffer.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    response.headers["Content-type"] = "application/pdf"
    
    return response


@payments_bp.route('/export-excel', methods=['GET'])
def export_payments_excel():
    """
    Exporta el listado de pagos o morosos a Excel formateado
    """
    from src.application.services.report_service import ReportService
    from flask import make_response
    
    db = get_db()
    
    # Filtros
    report_type = request.args.get('report_type', 'payments')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    method = request.args.get('method')
    
    start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00')) if start_date else None
    end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00')) if end_date else None
    
    if end_dt:
        end_dt = end_dt.replace(hour=23, minute=59, second=59)
    
    if report_type == 'debtors':
        client_repo = db.get_client_repository()
        clients = client_repo.get_all()
        debtors = [c for c in clients if (c.account_balance or 0) > 0]
        # Necesitamos un método en ReportService para Excel de Morosos
        excel_buffer = ReportService.generate_debtors_excel(debtors)
        filename = f"reporte_morosos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    else:
        payment_repo = db.get_payment_repository()
        payments = payment_repo.get_filtered(
            start_date=start_dt,
            end_date=end_dt,
            method=method,
            limit=5000
        )
        excel_buffer = ReportService.generate_payments_excel(payments)
        filename = f"reporte_pagos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    response = make_response(excel_buffer.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    response.headers["Content-type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    
    return response


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
