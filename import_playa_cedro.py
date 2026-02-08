
import logging
from datetime import datetime
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Router, NetworkSegment, Client, InternetPlan
from src.infrastructure.mikrotik.adapter import MikroTikAdapter
from src.application.services.billing_service import BillingService

# Data
ROUTER_DATA = {
    'alias': 'PLAYA DE CEDRO',
    'host_address': '12.12.12.172',
    'api_username': 'admin',
    'api_password': 'b1382285**',
    'api_port': 8728,
    'status': 'online',
    'zone': 'PLAYA DE CEDRO'
}

SEGMENT_CIDR = '174.17.10.0/24'
DEFAULT_FEE = 90000.0
PLAN_NAME_DEFAULT = 'Plan_Playa_Cedro_90K'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_import():
    # Use get_db() to get the DatabaseManager instance
    db_manager = get_db()
    session = db_manager.session
    
    # 1. Create/Get Router
    router = session.query(Router).filter_by(host_address=ROUTER_DATA['host_address']).first()
    if not router:
        logger.info("Creating router...")
        router = Router(**ROUTER_DATA)
        session.add(router)
        session.commit()
    else:
        logger.info(f"Router found: {router.alias}")
        
    # 2. Create/Get Segment
    segment = session.query(NetworkSegment).filter_by(cidr=SEGMENT_CIDR, router_id=router.id).first()
    if not segment:
        logger.info("Creating network segment...")
        segment = NetworkSegment(name='Gestion Interna Playa Cedro', cidr=SEGMENT_CIDR, router_id=router.id)
        session.add(segment)
        session.commit()
        
    # 3. Create Default Plan if not exists (to map the 90k)
    plan = session.query(InternetPlan).filter_by(name=PLAN_NAME_DEFAULT).first()
    if not plan:
        logger.info("Creating default plan...")
        plan = InternetPlan(
            name=PLAN_NAME_DEFAULT,
            download_speed=10000, # Assuming 10M default if unknown
            upload_speed=10000,
            monthly_price=DEFAULT_FEE,
            service_type='pppoe',
            router_id=router.id
        )
        session.add(plan)
        session.commit()
        
    # 4. Connect and Fetch Clients
    adapter = MikroTikAdapter()
    if not adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
        logger.error("Could not connect to MikroTik!")
        return

    logger.info("Connected to MikroTik. Fetching PPPoE secrets...")
    secrets = adapter.get_all_pppoe_secrets()
    
    imported_count = 0
    
    for secret in secrets:
        name = secret.get('name')
        profile = secret.get('profile')
        remote_address = secret.get('remote-address') 
        
        if not name: continue
        
        # Check if already exists
        exists = session.query(Client).filter(Client.router_id == router.id, Client.username == name).first()
        if exists:
            logger.info(f"Skipping existing client {name}")
            continue
            
        # Basic Validation (Simple)
        if profile == 'default': continue
        
        # Create Client
        new_client = Client(
            router_id=router.id,
            plan_id=plan.id,
            subscriber_code=f"PC-{name[:6].upper()}", # Generate code
            legal_name=name, # Default to username as name
            username=name,
            password=secret.get('password', ''),
            ip_address=remote_address,
            status='active' if not secret.get('disabled') else 'suspended',
            monthly_fee=DEFAULT_FEE,
            plan_name=PLAN_NAME_DEFAULT,
            service_type='pppoe',
            created_at=datetime.utcnow()
        )
        session.add(new_client)
        imported_count += 1
        
    session.commit()
    logger.info(f"Imported {imported_count} clients.")
    adapter.disconnect()
    
    # 5. Generate Invoices
    if imported_count > 0:
        logger.info("Generating invoices for new clients...")
        bs = BillingService()
        now = datetime.now()
        bs.generate_monthly_invoices(year=now.year, month=now.month, router_id=router.id)
        logger.info("Invoices generated.")

if __name__ == "__main__":
    run_import()
