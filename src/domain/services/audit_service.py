
import hashlib
import json
from datetime import datetime

class AuditService:
    """
    Servicio de Auditoría Empresarial
    Encargado de la integridad de los registros financieros mediante hashing criptográfico.
    """
    
    @staticmethod
    def calculate_transaction_hash(entity_type, data_dict):
        """
        Calcula un hash SHA-256 único para una transacción.
        Incluye todos los campos críticos para garantizar la inmutabilidad.
        """
        # Extraer solo campos financieros y temporales críticos para el hash
        critical_fields = [
            'amount', 'currency', 'exchange_rate', 'base_amount',
            'payment_date', 'expense_date', 'total_amount', 'created_at',
            'client_id', 'payment_method', 'category'
        ]
        
        # Filtrar el dict y normalizar valores
        payload = {}
        for field in critical_fields:
            if field in data_dict:
                val = data_dict[field]
                if isinstance(val, datetime):
                    payload[field] = val.isoformat()
                elif isinstance(val, (float, int)):
                    payload[field] = round(float(val), 2)
                else:
                    payload[field] = str(val)
        
        # Añadir el tipo de entidad
        payload['_entity'] = entity_type
        
        # Serializar de forma determinista (sort_keys=True)
        content = json.dumps(payload, sort_keys=True).encode('utf-8')
        
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def verify_transaction_integrity(record, entity_type):
        """
        Verifica si el hash actual del registro coincide con los datos.
        """
        if not hasattr(record, 'transaction_hash') or not record.transaction_hash:
            return False, "Registro sin hash de integridad"
            
        current_data = record.to_dict()
        expected_hash = AuditService.calculate_transaction_hash(entity_type, current_data)
        
        if record.transaction_hash == expected_hash:
            return True, "Integridad verificada"
        else:
            return False, f"DISCREPANCIA DETECTADA: El registro ha sido alterado manualmente. Hash esperado: {expected_hash[:10]}... Actual: {record.transaction_hash[:10]}..."
