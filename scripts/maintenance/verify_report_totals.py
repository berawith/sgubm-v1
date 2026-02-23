
import json
from src.presentation.api.reports_controller import get_clients_status_report
from flask import Flask, request

app = Flask(__name__)

def test_report_totals(router_id, month, year):
    with app.test_request_context(f'/api/reports/clients-status?router_id={router_id}&month={month}&year={year}&type=paid'):
        response = get_clients_status_report()
        data = json.loads(response.data)
        print(f"--- Report Totals for Router {router_id} (Type: paid) ---")
        print(f"Total Collected: {data.get('total_collected')}")
        print(f"Total Pending (Router-wide): {data.get('total_pending')}")
        print(f"Total Credit (Router-wide): {data.get('total_credit')}")
        print(f"Client count in this report: {len(data.get('clients', []))}")

if __name__ == "__main__":
    # Test with a router ID (e.g., 1 if it exists)
    try:
        test_report_totals(1, 2, 2026)
    except Exception as e:
        print(f"Error testing report: {e}")
