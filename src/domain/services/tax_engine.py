
import json
from typing import Dict, Any, Optional

class TaxEngine:
    """
    Motor de Impuestos Regional (Venezuela & Colombia)
    Calcula automáticamente cargos tributarios según jurisdicción y método de pago.
    """
    
    @staticmethod
    def calculate_taxes(amount: float, country: str, payment_method: str, currency: str) -> Dict[str, Any]:
        """
        Calcula el desglose de impuestos según el contexto geográfico y financiero.
        """
        result = {
            'total_tax': 0.0,
            'details': [],
            'net_amount': amount
        }
        
        if country.upper() == 'VEN':
            # 1. IVA Venezuela (Generalmente incluido en precio, pero se desglosa si se requiere)
            # Default para ISP suele ser exento o tasa general del 16%
            # result['details'].append({'type': 'IVA', 'rate': 0.16, 'amount': amount * 0.16})
            
            # 2. IGTF (Impuesto a las Grandes Transacciones Financieras)
            # Se aplica un 3% si el pago es en divisas (USD, EUR) o criptoactivos distintos al Petro
            if currency.upper() in ['USD', 'EUR']:
                igtf_amount = amount * 0.03
                result['total_tax'] += igtf_amount
                result['details'].append({
                    'name': 'IGTF (3%)',
                    'rate': 0.03,
                    'amount': igtf_amount,
                    'is_retention': False
                })
                result['net_amount'] = amount + igtf_amount

        elif country.upper() == 'COL':
            # 1. IVA Colombia (19%)
            # En servicios de internet, suele estar excluido para estratos 1, 2 y 3.
            # En este ERP asumimos que calculamos si aplica.
            iva_rate = 0.19
            iva_amount = amount * iva_rate
            # result['total_tax'] += iva_amount
            # result['details'].append({'name': 'IVA (19%)', 'rate': iva_rate, 'amount': iva_amount})
            
            # 2. Retenciones (ReteFuente, ReteIVA, ReteICA)
            # Si el pago supera topes (UVR/UVT), se calculan retenciones.
            # Este es un motor simplificado inicial.
            pass

        return result

    @staticmethod
    def format_tax_details(tax_result: Dict[str, Any]) -> str:
        """Serializa los detalles de impuestos para almacenamiento en DB"""
        return json.dumps(tax_result.get('details', []))
