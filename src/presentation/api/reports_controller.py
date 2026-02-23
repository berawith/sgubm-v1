"""
Reports API Controller
Advanced financial and management reporting - DATOS REALES
"""
from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
from typing import List, Dict, Any
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import ClientStatus, Client, Payment
import logging

logger = logging.getLogger(__name__)

reports_bp = Blueprint('reports', __name__, url_prefix='/api/reports')
@reports_bp.route('/financial', methods=['GET'])
def get_financial_reports():
    """
    Análisis financiero avanzado: Trimestral, Semestral, Anual.
    Compara Recaudo Real vs Facturación Teórica.
    """
    period = request.args.get('period', 'annual') # quarter, semester, annual
    year = request.args.get('year', datetime.now().year, type=int)
    router_id = request.args.get('router_id', type=int)
    
    db = get_db()
    payment_repo = db.get_payment_repository()
    client_repo = db.get_client_repository()
    
    try:
        now = datetime.now()
        
        # 1. Obtener todos los clientes operativos
        all_clients = client_repo.get_filtered(router_id=router_id, status='ALL') if router_id else client_repo.get_all()
        working_clients = [c for c in all_clients if str(c.status).lower() in ['active', 'suspended', 'deleted']]
        
        # 2. Calcular datos mensuales base (12 meses)
        monthly_stats = []
        for month in range(1, 13):
            start_dt = datetime(year, month, 1)
            # Fin del mes
            if month == 12:
                end_dt = datetime(year + 1, 1, 1) - timedelta(seconds=1)
            else:
                end_dt = datetime(year, month + 1, 1) - timedelta(seconds=1)
            
            if start_dt > now: continue
                
            clients_active = []
            clients_lost = []
            
            for c in working_clients:
                if not c.created_at or c.created_at > end_dt:
                    continue
                
                if str(c.status).lower() == 'deleted':
                    if c.updated_at and c.updated_at < start_dt:
                        continue
                    clients_lost.append(c)
                else:
                    clients_active.append(c)

            t_active = float(sum((c.monthly_fee or 0) for c in clients_active))
            t_lost = float(sum((c.monthly_fee or 0) for c in clients_lost))
            t_total = t_active + t_lost
            
            # Solo incluir mes si tiene meta o si es el mes actual
            if t_total == 0 and start_dt.year < now.year:
                continue
                
            collected = float(payment_repo.get_total_by_date_range(start_dt, end_dt, router_id=router_id) or 0)
            
            monthly_stats.append({
                'label': start_dt.strftime('%B'),
                'month': month,
                'year': year,
                'start_dt': start_dt,
                'end_dt': end_dt,
                'collected': collected,
                'theoretical': t_total,
                'theoretical_active': t_active,
                'theoretical_lost': t_lost,
                'loss': max(0, t_total - collected)
            })

        # 3. Agrupar resultados según el periodo solicitado
        results = []
        if period == 'annual':
            # Ya son mensuales por defecto
            for m in monthly_stats:
                m['performance'] = (m['collected'] / m['theoretical'] * 100) if m['theoretical'] > 0 else 0
                results.append(m)
        
        elif period == 'quarter':
            # Agrupar de a 3
            for q in range(1, 5):
                m_indices = [(q-1)*3 + 1, (q-1)*3 + 2, (q-1)*3 + 3]
                q_months = [m for m in monthly_stats if m['month'] in m_indices]
                if not q_months: continue
                
                q_start = q_months[0]['start_dt']
                q_end = q_months[-1]['end_dt']
                
                q_theoretical = sum(m['theoretical'] for m in q_months)
                q_collected = sum(m['collected'] for m in q_months)
                
                results.append({
                    'label': f'T{q} ({q_start.strftime("%b")}-{q_end.strftime("%b")})',
                    'period_num': q,
                    'year': year,
                    'start_dt': q_start,
                    'end_dt': q_end,
                    'collected': q_collected,
                    'theoretical': q_theoretical,
                    'theoretical_active': sum(m['theoretical_active'] for m in q_months),
                    'theoretical_lost': sum(m['theoretical_lost'] for m in q_months),
                    'loss': max(0, q_theoretical - q_collected),
                    'performance': (q_collected / q_theoretical * 100) if q_theoretical > 0 else 0
                })
        
        elif period == 'semester':
            # Agrupar de a 6
            for s in [1, 2]:
                m_indices = range(1, 7) if s == 1 else range(7, 13)
                s_months = [m for m in monthly_stats if m['month'] in m_indices]
                if not s_months: continue
                
                s_start = s_months[0]['start_dt']
                s_end = s_months[-1]['end_dt']
                
                s_theoretical = sum(m['theoretical'] for m in s_months)
                s_collected = sum(m['collected'] for m in s_months)
                
                results.append({
                    'label': f'S{s} ({s_start.strftime("%b")}-{s_end.strftime("%b")})',
                    'period_num': s,
                    'year': year,
                    'start_dt': s_start,
                    'end_dt': s_end,
                    'collected': s_collected,
                    'theoretical': s_theoretical,
                    'theoretical_active': sum(m['theoretical_active'] for m in s_months),
                    'theoretical_lost': sum(m['theoretical_lost'] for m in s_months),
                    'loss': max(0, s_theoretical - s_collected),
                    'performance': (s_collected / s_theoretical * 100) if s_theoretical > 0 else 0
                })
        
        # Resumen general
        total_theoretical = float(sum(r['theoretical'] for r in results))
        total_theoretical_active = float(sum(r['theoretical_active'] for r in results))
        total_theoretical_lost = float(sum(r['theoretical_lost'] for r in results))
        total_collected = float(sum(r['collected'] for r in results))
        
        summary = {
            'total_theoretical': total_theoretical,
            'total_theoretical_active': total_theoretical_active,
            'total_theoretical_lost': total_theoretical_lost,
            'total_collected': total_collected,
            'total_loss': max(0, total_theoretical - total_collected),
            'overall_performance': (total_collected / total_theoretical * 100) if total_theoretical > 0 else 0,
            'active_clients_count': len([c for c in working_clients if str(c.status).lower() == 'active']),
            'status_distribution': {
                'active': len([c for c in all_clients if str(c.status).lower() == 'active' and c.is_online]),
                'suspended': len([c for c in all_clients if str(c.status).lower() == 'suspended']),
                'retired': len([c for c in all_clients if str(c.status).lower() == 'deleted']),
                'offline': len([c for c in all_clients if str(c.status).lower() == 'active' and not c.is_online])
            },
            'loss_by_router': _calculate_loss_by_router(db, results, working_clients, router_id)
        }
        
        # Limpiar/Convertir datetimes para JSON
        for r in results:
            if 'start_dt' in r: r['start_dt'] = r['start_dt'].strftime('%Y-%m-%d')
            if 'end_dt' in r: r['end_dt'] = r['end_dt'].strftime('%Y-%m-%d')

        return jsonify({
            'period': period,
            'year': year,
            'summary': summary,
            'breakdown': results
        })
        
    except Exception as e:
        logger.exception("Error in get_financial_reports")
        return jsonify({'error': str(e)}), 500

def _calculate_loss_by_router(db, period_results, working_clients, filtered_router_id):
    """Calcula el desglose de pérdida por router."""
    router_stats = {}
    payment_repo = db.get_payment_repository()
    
    # Agrupar clientes por router
    clients_by_router = {}
    for c in working_clients:
        rid = c.router_id
        if rid not in clients_by_router:
            clients_by_router[rid] = {'alias': c.router.alias if c.router else f"Router {rid}", 'clients': []}
        clients_by_router[rid]['clients'].append(c)

    for rid, data in clients_by_router.items():
        if filtered_router_id and rid != filtered_router_id:
            continue
            
        total_theoretical = 0
        total_collected = 0
        unpaid_count = 0
        
        # Para cada periodo en los resultados
        for m in period_results:
            start_dt = m['start_dt']
            end_dt = m['end_dt']
                
            # Calcular meta para este router en este periodo
            period_theoretical = 0
            for c in data['clients']:
                # Mismo filtro que el reporte principal
                if not c.created_at or c.created_at > end_dt:
                    continue
                if str(c.status).lower() == 'deleted' and c.updated_at and c.updated_at < start_dt:
                    continue
                period_theoretical += (c.monthly_fee or 0)
            
            period_collected = float(payment_repo.get_total_by_date_range(start_dt, end_dt, router_id=rid) or 0)
            
            total_theoretical += period_theoretical
            total_collected += period_collected
            
            # Estimación de clientes que no pagaron (Si lo recolectado < meta)
            if period_theoretical > period_collected:
                diff = period_theoretical - period_collected
                avg_fee = period_theoretical / len(data['clients']) if data['clients'] else 1
                unpaid_count += round(diff / avg_fee) if avg_fee > 0 else 0

        loss = max(0, total_theoretical - total_collected)
        if loss > 0 or total_theoretical > 0:
            router_stats[data['alias']] = {
                'loss': float(loss),
                'theoretical': float(total_theoretical),
                'collected': float(total_collected),
                'unpaid_estimate': int(unpaid_count)
            }
            
    return router_stats

@reports_bp.route('/clients-status', methods=['GET'])
def get_clients_status_report():
    """
    Listado detallado de clientes según su estado para impresión/gestión.
    Tipos: 'paid', 'missing', 'debtors', 'deleted'
    """
    report_type = request.args.get('type', 'debtors')
    router_id = request.args.get('router_id', type=int)
    audit_day = request.args.get('day', type=int)
    audit_month = request.args.get('month', datetime.now().month, type=int)
    audit_year = request.args.get('year', datetime.now().year, type=int)
    
    db = get_db()
    client_repo = db.get_client_repository()
    payment_repo = db.get_payment_repository()
    
    try:
        # Obtener todos los clientes operativos (excluyendo archivados para el cálculo base)
        all_clients = client_repo.get_filtered(router_id=router_id, status='ALL')
        
        # El periodo de auditoría solicitado
        if audit_day:
            audit_start = datetime(audit_year, audit_month, audit_day)
            audit_end = datetime(audit_year, audit_month, audit_day, 23, 59, 59)
        else:
            audit_start = datetime(audit_year, audit_month, 1)
            if audit_month == 12:
                audit_end = datetime(audit_year + 1, 1, 1) - timedelta(seconds=1)
            else:
                audit_end = datetime(audit_year, audit_month + 1, 1) - timedelta(seconds=1)
        
        # Auditoría de ciclo y pagos
        invoice_repo = db.get_invoice_repository()
        period_invoices = invoice_repo.get_by_date_range(audit_start, audit_end, router_id=router_id)
        period_payments = payment_repo.get_by_date_range(audit_start, audit_end, router_id=router_id)
        
        cycle_exists = len(period_invoices) > 0
        has_payments = len(period_payments) > 0
        
        # Mapa de cuánto pagó cada cliente en este periodo
        paid_map = {}
        for p in period_payments:
            if p.client_id:
                paid_map[p.client_id] = paid_map.get(p.client_id, 0) + p.amount
        
        # --- FILTRADO DE CLIENTES SEGÚN TIPO DE REPORTE ---
        results_list = []
        if report_type == 'debtors':
            # Clientes con balance > 0
            results_list = [c for c in all_clients if (c.account_balance or 0) > 0 and c.status != 'deleted']
        elif report_type == 'paid':
            # Clientes que han pagado en el periodo solicitado
            paid_client_ids = set(paid_map.keys())
            results_list = [c for c in all_clients if c.id in paid_client_ids and c.status != 'deleted']
        elif report_type == 'missing':
            # Clientes activos que NO han pagado en el periodo
            paid_client_ids = set(paid_map.keys())
            results_list = [c for c in all_clients if str(c.status).lower() == 'active' and c.id not in paid_client_ids]
        elif report_type == 'deleted':
            results_list = [c for c in all_clients if c.status == 'deleted']
        
        # --- CÁLCULO DE TOTALES SENSIBLES AL FILTRO ---
        # Si el usuario filtra por un tipo, los totales en las tarjetas superiores deben reflejar ese grupo
        total_collected = sum(paid_map.get(c.id, 0) for c in results_list)
        total_pending = sum(c.account_balance for c in results_list if (c.account_balance or 0) > 0)
        total_credit = sum(abs(c.account_balance) for c in results_list if (c.account_balance or 0) < 0)
        
        # Preparar data final
        clients_data = []
        for c in results_list:
            clients_data.append({
                'id': c.id,
                'name': c.legal_name,
                'code': c.subscriber_code,
                'balance': float(c.account_balance or 0),
                'fee': float(c.monthly_fee or 0),
                'paid_amount': float(paid_map.get(c.id, 0)),
                'status': str(c.status),
                'address': c.address,
                'phone': c.phone,
                'router': c.router.alias if c.router else 'N/A'
            })
            
        return jsonify({
            'type': report_type,
            'count': len(clients_data),
            'router_id': router_id,
            'day': audit_day,
            'month': audit_month,
            'year': audit_year,
            'cycle_exists': cycle_exists,
            'has_payments': has_payments,
            'total_collected': float(total_collected),
            'total_pending': float(total_pending),
            'total_credit': float(total_credit),
            'clients': clients_data
        })
        
    except Exception as e:
        logger.exception("Error in get_clients_status_report")
        return jsonify({'error': str(e)}), 500

@reports_bp.route('/performance', methods=['GET'])
def get_performance_report():
    """
    Reporte de métricas de crecimiento, eficiencia y churn.
    """
    db = get_db()
    client_repo = db.get_client_repository()
    payment_repo = db.get_payment_repository()
    
    try:
        now = datetime.now()
        # 12 meses atrás
        months = []
        for i in range(11, -1, -1):
            # Obtener primer día de cada mes
            month_date = (now.replace(day=1) - timedelta(days=i*30)).replace(day=1)
            # Rebalancear si el cálculo anterior falló por meses de diferente duración
            # Mejor forma:
            temp_date = now.replace(day=1)
            for _ in range(i):
                last_day_prev_month = temp_date - timedelta(days=1)
                temp_date = last_day_prev_month.replace(day=1)
            months.append(temp_date.replace(hour=0, minute=0, second=0))

        # Evitar duplicados si i=0 o similar
        seen_months = set()
        unique_months = []
        for m in months:
            m_key = f"{m.year}-{m.month}"
            if m_key not in seen_months:
                unique_months.append(m)
                seen_months.add(m_key)
        
        all_clients = client_repo.get_all()
        
        breakdown = []
        for m_start in unique_months:
            if m_start.month == 12:
                m_end = datetime(m_start.year + 1, 1, 1) - timedelta(seconds=1)
            else:
                m_end = datetime(m_start.year, m_start.month + 1, 1) - timedelta(seconds=1)
            
            if m_start > now: continue

            # Altas en este mes
            new_clients = [c for c in all_clients if c.created_at and m_start <= c.created_at <= m_end]
            # Bajas en este mes (usando updated_at como proxy si status es deleted)
            churned = [c for c in all_clients if str(c.status).lower() == 'deleted' and c.updated_at and m_start <= c.updated_at <= m_end]
            
            # Base instalada al final del mes
            installed_base = [c for c in all_clients if c.created_at and c.created_at <= m_end and 
                              (str(c.status).lower() != 'deleted' or (c.updated_at and c.updated_at > m_end))]
            
            collected = float(payment_repo.get_total_by_date_range(m_start, m_end) or 0)
            theoretical = float(sum((c.monthly_fee or 0) for c in installed_base))
            
            breakdown.append({
                'month': m_start.strftime('%B %Y'),
                'new_sales': len(new_clients),
                'churn': len(churned),
                'net_growth': len(new_clients) - len(churned),
                'total_base': len(installed_base),
                'efficiency': (collected / theoretical * 100) if theoretical > 0 else 0,
                'revenue': collected
            })

        return jsonify({
            'period': '12 months',
            'summary': {
                'total_new': sum(b['new_sales'] for b in breakdown),
                'total_churn': sum(b['churn'] for b in breakdown),
                'avg_efficiency': sum(b['efficiency'] for b in breakdown) / len(breakdown) if breakdown else 0
            },
            'breakdown': breakdown
        })
    except Exception as e:
        logger.error(f"Error in performance report: {e}")
        return jsonify({'error': str(e)}), 500
