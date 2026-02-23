
import json
from src.presentation.api.reports_controller import get_clients_status_report
from flask import Flask, request

app = Flask(__name__)

def test_router_2():
    # Simulate a request for Router 2, Feb 2026, type=paid (or debtors, doesn't matter for the global totals)
    with app.test_request_context('/api/reports/clients-status?router_id=2&month=2&year=2026&type=paid'):
        response = get_clients_status_report()
        data = json.loads(response.data)
        print(f"API Response for Router 2:")
        print(f"Total Collected: {data.get('total_collected')}")
        print(f"Total Pending: {data.get('total_pending')}")
        print(f"Total Credit: {data.get('total_credit')}")

if __name__ == "__main__":
    test_router_2()
