
import logging
from datetime import datetime
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Expense
from src.domain.services.tax_engine import TaxEngine
from src.domain.services.currency_service import CurrencyService
from src.domain.services.audit_service import AuditService

logger = logging.getLogger(__name__)

class ExpenseService:
    """
    Servicio de Gestión de Gastos y Egresos Empresariales
    Maneja la lógica de impuestos, divisas y auditoría para la salida de capital.
    """
    
    def __init__(self):
        pass

    def register_expense(self, data: dict):
        """
        Registra un gasto aplicando reglas ERP de impuestos y multimoneda.
        """
        db = get_db()
        repo = db.get_expense_repository()
        settings_repo = db.get_system_setting_repository()
        
        amount = float(data.get('amount', 0))
        currency = data.get('currency', 'COP')
        
        # 1. Determinar contexto fiscal
        country = 'VEN' if currency.upper() in ['VES', 'USD'] else 'COL'
        
        # 2. Calcular Impuestos (Si aplica IVA deducible, etc.)
        tax_results = TaxEngine.calculate_taxes(amount, country, 'transfer', currency)
        
        # 3. Conversión Multimoneda
        currency_service = CurrencyService(settings_repo)
        base_amount = currency_service.get_base_amount(amount, currency)
        exchange_rate = currency_service.get_rate(currency, settings_repo.get_value('ERP_BASE_CURRENCY', 'USD'))
        
        # 4. Preparar datos para el repositorio
        expense_date = data.get('expense_date')
        if isinstance(expense_date, str) and expense_date:
            try:
                if 'T' in expense_date:
                    expense_date = datetime.fromisoformat(expense_date.replace('Z', '+00:00'))
                elif '-' in expense_date:
                    expense_date = datetime.strptime(expense_date, '%Y-%m-%d')
                elif '/' in expense_date:
                    expense_date = datetime.strptime(expense_date, '%d/%m/%Y')
                else:
                    expense_date = datetime.now()
            except:
                expense_date = datetime.now()
        else:
            # Si no viene o no es string, usar ahora (a menos que ya sea datetime)
            if not isinstance(expense_date, datetime):
                expense_date = datetime.now()

        expense_payload = {
            'description': data.get('description'),
            'amount': amount,
            'currency': currency,
            'base_amount': base_amount,
            'exchange_rate': exchange_rate,
            'tax_details': TaxEngine.format_tax_details(tax_results),
            'expense_date': expense_date,
            'category': data.get('category', 'variable'),
            'notes': data.get('notes', ''),
            'is_recurring': data.get('is_recurring', False),
            'created_by': data.get('created_by', 'admin'),
            'router_id': int(data['router_id']) if data.get('router_id') else None,
            'user_id': int(data['user_id']) if data.get('user_id') else None
        }
        
        # El repositorio ya calcula el hash en su método .create()
        return repo.create(expense_payload)
