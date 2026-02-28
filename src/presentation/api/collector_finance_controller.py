"""
Collector Finance Controller
API endpoints for the collector's financial summary, earnings and remittance tracking.
"""
from flask import Blueprint, request, jsonify, g
from datetime import datetime, timedelta
from src.application.services.auth import login_required
from src.infrastructure.database.models import (
    User, Payment, Client, CollectorTransfer, Expense, UserRole, get_session, init_db
)
import os
from sqlalchemy import or_

collector_finance_bp = Blueprint('collector_finance', __name__, url_prefix='/api/collector')

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///sgubm.db')
engine = init_db(DATABASE_URL)

RESTRICTED_ROLES = [UserRole.COLLECTOR.value, UserRole.TECHNICAL.value, UserRole.SECRETARY.value]

def _get_date_range(args):
    """Parse optional start/end date query params, default to current month."""
    now = datetime.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    start_str = args.get('start_date')
    end_str = args.get('end_date')
    
    try:
        start = datetime.fromisoformat(start_str) if start_str else month_start
    except:
        start = month_start
    try:
        end = datetime.fromisoformat(end_str) if end_str else now
    except:
        end = now
    
    return start, end


@collector_finance_bp.route('/summary', methods=['GET'])
@login_required
def get_collector_summary():
    """
    Resumen financiero del cobrador:
    - Total cobrado por período y método de pago
    - Ganancia del cobrador (% configurable)
    - Gastos fijos/deducibles
    - Total enviado a la empresa
    - Saldo pendiente por enviar
    """
    admin_user = g.user
    session = get_session(engine)
    
    try:
        start, end = _get_date_range(request.args)
        
        # Admin can view other collectors
        target_user_id = request.args.get('collector_id', type=int)
        is_admin = admin_user.role in [UserRole.ADMIN.value, UserRole.ADMIN_FEM.value, UserRole.PARTNER.value]
        
        if target_user_id and is_admin:
            user = session.query(User).get(target_user_id)
            if not user:
                return jsonify({'success': False, 'message': 'Usuario no encontrado'}), 404
        else:
            user = admin_user

        # Filter clients by assigned_collector_id OR assigned_router_id
        # Prioritize assigned_collector_id if it's a collector role
        if user.role == UserRole.COLLECTOR.value:
            from src.infrastructure.database.models import CollectorAssignment
            # Get router IDs from multi-router assignments
            collector_router_ids = [a.router_id for a in (getattr(user, 'assignments', None) or [])]
            # Fallback to legacy
            if not collector_router_ids and user.assigned_router_id:
                collector_router_ids = [user.assigned_router_id]
            
            if collector_router_ids:
                clients = session.query(Client).filter(
                    (Client.assigned_collector_id == user.id) | 
                    ((Client.assigned_collector_id == None) & (Client.router_id.in_(collector_router_ids)))
                ).all()
            else:
                clients = session.query(Client).filter(
                    Client.assigned_collector_id == user.id
                ).all()
        else:
            # If it's an admin looking at a user without specific filters, we might want to narrow down
            # but for now, if no collector_id is provided, admin sees global summary?
            # User request says: "administrator can see financial operations per collector"
            # So if no collector_id, maybe we return a list of summaries or just the admin's (empty usually)
            if not target_user_id:
                clients = []
            else:
                clients = session.query(Client).all()
        
        client_ids = [c.id for c in clients]
        
        # Fetch payments within period
        if client_ids:
            payments = session.query(Payment).filter(
                Payment.client_id.in_(client_ids),
                Payment.payment_date >= start,
                Payment.payment_date <= end,
                Payment.status.in_(['paid', 'verified', 'approved'])
            ).all()
        else:
            payments = []
        
        total_collected = sum(p.amount or 0 for p in payments)
        
        # Breakdown by method
        by_method = {}
        for p in payments:
            method = (p.payment_method or 'efectivo').lower()
            by_method[method] = by_method.get(method, 0) + (p.amount or 0)
        
        # Collector earnings calculation
        # 1. Fetch assignments for this user
        assignments = getattr(user, 'assignments', [])
        collector_earnings = 0
        earnings_breakdown = []
        
        profit_pct = float(user.profit_percentage or 0) if hasattr(user, 'profit_percentage') else 0.0
        bonus = float(user.bonus_amount or 0) if hasattr(user, 'bonus_amount') else 0.0
        
        if assignments:
            # Calculate per assignment/router
            for a in assignments:
                # Payments for clients assigned to THIS specific router
                router_payments = [p for p in payments if p.client and p.client.router_id == a.router_id]
                subtotal = sum(p.amount or 0 for p in router_payments)
                
                # Formula: (Collected * %) + Fixed Bonus
                router_gain = (subtotal * (a.profit_percentage or 0) / 100) + (a.bonus_amount or 0)
                collector_earnings += router_gain
                
                earnings_breakdown.append({
                    'router_id': a.router_id,
                    'router_name': a.router.alias if a.router else 'N/A',
                    'collected': float(subtotal),
                    'profit_percentage': float(a.profit_percentage or 0),
                    'bonus_amount': float(a.bonus_amount or 0),
                    'earnings': float(router_gain)
                })
        else:
            # Fallback legacy logic (Backward compatibility)
            collector_earnings = (total_collected * profit_pct / 100) + bonus
            
            earnings_breakdown.append({
                'router_id': user.assigned_router_id,
                'router_name': user.assigned_router.alias if user.assigned_router else 'Global/Sin Router',
                'collected': float(total_collected),
                'profit_percentage': profit_pct,
                'bonus_amount': bonus,
                'earnings': float(collector_earnings)
            })
        
        # Expenses (Fixed and Variable)
        allowed_router_ids = set()
        if assignments:
            for a in assignments:
                allowed_router_ids.add(a.router_id)
        elif user.assigned_router_id:
            allowed_router_ids.add(user.assigned_router_id)

        expense_filters = [Expense.user_id == user.id]
        if allowed_router_ids:
            expense_filters.append(Expense.router_id.in_(allowed_router_ids))

        expenses = session.query(Expense).filter(
            or_(*expense_filters),
            Expense.expense_date >= start,
            Expense.expense_date <= end
        ).all()
        
        total_expenses = sum(e.amount or 0 for e in expenses)
        
        # Amount to send to company (Collected - Earnings - Expenses)
        amount_to_send = max(0, total_collected - collector_earnings - total_expenses)
        
        # Remittances sent to company (for this period)
        transfers = session.query(CollectorTransfer).filter(
            CollectorTransfer.user_id == user.id,
            CollectorTransfer.sent_at >= start,
            CollectorTransfer.sent_at <= end
        ).order_by(CollectorTransfer.sent_at.asc()).all()
        
        total_sent = sum(t.amount or 0 for t in transfers)
        balance_pending = max(0, amount_to_send - total_sent)
        
        # All-time first transfer
        first_ever = session.query(CollectorTransfer).filter(
            CollectorTransfer.user_id == user.id
        ).order_by(CollectorTransfer.sent_at.asc()).first()
        
        # Calculate effective values for the summary card
        effective_profit_pct = (collector_earnings / total_collected * 100) if total_collected > 0 else 0.0
        # If there's a fixed bonus, we might want to show it separately, but for the summary pct, 
        # usually users want to see the real weight of their earnings.
        
        return jsonify({
            'success': True,
            'user': {
                'id': user.id,
                'name': user.username,
                'role': user.role
            },
            'period': {
                'start': start.isoformat(),
                'end': end.isoformat()
            },
            'total_collected': float(total_collected),
            'by_method': {k: float(v) for k, v in by_method.items()},
            'payment_count': len(payments),
            'profit_percentage': round(effective_profit_pct, 1),
            'bonus_amount': bonus,  # Still show the global bonus if any, or maybe sum of assignment bonuses?
            'collector_earnings': float(collector_earnings),
            'total_expenses': float(total_expenses),
            'expenses': [e.to_dict() for e in expenses],
            'amount_to_send': float(amount_to_send),
            'total_sent_to_company': float(total_sent),
            'balance_pending': float(balance_pending),
            'first_ever_remittance': first_ever.sent_at.isoformat() if first_ever else None,
            'transfers_count': len(transfers),
            'earnings_breakdown': earnings_breakdown
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        session.close()


@collector_finance_bp.route('/transfers', methods=['GET'])
@login_required
def get_transfers():
    """Historial de envíos a la empresa del cobrador."""
    user = g.user
    session = get_session(engine)
    try:
        start, end = _get_date_range(request.args)
        
        transfers = session.query(CollectorTransfer).filter(
            CollectorTransfer.user_id == user.id,
            CollectorTransfer.sent_at >= start,
            CollectorTransfer.sent_at <= end
        ).order_by(CollectorTransfer.sent_at.desc()).all()
        
        return jsonify([t.to_dict() for t in transfers])
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        session.close()


@collector_finance_bp.route('/transfers', methods=['POST'])
@login_required
def create_transfer():
    """Registra un nuevo envío de dinero a la empresa."""
    user = g.user
    data = request.json or {}
    
    amount = data.get('amount')
    if not amount or float(amount) <= 0:
        return jsonify({'success': False, 'message': 'El monto debe ser mayor a 0'}), 400
    
    session = get_session(engine)
    try:
        target_user_id = data.get('user_id')
        is_admin = user.role in [UserRole.ADMIN.value, UserRole.ADMIN_FEM.value, UserRole.PARTNER.value]
        
        final_user_id = target_user_id if (target_user_id and is_admin) else user.id

        transfer = CollectorTransfer(
            user_id=final_user_id,
            amount=float(amount),
            method=data.get('method', 'transfer'),
            notes=data.get('notes', ''),
            sent_at=datetime.now()
        )
        session.add(transfer)
        session.commit()
        return jsonify({'success': True, 'data': transfer.to_dict()}), 201
    except Exception as e:
        session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        session.close()


@collector_finance_bp.route('/expenses', methods=['GET'])
@login_required
def get_collector_expenses():
    """Listado de gastos/descuentos aplicados al cobrador."""
    user = g.user
    session = get_session(engine)
    try:
        start, end = _get_date_range(request.args)
        
        # Filters
        target_user_id = request.args.get('user_id', type=int) or user.id
        
        target_user = session.query(User).get(target_user_id) if target_user_id != user.id else user
        
        allowed_router_ids = set()
        assignments = getattr(target_user, 'assignments', [])
        if assignments:
            for a in assignments:
                allowed_router_ids.add(a.router_id)
        elif target_user and target_user.assigned_router_id:
            allowed_router_ids.add(target_user.assigned_router_id)

        expense_filters = [Expense.user_id == target_user_id]
        if allowed_router_ids:
            expense_filters.append(Expense.router_id.in_(allowed_router_ids))

        expenses = session.query(Expense).filter(
            or_(*expense_filters),
            Expense.expense_date >= start,
            Expense.expense_date <= end
        ).order_by(Expense.expense_date.desc()).all()
        
        return jsonify([e.to_dict() for e in expenses])
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        session.close()


@collector_finance_bp.route('/expenses', methods=['POST'])
@login_required
def create_collector_expense():
    """Registra un nuevo gasto o descuento de cuadre."""
    # Solo administradores pueden crear gastos para cobradores
    if g.user.role not in [UserRole.ADMIN.value, UserRole.ADMIN_FEM.value, UserRole.PARTNER.value]:
        return jsonify({'success': False, 'message': 'No tienes permisos para registrar gastos'}), 403
        
    data = request.json or {}
    session = get_session(engine)
    try:
        expense = Expense(
            description=data.get('description'),
            amount=float(data.get('amount', 0)),
            category=data.get('category', 'variable'),
            user_id=data.get('user_id'),
            router_id=data.get('router_id'),
            expense_date=datetime.now(),
            created_by=g.user.username,
            is_recurring=data.get('is_recurring', False)
        )
        session.add(expense)
        session.commit()
        return jsonify({'success': True, 'data': expense.to_dict()}), 201
    except Exception as e:
        session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        session.close()
