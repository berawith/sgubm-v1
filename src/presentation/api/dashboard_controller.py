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
    
    # Obtener todos los clientes de la BD de una sola vez
    clients_raw = client_repo.get_all()
    
    # Índices para calcular todo en una sola pasada
    total_clients = 0
    active_clients = 0
    suspended_clients = 0
    online_clients = 0
    offline_clients = 0
    paid_clients = 0
    inactive_clients = 0
    archived_clients = 0
    projected_revenue = 0
    total_debt = 0
    clients_with_debt = 0

    for c in clients_raw:
        status = str(c.status).lower() if c.status else 'active' # Fallback sin persistir en cada GET
        
        if status == 'deleted':
            archived_clients += 1
            continue
            
        total_clients += 1
        
        if status == 'active':
            active_clients += 1
            projected_revenue += (c.monthly_fee or 0)
        elif status == 'suspended':
            suspended_clients += 1
        elif status == 'inactive':
            inactive_clients += 1
            
        if c.is_online:
            online_clients += 1
        else:
            offline_clients += 1
            
        balance = (c.account_balance or 0)
        if balance <= 0:
            paid_clients += 1
        else:
            total_debt += balance
            clients_with_debt += 1

    # Calcular revenue del mes actual (Recaudación Real)
    today = datetime.now()
    month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_end = today
    revenue = payment_repo.get_total_by_date_range(month_start, month_end)
    
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
    
    stats = {
        'total_servers': len(routers),
        'servers_online': len(routers_online),
        'servers_warning': len(routers_warning),
        'servers_offline': len(routers_offline),
        'total_clients': total_clients,
        'active_clients': active_clients,
        'suspended_clients': suspended_clients,
        'online_clients': online_clients,
        'offline_clients': offline_clients,
        'paid_clients': paid_clients,
        'inactive_clients': inactive_clients,
        'archived_clients': archived_clients,
        'monthly_revenue': float(revenue or 0),
        'projected_revenue': float(projected_revenue or 0),
        'average_uptime': round(avg_uptime, 1),
        'total_pending_debt': float(total_debt or 0),
        'pending_debt_clients': clients_with_debt
    }
    
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
                    time_diff = datetime.now() - payment.payment_date
                    
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
                    time_diff = datetime.now() - client.updated_at
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
                    time_diff = datetime.now() - router.last_sync
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
