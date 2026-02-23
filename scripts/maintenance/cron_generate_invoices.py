
import logging
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from src.infrastructure.database.db_manager import init_db, get_db
from src.application.services.billing_service import BillingService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("billing_job.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("BillingCron")

def run_job():
    logger.info("🕒 Starting Billing Job...")
    
    try:
        # Initialize App Context (DB)
        # We need to simulate the app context or just init db manually
        # Since get_db uses flask g, we might need a workaround or just use the service directly if it manages sessions well.
        # But get_db relies on Flask app context usually.
        # Let's check db_manager.py implementation. 
        # Actually, let's use the create_app approach if possible, or just setup the DB session manually.
        
        # Checking db_manager implementation in mind... usually it checks 'g'. 
        # If we are outside request context, we should create a manual session.
        # Let's import the engine and sessionmaker directly to be safe, or use app.app_context().
        
        from run import create_app
        app = create_app()
        
        with app.app_context():
            service = BillingService()
            now = datetime.now()
            
            # Check if today is the billing day (e.g., day 1)
            # For now, we force generation if run, leveraging the idempotency of the service.
            
            logger.info(f"📅 Date: {now.strftime('%Y-%m-%d')}")
            result = service.generate_monthly_invoices()
            
            logger.info(f"✅ Job Finished. created={result['created']} skipped={result['skipped']} errors={result['errors']}")
            
    except Exception as e:
        logger.error(f"❌ Job Failed: {e}", exc_info=True)

if __name__ == "__main__":
    run_job()
