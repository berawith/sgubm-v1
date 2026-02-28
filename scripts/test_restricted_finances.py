import os
import sys

sys.path.insert(0, os.path.abspath('.'))

from run import create_app
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import User
from src.application.services.auth import AuthService

test_user = None

def mock_validate(token):
    return test_user

AuthService.validate_session = staticmethod(mock_validate)

app = create_app()

with app.app_context():
    db = get_db()
    session = db.session
    collector = session.query(User).filter(User.role == 'collector').first()
    
    if not collector:
        print("No collector found in the database. Cannot verify.")
    else:
        test_user = collector
        print(f"Testing with collector: {collector.username} (ID: {collector.id})")
        print(f"Legacy Assigned Router ID: {collector.assigned_router_id}")
        
        assignments = []
        if hasattr(collector, 'assignments'):
            assignments = [a.router_id for a in collector.assignments]
        print(f"Router Assignments: {assignments}")
        
        headers = {'Authorization': 'Bearer fake-token'}
        
        print("\n--- Testing /api/reports/financial ---")
        with app.test_request_context('/api/reports/financial?period=annual', method='GET', headers=headers):
            from flask import g
            g.user = collector
            
            from src.presentation.api.reports_controller import get_financial_reports
            try:
                response = get_financial_reports()
                
                if isinstance(response, tuple):
                    res, status = response
                    print(f"Status Code: {status}")
                    data = res.get_json() if hasattr(res, 'get_json') else res
                else:
                    print(f"Status Code: {response.status_code}")
                    data = response.get_json()
                
                if data and 'error' in data:
                     print(f"Error returned: {data['error']}")
                elif data:
                    print("Summary Total Collected:", data.get('summary', {}).get('total_collected'))
                    print("Loss By Router Breakdown:")
                    breakdown = data.get('summary', {}).get('loss_by_router', {})
                    if not breakdown:
                        print("  (Empty)")
                    for k, v in breakdown.items():
                        print(f"  - {k}: {v}")
            except Exception as e:
                import traceback
                traceback.print_exc()

        print("\n--- Testing /api/payments/statistics ---")
        with app.test_request_context('/api/payments/statistics', method='GET', headers=headers):
            from flask import g
            g.user = collector
            
            from src.presentation.api.payments_controller import get_statistics
            try:
                response = get_statistics()
                
                if isinstance(response, tuple):
                    res, status = response
                    print(f"Status Code: {status}")
                    data = res.get_json() if hasattr(res, 'get_json') else res
                else:
                    print(f"Status Code: {response.status_code}")
                    data = response.get_json()
                
                if data and 'error' in data:
                     print(f"Error returned: {data['error']}")
                elif data:
                    print("Totals -> Filtered Period Total:", data.get('totals', {}).get('filtered_period_total'))
                    print("Totals -> Expenses (should be 0 for restricted roles):", data.get('totals', {}).get('month_expenses'))
            except Exception as e:
                import traceback
                traceback.print_exc()
