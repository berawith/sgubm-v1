"""
Dashboard API Controller
Endpoints con DATOS REALES de la base de datos
"""
from flask import Blueprint, jsonify, render_template, g, request
from datetime import datetime, timedelta
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Router, Client
from src.application.services.auth import login_required, UserRole
import logging

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
def index():
    """Renderiza la página principal"""
    return render_template('index.html')





@dashboard_bp.route('/api/dashboard/stats')
@login_required
def get_stats():
    """
    Retorna estadísticas generales del sistema - DATOS REALES
    Filtrado por rol (RBAC)
    """
    db = get_db()
    router_repo = db.get_router_repository()
    client_repo = db.get_client_repository()
    payment_repo = db.get_payment_repository()
    
    user = g.user
    
    # Obtener routers filtrados por alcance del usuario
    is_restricted_role = user.role not in [UserRole.ADMIN.value, UserRole.ADMIN_FEM.value, UserRole.PARTNER.value]
    
    # Soporte para filtro por router_id en el query string (frecuente en el frontend)
    requested_router_id = request.args.get('router_id')
    try:
        requested_router_id = int(requested_router_id) if requested_router_id else None
    except (ValueError, TypeError):
        requested_router_id = None

    if is_restricted_role:
        # Combinar router legacy + nuevos assignments
        assigned_router_ids = set()
        
        # If the user has explicitly defined router assignments (Multi-router feature), use ONLY those.
        has_assignments = hasattr(user, 'assignments') and len(user.assignments) > 0
        
        if has_assignments:
            for assignment in user.assignments:
                assigned_router_ids.add(assignment.router_id)
        elif user.assigned_router_id:
            assigned_router_ids.add(user.assigned_router_id)
            
        allowed_router_ids = list(assigned_router_ids)
        
        # Si pide un router específico, validar que tenga acceso
        if requested_router_id:
            if requested_router_id in allowed_router_ids:
                router_ids = [requested_router_id]
            else:
                # No tiene acceso al router solicitado
                router_ids = []
        else:
            router_ids = allowed_router_ids
            
        if router_ids:
            routers = router_repo.session.query(Router).filter(Router.id.in_(router_ids)).all()
        else:
            routers = []
    else:
        # Administrador: puede filtrar por cualquier router o ver todos
        if requested_router_id:
            routers = [router_repo.get_by_id(requested_router_id)]
            routers = [r for r in routers if r]
        else:
            routers = router_repo.get_all()
        
    router_ids = [r.id for r in routers]
        
    # Comparación robusta status (String)
    routers_online = [r for r in routers if str(r.status).lower() == 'online']
    routers_offline = [r for r in routers if str(r.status).lower() == 'offline']
    routers_warning = [r for r in routers if str(r.status).lower() == 'warning']
    
    # Obtener clientes
    clients_raw = client_repo.get_all()
    
    # Filtrar clientes por zona si tiene acceso restringido
    if is_restricted_role:
        clients_raw = [c for c in clients_raw if c.router_id in router_ids]
        
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
            
            # Conectividad SÓLO para activos
            if c.is_online:
                online_clients += 1
            else:
                offline_clients += 1
        elif status == 'suspended':
            suspended_clients += 1
        elif status == 'inactive':
            inactive_clients += 1
            
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
    
    # Filtrar revenue por routers asignados si restringido O si se solicitó uno específico
    should_filter_revenue = is_restricted_role or requested_router_id
    revenue = payment_repo.get_total_by_date_range(
        month_start, 
        month_end, 
        router_ids=router_ids if should_filter_revenue else None
    )
    
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
@login_required
def get_recent_activity():
    """
    Retorna actividad reciente del sistema - DATOS REALES
    """
    try:
        db = get_db()
        payment_repo = db.get_payment_repository()
        client_repo = db.get_client_repository()
        router_repo = db.get_router_repository()
        
        user = g.user
        
        activities = []
        
        # Últimos pagos
        try:
            recent_payments = payment_repo.get_all(limit=50) # Aumentar para filtrar
            added_payments = 0
            
            is_restricted_role = user.role not in [UserRole.ADMIN.value, UserRole.ADMIN_FEM.value, UserRole.PARTNER.value]
            
            allowed_router_ids = set()
            if is_restricted_role:
                has_assignments = hasattr(user, 'assignments') and len(user.assignments) > 0
                
                if has_assignments:
                    for a in user.assignments:
                        allowed_router_ids.add(a.router_id)
                elif user.assigned_router_id:
                    allowed_router_ids.add(user.assigned_router_id)
            
            for payment in recent_payments:
                if is_restricted_role and allowed_router_ids:
                    if not payment.client or payment.client.router_id not in allowed_router_ids:
                        continue
                        
                if added_payments >= 5:
                    break
                    
                if payment and payment.payment_date:
                    time_diff = datetime.now() - payment.payment_date
                    
                    client_name = payment.client.legal_name if payment.client else 'Cliente'
                    
                    activities.append({
                        'type': 'payment',
                        'message': f"Pago recibido: {client_name} - ${payment.amount:.2f}",
                        'timestamp': payment.payment_date.isoformat()
                    })
                    added_payments += 1
        except Exception as e:
            print(f"Error loading payments: {e}")
        
        # Clientes suspendidos recientemente
        try:
            suspended_clients = client_repo.get_by_status('suspended')
            
            if is_restricted_role and allowed_router_ids:
                suspended_clients = [c for c in suspended_clients if c.router_id in allowed_router_ids]
                
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
