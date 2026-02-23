
from typing import Dict, Any, Optional
from datetime import datetime

class CurrencyService:
    """
    Servicio de Gestión Multimoneda
    Maneja conversiones entre VES, COP y USD para reportes consolidados.
    """
    
    def __init__(self, settings_repo):
        self.settings_repo = settings_repo

    def get_rate(self, from_currency: str, to_currency: str) -> float:
        """
        Obtiene la tasa de cambio entre dos monedas.
        Busca en la configuración del sistema (SystemSettings).
        """
        if from_currency == to_currency:
            return 1.0
            
        rate_key = f"RATE_{from_currency}_{to_currency}".upper()
        # Intentar obtener tasa directa
        rate = self.settings_repo.get_value(rate_key)
        
        if rate:
            return float(rate)
            
        # Intentar obtener tasa inversa
        inverse_key = f"RATE_{to_currency}_{from_currency}".upper()
        inverse_rate = self.settings_repo.get_value(inverse_key)
        
        if inverse_rate:
            return 1.0 / float(inverse_rate)
            
        # Tasas por defecto (referenciales)
        defaults = {
            'RATE_USD_COP': 4000.0,
            'RATE_USD_VES': 36.5,
            'RATE_COP_VES': 0.009
        }
        
        return defaults.get(rate_key, 1.0)

    def convert(self, amount: float, from_currency: str, to_currency: str) -> float:
        """Convierte un monto entre monedas"""
        if from_currency == to_currency:
            return amount
        
        rate = self.get_rate(from_currency, to_currency)
        return amount * rate

    def get_base_amount(self, amount: float, currency: str) -> float:
        """Convierte un monto a la moneda base del sistema (configurada como ERP_BASE_CURRENCY)"""
        base_currency = self.settings_repo.get_value('ERP_BASE_CURRENCY', 'USD')
        return self.convert(amount, currency, base_currency)
