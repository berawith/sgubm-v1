from flask import Blueprint, jsonify
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Payment, Client
from sqlalchemy import func
from datetime import datetime, timedelta

health_bp = Blueprint('health', __name__, url_prefix='/api/health')

@health_bp.route('/integrity', methods=['GET'])
def get_integrity_status():
    """Returns a summary of system data integrity checks"""
    db = get_db()
    session = db.session
    
    issues = []
    
    # 1. Duplicate Payments (Reference)
    dup_refs = session.query(
        Payment.reference, 
        func.count(Payment.id).label('qty')
    ).filter(Payment.reference != '', Payment.reference != None)\
     .group_by(Payment.reference)\
     .having(func.count(Payment.id) > 1).all()
    
    if dup_refs:
        issues.append({
            "type": "duplicate_references",
            "severity": "high",
            "count": len(dup_refs),
            "description": "Existen pagos con referencias duplicadas en el sistema."
        })
        
    # 2. Balance Inconsistencies
    inconsistent_suspended = session.query(Client).filter(
        Client.account_balance > 0,
        Client.status == 'active'
    ).count()
    
    if inconsistent_suspended > 0:
        issues.append({
            "type": "balance_mismatch",
            "severity": "medium",
            "count": inconsistent_suspended,
            "description": f"Hay {inconsistent_suspended} clientes activos con deuda pendiente (>0)."
        })
        
    return jsonify({
        "status": "warning" if issues else "ok",
        "last_check": datetime.now().isoformat(),
        "issues": issues,
        "summary": {
            "is_clean": len(issues) == 0,
            "total_issues": len(issues)
        }
    })
