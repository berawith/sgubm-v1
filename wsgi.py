"""
WSGI entry point for production deployment (Gunicorn + eventlet)
"""
from run import create_app
from src.application.services.automation_manager import AutomationManager

app = create_app()

# Start background automation (billing, traffic snapshots)
AutomationManager.get_instance().start()
