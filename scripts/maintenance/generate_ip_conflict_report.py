
import os
import sys

# Add the project root to sys.path
sys.path.append(os.getcwd())

from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client
from src.application.services.report_service import ReportService
from sqlalchemy import func

def generate_report():
    print("🚀 Generating IP Conflict Report...")
    db = get_db()
    session = db.session
    
    try:
        # 1. Find duplicate IPs
        duplicates = session.query(
            Client.ip_address, 
            func.count(Client.ip_address).label('count')
        ).filter(
            Client.ip_address != None,
            Client.ip_address != '',
            Client.ip_address != 'N/A'
        ).group_by(
            Client.ip_address
        ).having(
            func.count(Client.ip_address) > 1
        ).all()
        
        duplicates_data = []
        if duplicates:
            print(f"⚠️ Found {len(duplicates)} duplicate IPs.")
            for ip, count in duplicates:
                clients = session.query(Client).filter(Client.ip_address == ip).all()
                clients_list = []
                for c in clients:
                    clients_list.append({
                        'code': c.subscriber_code,
                        'name': c.legal_name,
                        'router': c.router.alias if c.router else 'N/A',
                        'status': c.status
                    })
                
                duplicates_data.append({
                    'ip': ip,
                    'count': count,
                    'clients': clients_list
                })
        else:
            print("✅ No duplicates found.")

        # 2. Generate PDF
        pdf_buffer = ReportService.generate_duplicate_ips_report(duplicates_data)
        
        # 3. Save to file
        filename = 'reporte_conflictos_ip.pdf'
        with open(filename, 'wb') as f:
            f.write(pdf_buffer.getvalue())
            
        print(f"📄 Report saved successfully: {filename}")
        
    except Exception as e:
        print(f"❌ Error generating report: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    generate_report()
