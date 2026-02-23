"""
Payments API Controller - DATOS REALES
Endpoints para gestión y contabilidad de pagos
"""
from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta, timedelta
from typing import List, Dict, Any
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import ClientStatus, PaymentStatus, Client, Expense
from src.application.services.audit_service import AuditService
from src.application.services.expense_service import ExpenseService
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
        
        db = get_db() # Get DB early for transaction management
        
        # El servicio maneja: 
        # - Registro en tabla payments
        # - Actualización de balance
        # - Actualización de facturas (FIFO)
        # - Reactivación automática si corresponde
        # - Validación de no duplicidad (Problema 3)
        new_payment = service.register_payment(client_id, amount, data)
        
        # COMMIT FINAL: Si llegamos aquí sin errores, guardamos todo atómicamente
        db.session.commit()
        
        # Obtener balance actualizado para la respuesta
        client = db.session.query(Client).get(client_id)
        
        return jsonify({
            'success': True, 
            'payment_id': new_payment.id,
            'new_balance': client.account_balance,
            'message': 'Pago registrado exitosamente'
        }), 201
        
    except ValueError as ve:
        # Errores de validación (como el de pago duplicado)
        db = get_db()
        db.session.rollback()
        return jsonify({'error': str(ve)}), 400
    except Exception as e:
        logger.error(f"Error creating payment: {str(e)}")
        db = get_db()
        db.session.rollback()
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
    """Anula un pago y lo mueve a la papelera (lógica de borrado lógico/archivo)"""
    try:
        db = get_db()
        payment_repo = db.get_payment_repository()
        deleted_repo = db.get_deleted_payment_repository()
        
        payment = payment_repo.get_by_id(payment_id)
        if not payment:
            return jsonify({'error': 'Pago no encontrado'}), 404
            
        # 1. Obtener datos de eliminación (soportar JSON o Query Params)
        deleted_by = 'admin'
        reason = 'Anulado por usuario'
        
        if request.is_json:
            try:
                data = request.get_json()
                if data:
                    deleted_by = data.get('deleted_by', deleted_by)
                    reason = data.get('reason', reason)
            except:
                pass
        
        # Fallback/Sobreescribir con query params si existen (común en llamadas DELETE)
        deleted_by = request.args.get('deleted_by', deleted_by)
        reason = request.args.get('reason', reason)

        # 2. Crear copia en papelera (sin commit interno)
        deleted_repo.create_from_payment(
            payment, 
            deleted_by=deleted_by,
            reason=reason,
            commit=False
        )
        
        # 2. Borrar del original (sin commit interno)
        payment_repo.delete(payment_id, commit=False)
        
        # 3. Restaurar balance al cliente (Sumar el monto de vuelta a la deuda)
        client_repo = db.get_client_repository()
        client_repo.update_balance(payment.client_id, payment.amount, operation='add', commit=False)
        
        # 4. Auditoría (sin commit interno)
        AuditService.log(
            operation='payment_deleted',
            category='accounting',
            entity_type='payment',
            entity_id=payment_id,
            description=f"Pago ID {payment_id} anulado y movido a papelera. Monto: {payment.amount}",
            commit=False
        )
        
        # COMMIT FINAL: Si llegamos aquí sin errores, guardamos todo atómicamente
        db.session.commit()
        
        logger.info(f"Pago archivado y eliminado: ID {payment_id}")
        return jsonify({'message': 'Pago anulado y movido a papelera correctamente'}), 200
        
    except Exception as e:
        logger.error(f"Error deleting/archiving payment: {e}")
        db = get_db()
        db.session.rollback()
        return jsonify({'error': f'Error al procesar la anulación: {str(e)}'}), 500


@payments_bp.route('/<int:payment_id>/revert', methods=['POST'])
def revert_payment(payment_id):
    """
    Revierte un pago (diferente de delete):
    - Ciclo actual: suspende cliente + ajusta contabilidad
    - Ciclo histórico: solo ajusta contabilidad + auditoría fuerte
    """
    try:
        db = get_db()
        payment_repo = db.get_payment_repository()
        client_repo = db.get_client_repository()
        
        payment = payment_repo.get_by_id(payment_id)
        if not payment:
            return jsonify({'error': 'Pago no encontrado'}), 404
        
        # Si ya está cancelado, no permitir
        if payment.status == PaymentStatus.CANCELLED.value:
            return jsonify({'error': 'Este pago ya está anulado'}), 400
        
        data = request.get_json() or {}
        reason = data.get('reason', 'Reversión de pago')
        is_current_cycle = data.get('is_current_cycle', False)
        
        client = client_repo.get_by_id(payment.client_id)
        if not client:
            return jsonify({'error': 'Cliente no encontrado'}), 404
        
        # 1. Marcar pago como cancelado
        payment.status = PaymentStatus.CANCELLED.value
        payment.notes = f"REVERTIDO: {reason}"
        
        # 2. Restaurar balance (sumar monto de vuelta a la deuda)
        client_repo.update_balance(
            payment.client_id,
            payment.amount,
            operation='add',
            commit=False
        )
        
        # 3. Si es ciclo actual, suspender cliente
        suspension_info = ""
        if is_current_cycle:
            from src.application.services.batch_service import BatchService
            batch_service = BatchService()
            
            # Suspender en MikroTik
            try:
                batch_service._disable_mikrotik_only(client)
                client.status = ClientStatus.SUSPENDED.value
                db.session.add(client)
                suspension_info = " Cliente suspendido en MikroTik."
            except Exception as e:
                logger.error(f"Error suspending client in MikroTik: {e}")
                db.session.rollback()
                return jsonify({'error': f'Error al suspender cliente: {str(e)}'}), 500
        
        # 4. Auditoría
        audit_category = 'accounting_critical' if not is_current_cycle else 'accounting'
        AuditService.log(
            operation='payment_reverted',
            category=audit_category,
            entity_type='payment',
            entity_id=payment_id,
            description=f"Pago #{payment_id} REVERTIDO ({'ciclo actual' if is_current_cycle else f'HISTÓRICO'}). "
f"Monto: ${payment.amount:,.2f}. Cliente: {client.legal_name}. Motivo: {reason}",
            commit=False
        )
        
        db.session.commit()
        
        logger.info(f"Payment reverted: ID {payment_id}, Current Cycle: {is_current_cycle}")
        
        return jsonify({
            'message': f'Pago revertido exitosamente.{suspension_info}',
            'payment_id': payment_id,
            'client_id': client.id,
            'new_balance': float(client.debt_balance)
        }), 200
        
    except Exception as e:
        logger.error(f"Error reverting payment: {e}")
        db = get_db()
        db.session.rollback()
        return jsonify({'error': f'Error al revertir pago: {str(e)}'}), 500


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
        
        db = get_db()
        
        # El restore es básicamente re-registrar el pago
        data = {
            'payment_method': deleted.payment_method,
            'reference': deleted.reference,
            'notes': f"RESTAURADO (Original ID {deleted.original_id}): " + (deleted.notes or ""),
            'authorized': True # Forzar autorización ya que es una restauración
        }
        
        # 1. Registrar el pago nuevamente (sin commit interno)
        new_payment = service.register_payment(deleted.client_id, deleted.amount, data)
        
        # 2. Eliminar de la papelera (sin commit interno)
        deleted_repo.delete(deleted_id, commit=False)
        
        # 3. Auditoría (sin commit interno)
        AuditService.log(
            operation='payment_restored',
            category='accounting',
            entity_type='payment',
            entity_id=new_payment.id,
            description=f"Pago restaurado desde papelera. Cliente ID {deleted.client_id}, Monto ${deleted.amount}",
            commit=False
        )
        
        # COMMIT FINAL: Guardar todo atómicamente
        db.session.commit()
        
        return jsonify({'message': 'Pago restaurado correctamente', 'payment_id': new_payment.id}), 200
        
    except Exception as e:
        logger.error(f"Error restoring payment: {e}")
        db = get_db()
        db.session.rollback()
        return jsonify({'error': 'Error al restaurar el pago'}), 500


@payments_bp.route('/deleted/<int:deleted_id>', methods=['DELETE'])
def delete_permanently(deleted_id):
    """Elimina permanentemente un registro de la papelera"""
    db = get_db()
    deleted_repo = db.get_deleted_payment_repository()
    
    try:
        if deleted_repo.delete(deleted_id):
            return jsonify({'message': 'Registro eliminado permanentemente'}), 200
        return jsonify({'error': 'Registro no encontrado'}), 404
    except Exception as e:
        logger.error(f"Error delete_permanently: {e}")
        return jsonify({'error': str(e)}), 500


@payments_bp.route('/deleted/clear', methods=['DELETE'])
def clear_trash():
    """Vacía completamente la papelera"""
    db = get_db()
    deleted_repo = db.get_deleted_payment_repository()
    
    try:
        count = deleted_repo.clear_all()
        return jsonify({'message': f'Papelera vaciada ({count} registros)'}), 200
    except Exception as e:
        logger.error(f"Error clear_trash: {e}")
        return jsonify({'error': str(e)}), 500


@payments_bp.route('/deleted/delete-batch', methods=['POST'])
def delete_batch_permanently():
    """Elimina múltiples registros de la papelera de forma permanente"""
    data = request.json
    deleted_ids = data.get('deleted_ids', [])
    
    if not deleted_ids:
        return jsonify({'error': 'No se proporcionaron IDs'}), 400
        
    db = get_db()
    deleted_repo = db.get_deleted_payment_repository()
    
    try:
        count = deleted_repo.delete_batch(deleted_ids)
        return jsonify({'message': f'{count} registros eliminados permanentemente'}), 200
    except Exception as e:
        logger.error(f"Error delete_batch_permanently: {e}")
        return jsonify({'error': str(e)}), 500


@payments_bp.route('/revert-batch', methods=['POST'])
def revert_batch():
    """
    Revierte múltiples pagos de forma masiva
    """
    data = request.json
    payment_ids = data.get('payment_ids', [])
    reason = data.get('reason', 'Reversión masiva por incumplimiento')
    
    if not payment_ids:
        return jsonify({'error': 'No se proporcionaron IDs de pagos'}), 400
        
    try:
        from src.application.services.billing_service import BillingService
        service = BillingService()
        
        results = []
        for pid in payment_ids:
            try:
                service.revert_payment(pid, reason)
                results.append({'id': pid, 'status': 'success'})
            except Exception as e:
                results.append({'id': pid, 'status': 'error', 'message': str(e)})
                
        return jsonify({
            'success': True,
            'results': results,
            'message': f'Proceso completo. Exitosos: {sum(1 for r in results if r["status"] == "success")}'
        })
    except Exception as e:
        logger.error(f"Error in revert_batch: {e}")
        return jsonify({'error': 'Error interno al procesar reversión masiva'}), 500


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
        now = datetime.now()
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

        # repositorios
        client_repo = db.get_client_repository()
        expense_repo = db.get_expense_repository()

        # Calcular totales Fijos (Siempre útiles)
        today_total = payment_repo.get_total_by_date_range(today_start, now)
        week_total = payment_repo.get_total_by_date_range(week_start, now)
        month_total = payment_repo.get_total_by_date_range(month_start, now)
        year_total = payment_repo.get_total_by_date_range(year_start, now)
        all_time_total = payment_repo.get_total_by_date_range(datetime(2000, 1, 1), now)

        # Gastos Fijos
        today_expenses = expense_repo.get_total_by_date_range(today_start, now)
        week_expenses = expense_repo.get_total_by_date_range(week_start, now)
        month_expenses = expense_repo.get_total_by_date_range(month_start, now)
        year_expenses = expense_repo.get_total_by_date_range(year_start, now)
        all_time_expenses = expense_repo.get_total_by_date_range(datetime(2000, 1, 1), now)
        
        # Calcular total del periodo seleccionado (para la tarjeta "Este Mes" o "Periodo")
        # Obtener todos (sin filtro de status en repo)
        raw_period_payments = payment_repo.get_filtered(
            start_date=report_start, 
            end_date=report_end, 
            method=method_filter,
            limit=5000 
        )
        
        # Gastos del periodo filtrado
        filtered_expenses = expense_repo.get_total_by_date_range(report_start, report_end)

        # Statuses considered as "Successful/Collected"
        SUCCESS_STATUSES = ['paid', 'verified', 'approved', 'success']
        
        # Filtrar solo PAGADOS/VERIFICADOS para consistencia con Dashboard
        # Excluye 'pending', 'cancelled', 'deleted', etc.
        selected_period_total = [
            p for p in raw_period_payments 
            if str(p.status).lower() in SUCCESS_STATUSES
        ]

        # Sum manually because get_filtered returns objects
        selected_total_val = sum(p.amount for p in selected_period_total)
        total_fx_variance_val = sum(p.fx_variance or 0.0 for p in selected_period_total)

        # Métodos de pago (Basado en el rango seleccionado y filtros)
        # Si hay metodo filtro, todo será de ese método, pero si es 'Todos', desgloza.
        payment_methods = {}
        
        # Usamos los pagos ya filtrados (validos) del periodo seleccionado
        for payment in selected_period_total:
            method = payment.payment_method or 'unknown'
            if method_filter and method != method_filter:
                continue
                
            if method not in payment_methods:
                payment_methods[method] = {'count': 0, 'total': 0.0}
            payment_methods[method]['count'] += 1
            payment_methods[method]['total'] += float(payment.amount or 0)

        # --- Desglose de Gastos por Categoría ---
        expense_categories = {}
        # Obtener gastos reales del periodo para desglose
        from src.infrastructure.database.models import Expense
        period_expenses = db.session.query(Expense).filter(
            Expense.expense_date >= report_start,
            Expense.expense_date <= report_end
        ).all()

        for exp in period_expenses:
            cat = exp.category or 'otros'
            if cat not in expense_categories:
                expense_categories[cat] = {'count': 0, 'total': 0.0}
            expense_categories[cat]['count'] += 1
            expense_categories[cat]['total'] += float(exp.amount or 0)
        
        # Métricas de Deuda (Balances de Clientes)
        # Obtener todos los clientes (una sola vez para optimizar)
        all_clients = client_repo.get_all()
        
        # Filtramos operacionales (excluyendo eliminados) para consistencia con Dashboard
        operational_clients = [c for c in all_clients if str(c.status).lower() != 'deleted']
        
        total_debt = sum((c.account_balance or 0) for c in operational_clients if (c.account_balance or 0) > 0)
        clients_with_debt = sum(1 for c in operational_clients if (c.account_balance or 0) > 0)
        
        # Calcular facturación esperada mensual (Basado en mensualidades de clientes activos)
        # Manejo robusto de status (puede ser string o enum)
        active_str = ClientStatus.ACTIVE.value if hasattr(ClientStatus.ACTIVE, 'value') else "active"
        monthly_billed_target = sum(
            (c.monthly_fee or 0) for c in all_clients 
            if c.status == active_str or (hasattr(c.status, 'value') and c.status.value == active_str)
        )
        
        # --- Advanced Financial Metrics (Requested by User) ---
        # 2. Monto de más en caja (Saldos a favor)
        total_surplus = sum(abs(c.account_balance or 0) for c in operational_clients if (c.account_balance or 0) < 0)
        
        # 3. Cartera Castigada (Bad Debt): Deuda de clientes eliminados
        deleted_clients = [c for c in all_clients if str(c.status).lower() == 'deleted']
        total_bad_debt = sum((c.account_balance or 0) for c in deleted_clients if (c.account_balance or 0) > 0)
        
        # 2. Monto en espera por promesa de pago
        pending_promises_amount = sum(
            (c.account_balance or 0) for c in operational_clients 
            if (c.account_balance or 0) > 0 and c.promise_date and c.promise_date >= now
        )
        
        # 3. Pérdida por Prorrateo (Period)
        # Compara el total actual de facturas del periodo vs la suma original de sus items
        from src.infrastructure.database.models import Invoice, InvoiceItem
        
        # Usamos el rango del reporte para calcular descuentos otorgados en ese periodo
        period_invoices = db.session.query(Invoice).filter(
            Invoice.issue_date >= report_start,
            Invoice.issue_date <= report_end
        ).all()
        
        prorated_loss_month = 0.0
        for inv in period_invoices:
            # Calcular original sumando items
            original_val = sum(item.amount for item in inv.items)
            current_val = inv.total_amount
            
            # Si el monto actual es menor al original (y mayor a 0 para evitar anuladas), es descuento
            if current_val > 0 and original_val > current_val + 0.01: # 0.01 margen error float
                prorated_loss_month += (original_val - current_val)
        
        # Generar tendencia de los últimos 12 meses
        annual_trend = []
        
        # Filtramos operativos para tendencia histórica
        working_clients = [c for c in all_clients if str(c.status).lower() in ['active', 'suspended', 'deleted']]

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
                next_month = (month_start_i + timedelta(days=32)).replace(day=1)
                month_end_i = next_month - timedelta(seconds=1)
                
            collected = payment_repo.get_total_by_date_range(month_start_i, month_end_i)
            expenses_i = expense_repo.get_total_by_date_range(month_start_i, month_end_i)
            
            # Cálculo de Meta Histórica (Theoretical)
            clients_that_month = []
            for c in working_clients:
                if not c.created_at or c.created_at > month_end_i:
                    continue
                if str(c.status).lower() == 'deleted':
                    if c.updated_at and c.updated_at < month_start_i:
                        continue
                clients_that_month.append(c)
                
            theoretical = float(sum((c.monthly_fee or 0) for c in clients_that_month))
            net_profit_i = float(collected or 0) - float(expenses_i or 0)
            
            annual_trend.append({
                'label': month_start_i.strftime('%b'),
                'month_name': month_start_i.strftime('%B'),
                'year': month_start_i.year,
                'month': month_start_i.month,
                'collected': float(collected or 0),
                'expenses': float(expenses_i or 0),
                'net_profit': net_profit_i,
                'theoretical': theoretical,
                'loss': max(0, theoretical - float(collected or 0)),
                'performance': (float(collected or 0) / theoretical * 100) if theoretical > 0 else 0
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
                'today_expenses': float(today_expenses or 0),
                'week_expenses': float(week_expenses or 0),
                'month_expenses': float(month_expenses or 0),
                'year_expenses': float(year_expenses or 0),
                'all_time_expenses': float(all_time_expenses or 0),
                'today_net': float(today_total or 0) - float(today_expenses or 0),
                'week_net': float(week_total or 0) - float(week_expenses or 0),
                'month_net': float(month_total or 0) - float(month_expenses or 0),
                'year_net': float(year_total or 0) - float(year_expenses or 0),
                'all_time_net': float(all_time_total or 0) - float(all_time_expenses or 0),
                'filtered_period_total': float(selected_total_val or 0),
                'filtered_period_expenses': float(filtered_expenses or 0),
                'filtered_period_net': float(selected_total_val or 0) - float(filtered_expenses or 0),
                'total_fx_variance': float(total_fx_variance_val or 0),
                'total_pending_debt': float(total_debt or 0),
                'prorated_adjustment': float(prorated_loss_month or 0),
                'pending_promises': float(pending_promises_amount or 0),
                'client_surplus': float(total_surplus or 0),
                'bad_debt': float(total_bad_debt or 0),
                'theoretical_income': float(monthly_billed_target or 0),
                'combined_losses': float(prorated_loss_month or 0) + float(total_bad_debt or 0) + (abs(float(total_fx_variance_val)) if float(total_fx_variance_val) < 0 else 0)
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
            'expense_categories': expense_categories,
            'annual_trend': annual_trend,
            'recent_payments': [p.to_dict() for p in recent_payments]
        })
    except Exception as e:
        logger.exception("CRITICAL ERROR in get_statistics")
        return jsonify({
            'error': str(e),
            'type': type(e).__name__
        }), 500


@payments_bp.route('/losses-detail', methods=['GET'])
def get_losses_detail():
    """
    Obtiene el desglose detallado de todas las 'fugas' financieras:
    - Diferencias en cambio (negativas)
    - Descuentos por prorrateo
    - Deuda de clientes eliminados (Cartera Castigada)
    """
    try:
        db = get_db()
        now = datetime.now()
        report_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        report_end = now
        
        # Filtros opcionales de fecha
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        if start_date_str:
            try: report_start = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
            except: pass
        if end_date_str:
            try: report_end = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
            except: pass

        losses = []

        # 1. Variaciones Cambiarias Negativas (FX Loss)
        payment_repo = db.get_payment_repository()
        payments = payment_repo.get_filtered(start_date=report_start, end_date=report_end, limit=1000)
        
        for p in payments:
            if (p.fx_variance or 0) < 0:
                losses.append({
                    'id': f"fx-{p.id}",
                    'concept': f"Diferencia en Cambio - Pago #{p.id}",
                    'category': 'FX Variance',
                    'date': p.payment_date.isoformat() if p.payment_date else None,
                    'reference': p.reference or f"Ref {p.id}",
                    'client_name': p.client.legal_name if p.client else "N/A",
                    'amount': abs(p.fx_variance)
                })

        # 2. Pérdidas por Prorrateo (Discounts in Invoices)
        from src.infrastructure.database.models import Invoice
        invoices = db.session.query(Invoice).filter(
            Invoice.issue_date >= report_start,
            Invoice.issue_date <= report_end
        ).all()

        for inv in invoices:
            original_val = sum(item.amount for item in inv.items)
            current_val = inv.total_amount
            if current_val > 0 and original_val > current_val + 0.01:
                losses.append({
                    'id': f"pr-{inv.id}",
                    'concept': f"Ajuste por Prorrateo - Factura #{inv.id}",
                    'category': 'Prorating',
                    'date': inv.issue_date.isoformat(),
                    'reference': f"FACT-{inv.id}",
                    'client_name': inv.client.legal_name if inv.client else "N/A",
                    'amount': original_val - current_val
                })

        # 3. Cartera Castigada (Deleted Clients with Debt)
        from src.infrastructure.database.models import Client
        deleted_debtors = db.session.query(Client).filter(
            Client.status == 'deleted',
            Client.account_balance > 0
        ).all()

        for c in deleted_debtors:
            losses.append({
                'id': f"bd-{c.id}",
                'concept': f"Deuda Incobrable - Cliente Retirado",
                'category': 'Bad Debt',
                'date': c.updated_at.isoformat() if c.updated_at else None,
                'reference': c.subscriber_code,
                'client_name': c.legal_name,
                'amount': c.account_balance
            })

        # Ordenar por fecha descendente
        losses.sort(key=lambda x: x['date'] if x['date'] else "", reverse=True)

        return jsonify(losses)

    except Exception as e:
        logger.exception("Error in get_losses_detail")
        return jsonify({'error': str(e)}), 500


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
        # Traducción de métodos de pago
        method_map = {
            'Cash': 'Efectivo',
            'Bank Transfer': 'Transferencia',
            'Mobile Payment': 'Pago Móvil',
            'Zelle': 'Zelle',
            'Binance': 'Binance',
            'Digital Wallet': 'Billetera Digital',
            'Other': 'Otro'
        }
        
        display_method = method_map.get(p.payment_method, p.payment_method)
        
        writer.writerow([
            p.id,
            client_name,
            subs_code,
            p.payment_date.strftime('%Y-%m-%d %H:%M'),
            p.amount,
            p.currency,
            display_method,
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
        pdf_buffer = ReportService.generate_debtors_pdf(debtors)
        filename = f"reporte_morosos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    
    elif report_type == 'routers':
        # Reporte de Análisis por Router
        router_repo = db.get_router_repository()
        routers = router_repo.get_all()
        client_repo = db.get_client_repository()
        payment_repo = db.get_payment_repository() # Needed for collections
        
        # 1. Obtener pagos del periodo seleccionado para calcular recaudación real
        # Si no hay fechas, traer todo (o limitar a mes actual si se prefiere, pero el usuario elige)
        
        # Helper para fechas de meses anteriores
        def get_prev_month_dates(start, end):
            # Asumimos que start y end definen un mes. Restamos ~30 días.
            # Mejor aproximación: primer día del mes anterior
            if not start: return None, None
            
            curr_month_start = start.replace(day=1)
            prev_month_end = curr_month_start - timedelta(days=1)
            prev_month_start = prev_month_end.replace(day=1)
            return prev_month_start, prev_month_end

        # Periodo Actual (P0)
        p0_start, p0_end = start_dt, end_dt
        
        # Periodo Anterior 1 (P-1)
        p1_start, p1_end = get_prev_month_dates(p0_start, p0_end) if p0_start else (None, None)
        
        # Periodo Anterior 2 (P-2)
        p2_start, p2_end = get_prev_month_dates(p1_start, p1_end) if p1_start else (None, None)

        # DEBUG: Log to file
        try:
            with open('debug_payments.txt', 'a') as f:
                f.write(f"\n--- Report Request at {datetime.now()} ---\n")
                f.write(f"Start: {start_dt} (Type: {type(start_dt)})\n")
                f.write(f"End: {end_dt} (Type: {type(end_dt)})\n")
        except Exception as e:
            logger.error(f"Failed to write debug log: {e}")

        # Función auxiliar para obtener recaudado por router en un rango
        def get_collected_by_router(s_date, e_date):
            if not s_date or not e_date: return {}
            # Asegurar fin de día para e_date si no tiene hora
            if e_date.hour == 0 and e_date.minute == 0:
                 e_date = e_date.replace(hour=23, minute=59, second=59)

            pay_list = payment_repo.get_all(start_date=s_date, end_date=e_date, limit=50000)
            
            # DEBUG: Log count
            try:
                with open('debug_payments.txt', 'a') as f:
                    f.write(f"Query Range: {s_date} to {e_date} -> Found {len(pay_list)} payments\n")
                    if pay_list:
                        p = pay_list[0]
                        f.write(f"  Sample: ID={p.id} Amt={p.amount} Date={p.payment_date} RouterID={p.client.router_id if p.client else 'None'}\n")
            except: pass
            
            res = {}
            for p in pay_list:
                if p.client and p.client.router_id:
                     rid = p.client.router_id
                     res[rid] = res.get(rid, 0.0) + p.amount
            return res

        collected_p0 = get_collected_by_router(p0_start, p0_end)
        collected_p1 = get_collected_by_router(p1_start, p1_end)
        collected_p2 = get_collected_by_router(p2_start, p2_end)

        # Nombre de los meses para el reporte
        month_names = {1:'Enero', 2:'Febrero', 3:'Marzo', 4:'Abril', 5:'Mayo', 6:'Junio', 7:'Julio', 8:'Agosto', 9:'Septiembre', 10:'Octubre', 11:'Noviembre', 12:'Diciembre'}
        
        history_labels = [
            month_names[p0_start.month] if p0_start else 'Actual',
            month_names[p1_start.month] if p1_start else 'Mes -1',
            month_names[p2_start.month] if p2_start else 'Mes -2'
        ]

        router_stats = []
        
        for router in routers:
            # Obtener clientes del router
            clients = client_repo.get_by_router(router.id)
            
            # Datos Históricos
            c0 = collected_p0.get(router.id, 0.0)
            c1 = collected_p1.get(router.id, 0.0)
            c2 = collected_p2.get(router.id, 0.0)
            
            # Crecimiento %
            g1 = ((c0 - c1) / c1 * 100) if c1 > 0 else 100 if c0 > 0 else 0
            g2 = ((c1 - c2) / c2 * 100) if c2 > 0 else 100 if c1 > 0 else 0
            
            # Calcular Estadísticas
            stats = {
                'name': router.alias,
                'total_clients': len(clients),
                'active': 0,
                'cut': 0,
                'retired': 0,
                'solvent': 0,
                'debtor': 0,
                'total_debt': 0.0,
                'potential_revenue': 0.0,
                'collected': c0,
                'history': {
                    'labels': history_labels,
                    'values': [c0, c1, c2],
                    'growth': [g1, g2] # g1: P-1 -> P0, g2: P-2 -> P-1
                }
            }
            
            for c in clients:
                # Status Service
                # Normalizar status si es enum o string
                status_val = c.status.value if hasattr(c.status, 'value') else c.status
                
                if status_val == 'active':
                    stats['active'] += 1
                    stats['potential_revenue'] += (c.monthly_fee or 0)
                elif status_val == 'suspended':
                    stats['cut'] += 1
                    # Asumimos que cortados aún generan deuda potencial si no están retirados
                    stats['potential_revenue'] += (c.monthly_fee or 0) 
                elif status_val == 'retired':
                    stats['retired'] += 1
                
                # Financial Status
                balance = c.account_balance or 0
                if balance > 0:
                    stats['debtor'] += 1
                    stats['total_debt'] += balance
                else:
                    stats['solvent'] += 1
            
            if stats['total_clients'] > 0: # Solo incluir routers relevantes
                router_stats.append(stats)
        
        pdf_buffer = ReportService.generate_router_analysis_pdf(router_stats)
        filename = f"analisis_routers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

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


@payments_bp.route('/rates', methods=['GET'])
def get_exchange_rates():
    """
    Obtiene las tasas de cambio vigentes para el ERP (Soporta BCV y Comercial p/ VES)
    """
    db = get_db()
    settings_repo = db.get_system_setting_repository()
    
    # Tasas por defecto si no existen en DB
    rates = {
        'USD_COP': float(settings_repo.get_value('RATE_USD_COP', 4000.0)),
        'USD_VES': float(settings_repo.get_value('RATE_USD_VES', 36.5)),
        'USD_VES_BCV': float(settings_repo.get_value('RATE_USD_VES_BCV', 36.5)),
        'USD_VES_COM': float(settings_repo.get_value('RATE_USD_VES_COM', 40.0)),
        'COP_VES': float(settings_repo.get_value('RATE_COP_VES', 0.009)),
        'last_updated': settings_repo.get_value('RATE_LAST_UPDATED', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    }
    
    return jsonify(rates)


@payments_bp.route('/rates', methods=['POST'])
def update_exchange_rates():
    """
    Actualiza las tasas de cambio (BCV, Comercial, COP)
    """
    data = request.json
    db = get_db()
    settings_repo = db.get_system_setting_repository()
    
    updated_keys = []
    for key in ['RATE_USD_COP', 'RATE_USD_VES', 'RATE_USD_VES_BCV', 'RATE_USD_VES_COM', 'RATE_COP_VES']:
        json_key = key.replace('RATE_', '')
        if json_key in data:
            settings_repo.set_value(key, data[json_key], category='accounting', commit=False)
            updated_keys.append(json_key)
            
            # Si actualizamos USD_VES_BCV o USD_VES_COM, también sincronizamos USD_VES por defecto
            if json_key == 'USD_VES_BCV':
                settings_repo.set_value('RATE_USD_VES', data[json_key], category='accounting', commit=False)

    if updated_keys:
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        settings_repo.set_value('RATE_LAST_UPDATED', now_str, category='accounting', commit=False)
        db.session.commit()
        
        # Auditoría de cambio de tasas
        AuditService.log(
            operation='rates_updated',
            category='accounting',
            entity_type='settings',
            entity_id=0,
            description=f"Tasas de cambio actualizadas: {', '.join(updated_keys)}"
        )
        
        return jsonify({'success': True, 'message': 'Tasas actualizadas correctamente', 'last_updated': now_str})
    
    return jsonify({'success': False, 'message': 'No se proporcionaron tasas válidas'}), 400


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

# ==========================================
#  MODULO DE GASTOS Y DEDUCIBLES
# ==========================================

@payments_bp.route('/expenses', methods=['GET'])
def get_expenses():
    """Obtiene lista de gastos con filtros"""
    db = get_db()
    repo = db.get_expense_repository()
    
    # Filtros
    category = request.args.get('category')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    search = request.args.get('search')
    limit = request.args.get('limit', default=100, type=int)
    
    start_dt = None
    end_dt = None
    
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        except: pass
        
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            if end_dt.hour == 0 and end_dt.minute == 0:
                end_dt = end_dt.replace(hour=23, minute=59, second=59)
        except: pass
        
    expenses = repo.get_filtered(
        category=category,
        start_date=start_dt,
        end_date=end_dt,
        search=search,
        limit=limit
    )
    
    return jsonify([e.to_dict() for e in expenses])


@payments_bp.route('/expenses', methods=['POST'])
def create_expense():
    """Registra un nuevo gasto usando el servicio ERP"""
    data = request.json
    
    if not data.get('description') or not data.get('amount'):
        return jsonify({'error': 'Descripción y monto son requeridos'}), 400
        
    try:
        service = ExpenseService()
        new_expense = service.register_expense(data)
        
        return jsonify({
            'success': True,
            'message': 'Gasto registrado correctamente conforme a estándares ERP',
            'expense': new_expense.to_dict()
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating expense: {e}")
        return jsonify({'error': f"Error al procesar egreso: {str(e)}"}), 500


@payments_bp.route('/expenses/<int:expense_id>', methods=['GET'])
def get_expense(expense_id):
    """Obtiene un gasto específico"""
    db = get_db()
    repo = db.get_expense_repository()
    
    expense = repo.get_by_id(expense_id)
    if not expense:
        return jsonify({'error': 'Gasto no encontrado'}), 404
    
    return jsonify(expense.to_dict())


@payments_bp.route('/expenses/<int:expense_id>', methods=['PUT'])
def update_expense(expense_id):
    """Actualiza un gasto existente"""
    data = request.json
    db = get_db()
    repo = db.get_expense_repository()
    
    # 1. Filtrar campos permitidos
    allowed_fields = ['description', 'amount', 'currency', 'category', 'notes', 'expense_date', 'base_amount', 'exchange_rate', 'is_recurring', 'tax_deductible']
    update_data = {k: v for k, v in data.items() if k in allowed_fields}
    
    # 2. Convertir fecha si existe
    if 'expense_date' in update_data and update_data['expense_date']:
        if isinstance(update_data['expense_date'], str):
            try:
                if 'T' in update_data['expense_date']:
                    update_data['expense_date'] = datetime.fromisoformat(update_data['expense_date'].replace('Z', '+00:00'))
                elif '-' in update_data['expense_date']:
                    update_data['expense_date'] = datetime.strptime(update_data['expense_date'], '%Y-%m-%d')
                elif '/' in update_data['expense_date']:
                    update_data['expense_date'] = datetime.strptime(update_data['expense_date'], '%d/%m/%Y')
                else:
                    return jsonify({'error': 'Formato de fecha no reconocido'}), 400
            except ValueError:
                return jsonify({'error': 'Formato de fecha de gasto inválido. Use YYYY-MM-DD, DD/MM/YYYY o ISO 8601'}), 400
    
    try:
        updated_expense = repo.update(expense_id, update_data)
        if not updated_expense:
            return jsonify({'error': 'Gasto no encontrado'}), 404
            
        return jsonify({
            'success': True,
            'message': 'Gasto actualizado correctamente',
            'expense': updated_expense.to_dict()
        }), 200
        
    except Exception as e:
        logger.error(f"Error updating expense: {e}")
        return jsonify({'error': f"Error al actualizar egreso: {str(e)}"}), 500


@payments_bp.route('/expenses/<int:expense_id>', methods=['DELETE'])
def delete_expense(expense_id):
    """Elimina un gasto"""
    try:
        db = get_db()
        repo = db.get_expense_repository()
        
        if repo.delete(expense_id):
            return jsonify({'message': 'Gasto eliminado correctamente'}), 200
        return jsonify({'error': 'Gasto no encontrado'}), 404
        
    except Exception as e:
        logger.error(f"Error deleting expense: {e}")
        return jsonify({'error': str(e)}), 500


@payments_bp.route('/expenses/summary', methods=['GET'])
def get_expenses_summary():
    """Obtiene resumen de gastos del mes actual (o especificado)"""
    try:
        db = get_db()
        repo = db.get_expense_repository()
        
        month = request.args.get('month', default=datetime.now().month, type=int)
        year = request.args.get('year', default=datetime.now().year, type=int)
        
        summary = repo.get_summary(month, year)
        
        return jsonify(summary)
        
    except Exception as e:
        logger.error(f"Error getting expenses summary: {e}")
        return jsonify({'error': str(e)}), 500
