"""
Dashboard API Controller
Endpoints con DATOS REALES de la base de datos
"""
from flask import Blueprint, jsonify, render_template
from datetime import datetime, timedelta
from src.infrastructure.database.db_manager import get_db
import logging

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
def index():
    """Renderiza la página principal"""
    return render_template('index.html')





@dashboard_bp.route('/api/dashboard/stats')
def get_stats():
    """
    Retorna estadísticas generales del sistema - DATOS REALES
    """
    db = get_db()
    router_repo = db.get_router_repository()
    client_repo = db.get_client_repository()
    payment_repo = db.get_payment_repository()
    
    # Obtener routers
    routers = router_repo.get_all()
    # Comparación robusta status (String)
    routers_online = [r for r in routers if str(r.status).lower() == 'online']
    routers_offline = [r for r in routers if str(r.status).lower() == 'offline']
    routers_warning = [r for r in routers if str(r.status).lower() == 'warning']
    
    # Obtener todos los clientes de la BD
    clients_raw = client_repo.get_all()
    
    # Auto-repair: Corregir clientes sin status
    for c in clients_raw:
        if not c.status or str(c.status).strip() == '':
            logger.warning(f"Auto-repairing client {c.id} status to 'active'")
            c.status = 'active'
            client_repo.update(c.id, {'status': 'active'})
            # No commit here to speed up, handle via repo or batch if needed. 
            # Repositorie's update usually commits.

    # Filtrar clientes eliminados para estadísticas operativas
    clients_total_operational = [c for c in clients_raw if str(c.status).lower() != 'deleted']
    clients_deleted = [c for c in clients_raw if str(c.status).lower() == 'deleted']

    # Comparación robusta status (String)
    clients_active = [c for c in clients_total_operational if str(c.status).lower() == 'active']
    clients_suspended = [c for c in clients_total_operational if str(c.status).lower() == 'suspended']
    
    # Calcular revenue del mes actual (Recaudación Real)
    today = datetime.utcnow()
    month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_end = today
    revenue = payment_repo.get_total_by_date_range(month_start, month_end)
    
    # Calcular Facturación Proyectada (Suma de mensualidades de clientes activos)
    projected_revenue = sum(c.monthly_fee for c in clients_active if c.monthly_fee)

    # Calcular uptime promedio
    uptime_values = []
    for router in routers:
        if router.uptime and '%' in router.uptime:
            try:
                val = router.uptime.replace('%', '').strip()
                if val.replace('.','').isdigit():
                    uptime_values.append(float(val))
            except:
                pass
    
    avg_uptime = sum(uptime_values) / len(uptime_values) if uptime_values else 0
    
    # Calcular Deuda Total (Pendiente por Recaudar de clientes operativos)
    total_debt = sum(c.account_balance for c in clients_total_operational if c.account_balance > 0)
    clients_with_debt = sum(1 for c in clients_total_operational if c.account_balance > 0)

    stats = {
        'total_servers': len(routers),
        'servers_online': len(routers_online),
        'servers_warning': len(routers_warning),
        'servers_offline': len(routers_offline),
        'total_clients': len(clients_total_operational),
        'active_clients': len(clients_active),
        'suspended_clients': len(clients_suspended),
        'inactive_clients': len([c for c in clients_total_operational if str(c.status).lower() == 'inactive']),
        'archived_clients': len(clients_deleted),
        'monthly_revenue': float(revenue or 0),
        'projected_revenue': float(projected_revenue or 0),
        'average_uptime': round(avg_uptime, 1),
        'total_pending_debt': float(total_debt or 0),
        'pending_debt_clients': clients_with_debt
    }
    
    # DEBUG: Log breakdown count
    other_status_count = len(clients_raw) - len(clients_active) - len(clients_suspended)
    if other_status_count > 0:
        others = [f"{c.id}:{c.status}" for c in clients_raw if str(c.status).lower() not in ['active', 'suspended']]
        print(f"DEBUG DASHBOARD: Total={len(clients_raw)}, Active={len(clients_active)}, Suspended={len(clients_suspended)}, OTHERS={other_status_count}")
        print(f"   --> Missing statuses: {others}")
    
    return jsonify(stats)


@dashboard_bp.route('/api/activity/recent')
def get_recent_activity():
    """
    Retorna actividad reciente del sistema - DATOS REALES
    """
    try:
        db = get_db()
        payment_repo = db.get_payment_repository()
        client_repo = db.get_client_repository()
        router_repo = db.get_router_repository()
        
        activities = []
        
        # Últimos pagos
        try:
            recent_payments = payment_repo.get_all(limit=5)
            for payment in recent_payments:
                if payment and payment.payment_date:
                    time_diff = datetime.utcnow() - payment.payment_date
                    
                    client_name = payment.client.legal_name if payment.client else 'Cliente'
                    
                    activities.append({
                        'type': 'payment',
                        'message': f"Pago recibido: {client_name} - ${payment.amount:.2f}",
                        'timestamp': payment.payment_date.isoformat()
                    })
        except Exception as e:
            print(f"Error loading payments: {e}")
        
        # Clientes suspendidos recientemente
        try:
            suspended_clients = client_repo.get_by_status('suspended')
            for client in suspended_clients[:3]:
                if client and client.updated_at:
                    time_diff = datetime.utcnow() - client.updated_at
                    if time_diff.days < 7:  # Última semana
                        activities.append({
                            'type': 'client',
                            'message': f"Cliente suspendido: {client.legal_name} - {client.subscriber_code}",
                            'timestamp': client.updated_at.isoformat()
                        })
        except Exception as e:
            print(f"Error loading suspended clients: {e}")
        
        # Routers sincronizados
        try:
            routers = router_repo.get_all()
            for router in routers[:2]:
                if router and router.last_sync:
                    time_diff = datetime.utcnow() - router.last_sync
                    if time_diff.total_seconds() < 3600:
                        activities.append({
                            'type': 'server',
                            'message': f"Router sincronizado: {router.alias}",
                            'timestamp': router.last_sync.isoformat()
                        })
        except Exception as e:
            print(f"Error loading routers: {e}")
        
        # Ordenar por timestamp descendente
        activities.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        return jsonify(activities[:10])
    
    except Exception as e:
        print(f"Error in get_recent_activity: {e}")
        # Retornar array vacío en caso de error
        return jsonify([])
