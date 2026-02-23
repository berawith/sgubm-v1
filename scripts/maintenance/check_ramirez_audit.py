import sqlite3
import json

def check_audit(client_id):
    conn = sqlite3.connect('sgubm.db')
    cursor = conn.cursor()
    
    # Audit Logs related to this client
    cursor.execute("SELECT id, timestamp, username, category, operation, entity_type, entity_id, description FROM audit_logs WHERE entity_id = ? AND entity_type = 'client' ORDER BY timestamp DESC", (client_id,))
    client_audit = cursor.fetchall()
    
    # Audit Logs related to payments (we don't know the ID yet, so search by description)
    cursor.execute("SELECT id, timestamp, username, category, operation, entity_type, entity_id, description FROM audit_logs WHERE description LIKE '%Marcelo%' OR description LIKE '%591%' ORDER BY timestamp DESC")
    general_audit = cursor.fetchall()

    results = {
        "client_audit": [],
        "general_audit": []
    }
    
    for a in client_audit:
        results["client_audit"].append({
            "id": a[0],
            "timestamp": a[1],
            "username": a[2],
            "category": a[3],
            "operation": a[4],
            "entity_type": a[5],
            "entity_id": a[6],
            "description": a[7]
        })
        
    for a in general_audit:
        results["general_audit"].append({
            "id": a[0],
            "timestamp": a[1],
            "username": a[2],
            "category": a[3],
            "operation": a[4],
            "entity_type": a[5],
            "entity_id": a[6],
            "description": a[7]
        })
        
    print(json.dumps(results, indent=2))
    conn.close()

if __name__ == "__main__":
    check_audit(591)
