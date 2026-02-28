from flask import Blueprint, request, jsonify, g
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import SystemIncident, UserRole
from src.application.services.auth import login_required, admin_required
from datetime import datetime

reciclador_bp = Blueprint('reciclador', __name__, url_prefix='/api/reciclador')

@reciclador_bp.route('/incidents', methods=['GET'])
@login_required
@admin_required
def get_incidents():
    """Obtiene la lista de incidentes capturados por el centinela"""
    db = get_db()
    
    # Filtros
    status = request.args.get('status', 'new')
    severity = request.args.get('severity')
    category = request.args.get('category')
    limit = int(request.args.get('limit', 50))
    
    query = db.session.query(SystemIncident)
    
    if status != 'all':
        query = query.filter(SystemIncident.status == status)
    if severity:
        query = query.filter(SystemIncident.severity == severity)
    if category:
        query = query.filter(SystemIncident.category == category)
        
    incidents = query.order_by(SystemIncident.created_at.desc()).limit(limit).all()
    
    return jsonify([i.to_dict() for i in incidents])

@reciclador_bp.route('/incidents/<int:incident_id>', methods=['GET'])
@login_required
@admin_required
def get_incident_details(incident_id):
    """Obtiene el detalle completo de un incidente, incluyendo stack trace"""
    db = get_db()
    incident = db.session.query(SystemIncident).get(incident_id)
    
    if not incident:
        return jsonify({'error': 'Incidente no encontrado'}), 404
        
    # El to_dict estándar suele omitir el stack para no sobrecargar las listas
    data = incident.to_dict()
    data['stack_trace'] = incident.stack_trace
    data['request_payload'] = incident.request_payload
    data['request_params'] = incident.request_params
    data['environment_meta'] = incident.environment_meta
    
    return jsonify(data)

@reciclador_bp.route('/incidents/<int:incident_id>/resolve', methods=['PUT'])
@login_required
@admin_required
def resolve_incident(incident_id):
    """Marca un incidente como resuelto con notas de reparación"""
    db = get_db()
    incident = db.session.query(SystemIncident).get(incident_id)
    
    if not incident:
        return jsonify({'error': 'Incidente no encontrado'}), 404
        
    data = request.json
    incident.status = 'resolved'
    incident.resolution_notes = data.get('notes', 'Reparación manual completada')
    incident.resolved_at = datetime.now()
    incident.resolved_by = g.user.username
    
    db.session.commit()
    return jsonify(incident.to_dict())

@reciclador_bp.route('/stats', methods=['GET'])
@login_required
@admin_required
def get_stats():
    """Estadísticas rápidas para el dashboard del centinela"""
    db = get_db()
    
    total_new = db.session.query(SystemIncident).filter(SystemIncident.status == 'new').count()
    critical = db.session.query(SystemIncident).filter(SystemIncident.severity == 'critical', SystemIncident.status == 'new').count()
    total_resolved = db.session.query(SystemIncident).filter(SystemIncident.status == 'resolved').count()
    
    return jsonify({
        'new_incidents': total_new,
        'critical_incidents': critical,
        'resolved_incidents': total_resolved
    })
