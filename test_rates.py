from flask import current_app
from src.infrastructure.database.db_manager import DatabaseManager
import run

app = run.create_app()

with app.app_context():
    app.test_request_context('/api/payments/rates').push()
    from src.presentation.api.payments_controller import get_exchange_rates
    try:
        response = get_exchange_rates()
        print(response.get_json())
    except Exception as e:
        import traceback
        traceback.print_exc()
