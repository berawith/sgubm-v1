import os
import uuid
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, g, current_app
from werkzeug.utils import secure_filename

from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import SupportTicket, UserRole
from src.application.services.auth import login_required, admin_required

logger = logging.getLogger(__name__)

support_bp = Blueprint('support', __name__, url_prefix='/api/support')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@support_bp.route('', methods=['POST'])
@login_required
def create_ticket():
    """Crea un nuevo ticket de soporte con imagen adjunta opcional"""
    user = g.user
    
    # Multipart Form Data
    client_id = request.form.get('client_id')
    subject = request.form.get('subject')
    description = request.form.get('description')
    
    if not client_id or not subject or not description:
        return jsonify({'error': 'Faltan campos obligatorios'}), 400
        
    db = get_db()
    
    image_path = None
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename and allowed_file(file.filename):
            # Usar dirname de current_app.root_path para estar seguro, o rutas absolutas
            upload_folder = os.path.join('src', 'presentation', 'web', 'static', 'uploads', 'support')
            os.makedirs(upload_folder, exist_ok=True)
            
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = f"ticket_{uuid.uuid4().hex}.{ext}"
            file_path = os.path.join(upload_folder, filename)
            
            file.save(file_path)
            # Ruta pública para el navegador
            image_path = f"/static/uploads/support/{filename}"
            
    try:
        new_ticket = SupportTicket(
            client_id=int(client_id),
            user_id=user.id,
            subject=subject,
            description=description,
            status='open',
            image_path=image_path
        )
        db.session.add(new_ticket)
        db.session.commit()
        
        # REAL-TIME SYNC (TENANT-SCOPED)
        from src.application.events.event_bus import get_event_bus, SystemEvents
        get_event_bus().publish(SystemEvents.SUPPORT_TICKET_CREATED, {
            'event_type': SystemEvents.SUPPORT_TICKET_CREATED,
            'ticket': new_ticket.to_dict(),
            'tenant_id': g.tenant_id
        })
            
        return jsonify(new_ticket.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating support ticket: {e}")
        return jsonify({'error': 'Error interno guardando el ticket'}), 500


@support_bp.route('', methods=['GET'])
@login_required
def get_tickets():
    """Obtiene tickets. Admin ve todos, Collector ve los suyos."""
    user = g.user
    db = get_db()
    
    query = db.session.query(SupportTicket)
    
    # Si no es admin, filtramos por sus tickets
    if user.role not in [UserRole.ADMIN.value, UserRole.ADMIN_FEM.value, UserRole.PARTNER.value, UserRole.TECHNICAL.value]:
        query = query.filter(SupportTicket.user_id == user.id)
        
    # Ordenar por creados más recientes primero
    tickets = query.order_by(SupportTicket.created_at.desc()).all()
    
    return jsonify([t.to_dict() for t in tickets])


@support_bp.route('/<int:ticket_id>/status', methods=['PUT'])
@login_required
def update_ticket_status(ticket_id):
    """Actualiza el estado de un ticket. Solo admins/tecnicos pueden resolverlo."""
    user = g.user
    db = get_db()
    
    # Solo roles privilegiados
    if user.role not in [UserRole.ADMIN.value, UserRole.ADMIN_FEM.value, UserRole.PARTNER.value, UserRole.TECHNICAL.value, UserRole.SECRETARY.value]:
        return jsonify({'error': 'No tienes permisos para cambiar el estado'}), 403
        
    data = request.json
    status = data.get('status')
    
    if status not in ['open', 'in_progress', 'resolved', 'cancelled']:
        return jsonify({'error': 'Estado inválido'}), 400
        
    ticket = db.session.query(SupportTicket).get(ticket_id)
    if not ticket:
        return jsonify({'error': 'Ticket no encontrado'}), 404
        
    ticket.status = status
    
    if status == 'resolved':
        ticket.resolved_at = datetime.now()
        # Campos de resolución (V3)
        ticket.actual_failure = data.get('actual_failure')
        ticket.resolution_details = data.get('resolution_details')
        ticket.technicians = data.get('technicians')
        ticket.materials_used = data.get('materials_used')
        ticket.support_cost = float(data.get('support_cost', 0.0))
        ticket.admin_observations = data.get('admin_observations')
        
        support_date_str = data.get('support_date')
        if support_date_str:
            try:
                ticket.support_date = datetime.fromisoformat(support_date_str.replace('Z', ''))
            except:
                ticket.support_date = datetime.now()
        else:
            ticket.support_date = datetime.now()
            
    elif status == 'open':
        # Revertir resolución si es el caso
        ticket.resolved_at = None
        
    try:
        db.session.commit()
        
        # REAL-TIME SYNC (TENANT-SCOPED)
        from src.application.events.event_bus import get_event_bus, SystemEvents
        get_event_bus().publish(SystemEvents.SUPPORT_TICKET_UPDATED, {
            'event_type': SystemEvents.SUPPORT_TICKET_UPDATED,
            'ticket': ticket.to_dict(),
            'tenant_id': g.tenant_id
        })
            
        return jsonify(ticket.to_dict())
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating ticket status: {e}")
        return jsonify({'error': 'Error actualizando ticket'}), 500


@support_bp.route('/stats', methods=['GET'])
@login_required
def get_support_stats():
    """Obtiene estadísticas de soporte para el dashboard administrativo"""
    db = get_db()
    
    # Solo admins/socio/secretaria
    user = g.user
    if user.role not in [UserRole.ADMIN.value, UserRole.ADMIN_FEM.value, UserRole.PARTNER.value, UserRole.SECRETARY.value]:
        return jsonify({'error': 'Acceso denegado'}), 403
        
    try:
        total = db.session.query(SupportTicket).count()
        resolved = db.session.query(SupportTicket).filter(SupportTicket.status == 'resolved').count()
        open_tickets = db.session.query(SupportTicket).filter(SupportTicket.status == 'open').count()
        cancelled = db.session.query(SupportTicket).filter(SupportTicket.status == 'cancelled').count()
        
        # Calcular tiempo promedio de resolución (en horas)
        resolved_tickets = db.session.query(SupportTicket).filter(SupportTicket.status == 'resolved').all()
        avg_resolution_hours = 0
        if resolved_tickets:
            total_hours = 0
            count = 0
            for t in resolved_tickets:
                if t.resolved_at and t.created_at:
                    diff = t.resolved_at - t.created_at
                    total_hours += diff.total_seconds() / 3600
                    count += 1
            if count > 0:
                avg_resolution_hours = round(total_hours / count, 1)
                
        # Ingresos por soporte (opcional, si cobran)
        total_revenue = sum([t.support_cost or 0 for t in resolved_tickets])
        
        return jsonify({
            'total': total,
            'resolved': resolved,
            'open': open_tickets,
            'cancelled': cancelled,
            'avg_resolution_hours': avg_resolution_hours,
            'total_revenue': total_revenue,
            'efficiency_pct': round((resolved / total * 100), 1) if total > 0 else 0
        })
    except Exception as e:
        logger.error(f"Error fetching support stats: {e}")
        return jsonify({'error': 'Error calculando estadísticas'}), 500
